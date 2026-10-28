"""scripts/check_citations.py against the real knowledge-base chunks (read from disk, no models)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_citations as cc  # noqa: E402

CHUNKS, ARTICLES, SOURCES = cc.load_kb()


def check(text, retrieved=()):
    problems, ok = [], []
    cc.check_text("t", text, set(retrieved), ARTICLES, problems, ok)
    return problems, ok


class Mentions(unittest.TestCase):
    def test_existing_article(self):
        problems, ok = check("المادة 5 من قانون حماية البيانات الشخصية")
        self.assertEqual(problems, [])
        self.assertEqual(ok[0][2], "pdpl_2023")

    def test_missing_article(self):
        problems, _ = check("المادة 99 من قانون حماية البيانات الشخصية")
        self.assertIn("مش موجودة", problems[0][2])

    def test_clause_letter(self):
        self.assertEqual(check("المادة 5/أ من قانون حماية البيانات الشخصية")[0], [])
        self.assertTrue(check("المادة 5/ي من قانون حماية البيانات الشخصية")[0])

    def test_clause_letter_without_dash_in_source(self):
        # PDPL art. 4 opens «أ لكل شخص» with no dash after the letter
        self.assertEqual(check("المادة 4/أ من قانون حماية البيانات الشخصية")[0], [])

    def test_two_articles(self):
        problems, ok = check("المادتين 4 و20 من قانون حماية البيانات الشخصية")
        self.assertEqual(problems, [])
        self.assertEqual(sorted(r for _, r, _ in ok), ["20", "4"])

    def test_gdpr_wins_over_jordanian_pdpl(self):
        _, ok = check("المادة 22 من اللائحة العامة لحماية البيانات")
        self.assertEqual(ok[0][2], "gdpr_2016")

    def test_law_named_before_the_article(self):
        _, ok = check("قانون الأحوال المدنية، المادة 9")
        self.assertEqual(ok[0][2], "civil_status_2001")

    def test_does_not_cross_into_the_next_line_or_sentence(self):
        line = "- قانون حماية البيانات الشخصية، المادة 20\n**المثال العالمي:** اللائحة العامة لحماية البيانات"
        self.assertEqual(check(line)[0], [])
        sentence = "وفق المادة 6. ونصوص GDPR المرفقة غير ملزمة"
        problems, ok = check(sentence, retrieved=["pdpl_2023"])
        self.assertEqual(problems, [])
        self.assertEqual(ok[0][2], "pdpl_2023")

    def test_unknown_law_is_reported(self):
        problems, _ = check("المادة 9")
        self.assertIn("ما عرفنا", problems[0][2])


class KnowledgeBase(unittest.TestCase):
    def test_secondary_sources_are_flagged(self):
        self.assertEqual(SOURCES["pdpl_2023"], "secondary")
        self.assertEqual(SOURCES["gdpr_2016"], "official_eu")


if __name__ == "__main__":
    unittest.main()
