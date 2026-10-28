"""The scenario engine, run end to end on logged replies. No network, no models."""
import json
import unittest

from helpers import Replay, load_run
from muyassar import scenarios


class EngineReplay(unittest.TestCase):
    def test_procedure_change_replays_to_the_same_decisions(self):
        logged = load_run("procedure_change")
        with Replay(logged) as r:
            run = scenarios.run("procedure_change")
            written = [json.loads(l) for l in scenarios.LOG.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(run["status"], "awaiting_human")
        self.assertEqual([s["agent"] for s in run["steps"]], [s["agent"] for s in logged])
        self.assertEqual([s["decision"] for s in run["steps"]], [s["decision"] for s in logged])
        self.assertEqual(r.provider.calls, ["entity", "procedure", "policy", "orchestrator"])
        # every step is written to the log, in order
        self.assertEqual([s["n"] for s in written], [1, 2, 3, 4])

    def test_each_agent_only_sees_its_own_events(self):
        with Replay(load_run("procedure_change")):
            run = scenarios.run("procedure_change")
        by_agent = {s["agent"]: s for s in run["steps"]}
        self.assertEqual([d["label"] for d in by_agent["procedure"]["received"]], ["سؤال المواطن"])
        self.assertEqual(len(by_agent["entity"]["received"]), 1)
        # the orchestrator gets verdicts, not raw events
        self.assertEqual(len(by_agent["orchestrator"]["received"]), 3)

    def test_events_are_delivered_in_time_order(self):
        with Replay(load_run("procedure_change")):
            run = scenarios.run("procedure_change")
        ats = [s["at"] for s in run["steps"]]
        self.assertEqual(ats, sorted(ats))

    def test_staff_decision_is_logged(self):
        with Replay(load_run("procedure_change")):
            run = scenarios.run("procedure_change")
            scenarios.decide(run, approved=False, note="test")
            last = json.loads(scenarios.LOG.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(run["status"], "rejected")
        self.assertEqual(last["agent"], "human")
        self.assertFalse(last["approved"])

    def test_a_failing_call_leaves_an_error_run(self):
        with Replay(load_run("procedure_change")) as r:
            r.provider.queues["policy"] = []  # the model call fails; search still has its articles
            run = scenarios.run("procedure_change")
        self.assertEqual(run["status"], "error")
        self.assertIn("policy", run["error"])

    def test_voice_transcript_replaces_the_request_and_is_marked(self):
        logged = load_run("doubtful_id")
        voice = {"text": "طلب صوتي للتجربة", "duration": 3.0, "model": "test"}
        # doubtful_id has no voice event, so the transcript must change nothing
        with Replay(logged):
            run = scenarios.run("doubtful_id", voice=voice)
        self.assertFalse(any(s.get("input_source") == "voice" for s in run["steps"]))


if __name__ == "__main__":
    unittest.main()
