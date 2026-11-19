"""Unit tests for tools/secrets/identity_data_keys.py (stdlib; make ci-guard)."""
import base64
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import identity_data_keys as k  # noqa: E402


class KeysTests(unittest.TestCase):
    def test_value_is_a_json_list_of_fernet_keys(self) -> None:
        keys = json.loads(k.value(2))
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])
        for key in keys:
            self.assertEqual(len(base64.urlsafe_b64decode(key)), 32)  # Fernet: 32 bytes, URL-safe base64

    def test_prints_one_line_to_stdout_and_the_warning_to_stderr(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(k, "stdout_is_a_file", return_value=False), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(k.main([]), 0)
        self.assertEqual(len(out.getvalue().strip().splitlines()), 1)
        self.assertEqual(len(json.loads(out.getvalue())), 1)
        self.assertIn("SEALED", err.getvalue())
        self.assertNotIn(json.loads(out.getvalue())[0], err.getvalue())

    def test_refuses_to_write_into_a_file(self) -> None:
        with tempfile.TemporaryFile("w+") as f:
            err = io.StringIO()
            with mock.patch.object(sys, "stdout", f), contextlib.redirect_stderr(err):
                self.assertEqual(k.main([]), 2)
            f.seek(0)
            self.assertEqual(f.read(), "")
        self.assertIn("Refused", err.getvalue())


if __name__ == "__main__":
    unittest.main()
