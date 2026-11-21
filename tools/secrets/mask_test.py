"""Unit tests for tools/secrets/mask.py and guard_secrets.py (stdlib; make ci-guard)."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
tmp = tempfile.mkdtemp()
os.environ["BHOJANGO_SECRETS_DIR"] = tmp
Path(tmp, "BhojanGo_QA_Logins.txt").write_text(
    "Admin console\tfinance\tfinance.us@example.com\tPw-Abcdefgh123456\tTOTPKEYABCDEFGHIJKLMNOP\n"
    "Boise\tcustomer\tcustomer1.boi@example.com\tCustPw987654321\n", encoding="utf-8")
Path(tmp, "BhojanGo_Railway_Tokens.txt").write_text("QA: 11111111-2222-3333-4444-555555555555\n", encoding="utf-8")
Path(tmp, "BhojanGo_Stripe_Keys.txt").write_text("secret_key: sk_test_abcdefghijklmnop\n", encoding="utf-8")
sys.path.insert(0, str(ROOT / "tools" / "secrets"))
import mask as m  # noqa: E402

spec = importlib.util.spec_from_file_location("guard", ROOT / "tools" / "secrets" / "guard_secrets.py")
guard = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(guard)


FAKE_JWT = ".".join(["ey" + "J" + "x" * 14, "y" * 14, "z" * 14])  # built here: no token-shaped literal in the repo


class MaskTests(unittest.TestCase):
    def test_known_values_and_shapes_are_masked(self) -> None:
        text = ("pw Pw-Abcdefgh123456 key TOTPKEYABCDEFGHIJKLMNOP tok 11111111-2222-3333-4444-555555555555 "
                "stripe sk_test_abcdefghijklmnop other rk_live_ZZZZZZZZZZZZ Bearer abc.def.ghijklmnop "  # gitleaks:allow (fake values for the test)
                f"jwt {FAKE_JWT} cust CustPw987654321")
        out = m.mask(text)
        for secret in ("Pw-Abcdefgh123456", "TOTPKEYABCDEFGHIJKLMNOP", "11111111-2222", "sk_test_", "rk_live_",
                       "abc.def.ghijklmnop", FAKE_JWT, "CustPw987654321"):
            self.assertNotIn(secret, out)
        self.assertIn("finance", m.mask("finance.us@example.com"))  # emails stay

    def test_login_and_set_password_never_need_printing(self) -> None:
        self.assertEqual(m.login("finance.us@example.com"), ("Pw-Abcdefgh123456", "TOTPKEYABCDEFGHIJKLMNOP"))
        m.set_password("finance.us@example.com", "New-Pw-0987654321zz")
        self.assertEqual(m.login("finance.us@example.com"), ("New-Pw-0987654321zz", "TOTPKEYABCDEFGHIJKLMNOP"))
        self.assertEqual(m.login("customer1.boi@example.com")[0], "CustPw987654321")  # other rows untouched
        self.assertIn("<redacted>", m.mask("New-Pw-0987654321zz"))


class FailClosedTests(unittest.TestCase):
    """R25: no secrets files, no output. mask.py never passes text through unmasked."""
    MASK_PY = str(ROOT / "tools" / "secrets" / "mask.py")

    def run_mask(self, secrets_dir: str, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
        env = {**os.environ, "BHOJANGO_SECRETS_DIR": secrets_dir}
        return subprocess.run([sys.executable, self.MASK_PY, *args], input=stdin, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_missing_files_stop_it_with_the_folder_named_and_nothing_printed(self) -> None:
        empty = tempfile.mkdtemp()
        p = self.run_mask(empty, stdin="password Pw-Abcdefgh123456 in a log\n")
        self.assertEqual(p.returncode, m.EXIT_NO_SECRETS)
        self.assertEqual(p.stdout, "")  # the input is not passed through
        self.assertIn(empty, p.stderr)
        self.assertIn("BhojanGo_QA_Logins.txt", p.stderr)
        self.assertIn("BHOJANGO_SECRETS_DIR", p.stderr)

    def test_run_mode_does_not_run_the_command(self) -> None:
        marker = Path(tempfile.mkdtemp(), "ran.txt")
        p = self.run_mask(tempfile.mkdtemp(), "run", "--", sys.executable, "-c", f"open(r'{marker}', 'w').write('x')")
        self.assertEqual(p.returncode, m.EXIT_NO_SECRETS)
        self.assertFalse(marker.exists())

    def test_one_missing_file_is_enough_to_stop(self) -> None:
        partial = tempfile.mkdtemp()
        Path(partial, "BhojanGo_QA_Logins.txt").write_text("x\tfinance.us@example.com\tPw-Abcdefgh123456\n", encoding="utf-8")
        p = self.run_mask(partial, stdin="Pw-Abcdefgh123456\n")
        self.assertEqual((p.returncode, p.stdout), (m.EXIT_NO_SECRETS, ""))
        self.assertIn("BhojanGo_Stripe_Keys.txt", p.stderr)

    def test_with_the_files_it_masks(self) -> None:
        p = self.run_mask(tmp, stdin="pw CustPw987654321\n")
        self.assertEqual((p.returncode, p.stdout), (0, "pw <redacted>\n"))

    def test_in_python_a_missing_folder_raises(self) -> None:
        saved = m.DIR
        try:
            m.DIR = Path(tempfile.mkdtemp())
            with self.assertRaises(m.SecretsNotFound):
                m.secret_values()
        finally:
            m.DIR = saved


class ConfigTests(unittest.TestCase):
    def test_default_is_the_onedrive_products_folder_and_the_variable_overrides_it(self) -> None:
        import config
        saved = os.environ.pop("BHOJANGO_SECRETS_DIR")
        try:
            self.assertEqual(config.secrets_dir(), Path.home() / "OneDrive - DeepTrics LLC" / "Products")
            os.environ["BHOJANGO_SECRETS_DIR"] = "  "
            self.assertEqual(config.secrets_dir(), config.DEFAULT_DIR)  # blank counts as unset
        finally:
            os.environ["BHOJANGO_SECRETS_DIR"] = saved
        self.assertEqual(config.secrets_dir(), Path(tmp))
        self.assertEqual(m.DIR, Path(tmp))  # mask.py takes it from config.py


class HookTests(unittest.TestCase):
    def test_reading_a_secrets_file_unmasked_is_refused(self) -> None:
        for cmd in ('cat "C:/x/BhojanGo_QA_Logins.txt"', "python -c \"open(r'C:/x/BhojanGo_Stripe_Keys.txt').read()\"",
                    "Get-Content BhojanGo_Railway_Tokens.txt"):
            self.assertIsNotNone(guard.verdict(cmd), cmd)

    def test_masked_or_unrelated_commands_pass(self) -> None:
        for cmd in ('cat "C:/x/BhojanGo_QA_Logins.txt" | python tools/secrets/mask.py',
                    "python tools/secrets/mask.py run -- python x.py BhojanGo_Stripe_Keys.txt", "git status", "ls"):
            self.assertIsNone(guard.verdict(cmd), cmd)


if __name__ == "__main__":
    unittest.main()
