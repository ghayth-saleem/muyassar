"""The conflict rule and the citation rule, checked in code paths, not prompts."""
import copy
import unittest

from helpers import Replay, load_run
from muyassar import agents, scenarios
from muyassar.agents import CONFLICT_RULE, _verdict


def src(id_, layer="law"):
    return {"id": id_, "doc_name": "doc", "article": "1", "layer": layer, "text": "", "score": 0}


def reply(**kw):
    base = {"steps": [], "finding": "", "decision": "d", "confidence": 0.5, "cited": [], "sensitive": False,
            "sensitive_reason": "", "contradicts_guide": False, "contradicted_id": "", "gap_title": "", "gap": "",
            "global_example_id": "", "global_example": ""}
    base.update(kw)
    return base


class CitationRule(unittest.TestCase):
    def test_citation_not_retrieved_is_dropped(self):
        v = _verdict(reply(cited=["a:1:1", "ghost:9:1"]), [src("a:1:1")])
        self.assertEqual(v["cited"], ["a:1:1"])
        self.assertEqual(v["dropped_citations"], ["ghost:9:1"])
        self.assertFalse(v["unsourced"])

    def test_no_surviving_citation_is_unsourced(self):
        v = _verdict(reply(cited=["ghost:9:1"]), [src("a:1:1")])
        self.assertTrue(v["unsourced"])

    def test_confidence_is_clamped(self):
        self.assertEqual(_verdict(reply(confidence=3), [])["confidence"], 1.0)
        self.assertEqual(_verdict(reply(confidence=-1), [])["confidence"], 0.0)

    def test_gap_needs_a_retrieved_global_article(self):
        sources = [src("pdpl:5:1"), src("gdpr:9:1", "global")]
        ok = _verdict(reply(gap="x", global_example_id="gdpr:9:1"), sources)
        self.assertFalse(ok["gap_no_global"])
        not_global = _verdict(reply(gap="x", global_example_id="pdpl:5:1"), sources)
        self.assertTrue(not_global["gap_no_global"])
        self.assertEqual(not_global["global_example_id"], "")
        invented = _verdict(reply(gap="x", global_example_id="gdpr:99:1"), sources)
        self.assertTrue(invented["gap_no_global"])

    def test_unsourced_step_is_logged_as_such(self):
        # the doubtful_id fixture predates the document-check fix: its checker cited nothing
        with Replay(load_run("doubtful_id")):
            run = scenarios.run("doubtful_id")
        checker = next(s for s in run["steps"] if s["agent"] == "docs_check")
        self.assertTrue(checker["unsourced"])
        self.assertEqual(checker["cited"], [])


class ConflictRule(unittest.TestCase):
    def test_contradiction_must_point_to_a_retrieved_guide(self):
        sources = [src("cspd:شروط:1", "procedure"), src("pdpl:5:1")]
        guide = _verdict(reply(contradicts_guide=True, contradicted_id="cspd:شروط:1"), sources)
        self.assertEqual(guide["contradicted_id"], "cspd:شروط:1")
        law = _verdict(reply(contradicts_guide=True, contradicted_id="pdpl:5:1"), sources)
        self.assertEqual(law["contradicted_id"], "")
        invented = _verdict(reply(contradicts_guide=True, contradicted_id="cspd:x:9"), sources)
        self.assertEqual(invented["contradicted_id"], "")
        unflagged = _verdict(reply(contradicts_guide=False, contradicted_id="cspd:شروط:1"), sources)
        self.assertEqual(unflagged["contradicted_id"], "")

    def test_rule_makes_the_final_decision_sensitive(self):
        with Replay(load_run("procedure_change")):
            run = scenarios.run("procedure_change")
        final = run["steps"][-1]
        self.assertTrue(final["sensitive"])
        self.assertEqual(final["sensitive_by"], "rule")
        self.assertEqual(final["sensitive_rule"], CONFLICT_RULE)
        self.assertIn("قاعدة التعارض", final["sensitive_reason"])
        self.assertEqual(run["status"], "awaiting_human")

    def test_without_the_contradiction_the_run_finishes(self):
        steps = copy.deepcopy(load_run("procedure_change"))
        for s in steps:
            if s["agent"] == "entity":
                s["contradicts_guide"], s["contradicted_id"] = False, ""
        with Replay(steps):
            run = scenarios.run("procedure_change")
        final = run["steps"][-1]
        self.assertNotIn("sensitive_rule", final)
        self.assertEqual(run["status"], "done")

    def test_orchestrator_cannot_drop_an_agents_sensitive_flag(self):
        verdicts = {"policy": {**_verdict(reply(sensitive=True), []), "sources": []}}
        original = agents.ask
        agents.ask = lambda *a, **k: reply(conflicts=[], citizen_reply="", staff_note="", sensitive=False)
        try:
            out = agents.run_orchestrator("q", verdicts)
        finally:
            agents.ask = original
        self.assertTrue(out["sensitive"])
        self.assertEqual(out["sensitive_by"], "agent")


if __name__ == "__main__":
    unittest.main()
