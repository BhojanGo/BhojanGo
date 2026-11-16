"""Unit tests for tools/i18n/check_wording.py (make ci-i18n; standard library only).

    python tools/i18n/check_wording_test.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_wording as w  # noqa: E402


class ProblemTests(unittest.TestCase):
    def test_the_word_in_text_fails(self) -> None:
        for text in ("Tip your rider", "Riders apply in the app", "the rider's tip", "tips are the riders' own",
                     "RIDER", "Rider + tip", "Finding a rider…"):
            self.assertIsNotNone(w.problem(text), text)

    def test_the_word_in_other_scripts_fails(self) -> None:
        for text in ("आपका राइडर", "तुमच्या रायडरला", "మీ రైడర్‌కు", "உங்கள் ரைடருக்கு", "ನಿಮ್ಮ ರೈಡರ್‌ಗೆ", "আপনার রাইডারের"):
            self.assertIsNotNone(w.problem(text), text)

    def test_old_app_names_fail(self) -> None:
        for text in ("Install the BhojanGo Rider app.", "BhojanGo Partner", "Open the partner app", "the Rider app",
                     "Partner app"):
            self.assertIsNotNone(w.problem(text), text)

    def test_the_new_words_pass(self) -> None:
        for text in ("Tip your delivery partner", "Delivery partner + tip", "BhojanGo Delivery", "BhojanGo Kitchen",
                     "Kitchen partner support", "Tu repartidor", "डिलीवरी पार्टनर", "డెలివరీ పార్ట్‌నర్",
                     "Deliver with BhojanGo", "Ride share", "our payments partner", "Override the price"):
            self.assertIsNone(w.problem(text), text)

    def test_placeholders_and_code_names_pass(self) -> None:
        for text in ("{rider} picked it up", "Your delivery partner, {rider}", "{n, plural, one {rider} other {x}}",
                     "rider.brand", "rider_id", "/api/v1/riders/me", "bhojango-rider", "riderId", "rider.sim.boi"):
            self.assertIsNone(w.problem(text), text)


class SourceTests(unittest.TestCase):
    def found(self, src: str) -> list[str]:
        return w.check_source(src, "x.tsx")

    def test_jsx_text_and_string_props_fail(self) -> None:
        self.assertTrue(self.found("<p>Give it to your rider at the door.</p>"))
        self.assertTrue(self.found("<p>\n  Riders are paid\n  every week.\n</p>"))
        self.assertTrue(self.found('<p>Ask {name}, your rider.</p>'))
        self.assertTrue(self.found('<select aria-label="Give it to a rider" />'))
        self.assertTrue(self.found('<img alt="Rider on a scooter" />'))
        self.assertTrue(self.found("<input placeholder='Note for the rider' />"))
        self.assertTrue(self.found("const label = `Give ${code} to a rider`;"))
        self.assertTrue(self.found('const COLS = [["rider_pay", "Rider pay (tips excluded)"]];'))
        self.assertTrue(self.found("<p>Tips are the rider&apos;s.</p>"))
        self.assertTrue(self.found("<p>The kitchen cooks; the rider delivers.</p>"))
        self.assertTrue(self.found('<Text>Install the BhojanGo Rider app</Text>'))

    def test_code_comments_and_keys_pass(self) -> None:
        src = """
        // the rider's position comes from the Drive tab
        /* Riders as circles */
        import { riderFirstName } from "@/lib/contract";
        const rider = riderFirstName(order);
        const s = { rider: { padding: 12 } };
        type Live = { rider: Pt | null; trail: Pt[] };
        interface O { rider?: { first_name?: string } | null; placed_at: string | null }
        const x = <View style={s.rider}>{rider ? t("track.s_heading", { rider }) : null}</View>;
        await api.realtime.POST("/api/v1/riders/me/online", { body: fix });
        <Button title="Go online" variant="rider" block />
        <Text testID="rider-name">{rider}</Text>
        queryKey: ["rider-docs", country],
        """
        self.assertEqual(self.found(src), [])

    def test_line_numbers(self) -> None:
        got = self.found('const a = 1;\n// rider\nconst b = "Tip your rider";\n')
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].startswith("x.tsx:3:"), got)


class FileTests(unittest.TestCase):
    def test_messages_values_not_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "en.json").write_text(json.dumps({"rider": {"brand": "BhojanGo Delivery", "tip": "Tip your rider"}}),
                                       encoding="utf-8")
            (d / "hi.json").write_text(json.dumps({"rider": {"brand": "BhojanGo Delivery", "tip": "राइडर को टिप"}},
                                                  ensure_ascii=False), encoding="utf-8")
            got = w.check_messages(d)
            self.assertEqual(len(got), 2, got)
            self.assertTrue(any("en.json: rider.tip" in g for g in got), got)
            self.assertTrue(any("hi.json: rider.tip" in g for g in got), got)

    def test_backend_catalogues(self) -> None:
        cats = {"backend/shared/texts.py": {"names.x": {"en": "Your rider", "te": "మీ డెలివరీ పార్ట్‌నర్"},
                                            "names.y": {"en": "{rider} is here"}}}
        got = w.check_catalogues(cats)
        self.assertEqual(got, ['backend/shared/texts.py: names.x [en] says "rider": say "delivery partner"'])

    def test_manifest_names_not_slugs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "app.json"
            p.write_text(json.dumps({"expo": {"name": "BhojanGo Rider", "slug": "bhojango-rider",
                                              "android": {"package": "com.bhojango.rider"}}}), encoding="utf-8")
            got = w.check_manifest(p, "apps/rider/app.json")
            self.assertEqual(len(got), 1, got)
            self.assertIn("BhojanGo Rider", got[0])

    def test_the_repo_passes(self) -> None:
        self.assertEqual(w.check_repo(), [])


if __name__ == "__main__":
    unittest.main()
