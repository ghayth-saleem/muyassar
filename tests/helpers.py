"""Shared test setup: a logged run replayed without network, models or API.

The provider is a ReplayProvider (the logged replies), and search is replaced
by the articles each agent retrieved in that run, so neither the embedding
models nor the API are touched.
"""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MUYASSAR_LLM", "anthropic")  # never reached: tests install a replay provider

from muyassar import agents, llm, scenarios  # noqa: E402
from muyassar.providers import ReplayProvider  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


def load_run(name: str) -> list[dict]:
    return [json.loads(l) for l in (FIXTURES / f"{name}_run.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def hit(r: dict) -> dict:
    """A logged retrieved item back in the shape retrieval.search returns."""
    meta = {k: r.get(k) for k in ("doc_name", "article", "url", "layer", "jurisdiction")}
    meta["doc_id"] = r["id"].split(":")[0]
    return {"id": r["id"], "text": f"{r['doc_name']} - {r['article']}\n{r['text']}", "metadata": meta, "score": r.get("score", 0)}


class ReplaySearch:
    """Serves each agent's logged articles on its main search, in run order.
    Extra-layer searches return nothing new: the logged list already holds them."""

    def __init__(self, steps: list[dict]):
        self.queue = [s for s in steps if s["agent"] not in ("orchestrator", "human")]

    def __call__(self, query, k=5, mode=None, layer=None):
        if layer:
            return []
        step = self.queue.pop(0)
        return [hit(r) for r in step["retrieved"]]


class Replay:
    """Context manager: replay `steps` through the real engine into a temp log."""

    def __init__(self, steps: list[dict]):
        self.steps = copy.deepcopy(steps)

    def __enter__(self):
        self.provider = ReplayProvider(self.steps)
        llm.use(self.provider)
        self._search, agents.search = agents.search, ReplaySearch(self.steps)
        self._log = scenarios.LOG
        self.tmp = tempfile.TemporaryDirectory()
        scenarios.LOG = Path(self.tmp.name) / "replay.jsonl"
        return self

    def __exit__(self, *exc):
        llm.use(None)
        agents.search = self._search
        scenarios.LOG = self._log
        self.tmp.cleanup()
        return False
