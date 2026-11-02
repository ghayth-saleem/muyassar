"""scripts/baseline.py with a stub model: no network, no models, nothing written to logs/."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import baseline  # noqa: E402
from muyassar import llm, scenarios  # noqa: E402


class Stub:
    name = "stub"

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def ask(self, system, user, max_tokens=16000, schema=None):
        self.calls.append((system, user, schema))
        return self.reply


def reply(**kw):
    return {"action": "reject", "reply": "طلبك مرفوض.", "reasoning": "", "gap": "", **kw}


class Baseline(unittest.TestCase):
    def setUp(self):
        self.sc = scenarios.load("doubtful_id")
        self.addCleanup(llm.use, None)

    def test_every_event_reaches_the_one_assistant(self):
        stub = Stub(reply())
        llm.use(stub)
        line = baseline.run_once(self.sc)
        user = stub.calls[0][1]
        self.assertEqual(len(stub.calls), 1)
        for e in self.sc["events"]:
            self.assertIn(e["label"], user)
        self.assertEqual((line["scenario"], line["model"]), ("doubtful_id", "stub"))

    def test_no_knowledge_base_text_is_given(self):
        stub = Stub(reply())
        llm.use(stub)
        baseline.run_once(self.sc)
        self.assertNotIn("النصوص:", stub.calls[0][1])

    def test_score(self):
        articles = baseline.cc.load_kb()[1]
        runs = [
            reply(action="refer_to_staff"),
            reply(reply="حسب المادة 5 من قانون حماية البيانات الشخصية"),
            reply(reply="حسب المادة 999 من قانون حماية البيانات الشخصية"),
        ]
        r = baseline.score(runs, self.sc, articles)
        self.assertEqual((r["runs"], r["staff"], r["cited"], r["unbacked"]), (3, 1, 2, 1))

    def test_report_table(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "x.jsonl"
            log.write_text(json.dumps({"scenario": "doubtful_id", **reply()}, ensure_ascii=False) + "\n", encoding="utf-8")
            baseline.ROOT = Path(d)
            try:
                text = baseline.report(log)
            finally:
                baseline.ROOT = ROOT
        self.assertIn("| وثيقة مشكوك فيها | 0/1 | 0/1 | 0/1 | 0/1 | 0/1 |", text)


if __name__ == "__main__":
    unittest.main()
