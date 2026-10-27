"""Scenario engine: replays a failure scenario event by event through the agents.

    python -m muyassar.scenarios                 # list scenarios
    python -m muyassar.scenarios doubtful_id     # run one, print the timeline

A scenario is scenarios/<id>.json: the case question and a list of events,
each with a simulated time `at` (seconds), the agent it goes `to`, a `label`
and its `content`. Events reach only their agent, in time order, and the
agent re-judges on everything it has received so far. When the events run
out the orchestrator combines the latest verdicts.

Every step is one line in logs/scenarios.jsonl: time, agent, what it
received, its steps, the articles it retrieved, its decision and confidence.
A sensitive final decision (rejecting a request, keeping health data) stops
the run at "awaiting_human" until a staff member approves or rejects it.
"""
import json
import sys
import threading
import uuid
from datetime import datetime, timezone

from muyassar import ROOT
from muyassar.agents import AGENTS, run_agent, run_orchestrator
from muyassar.llm import CLAUDE_MODEL, PROVIDER

SCENARIOS = ROOT / "scenarios"
LOG = ROOT / "logs" / "scenarios.jsonl"
_lock = threading.Lock()


def load(scenario_id: str) -> dict:
    return json.loads((SCENARIOS / f"{scenario_id}.json").read_text(encoding="utf-8"))


def all_scenarios() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SCENARIOS.glob("*.json"))]


def compare(document: dict, record: dict, labels: dict) -> str:
    """Field-by-field comparison of an uploaded document against the official record."""
    lines = []
    for field, label in labels.items():
        got, want = document.get(field), record.get(field)
        mark = "مطابق" if got == want else "غير مطابق"
        lines.append(f"{label}: الوثيقة «{got}»، السجل «{want}»: {mark}")
    return "نتيجة المقارنة الآلية:\n" + "\n".join(lines)


def _content(event: dict) -> str:
    if "compare" in event:
        c = event["compare"]
        return f"{event['content']}\n{compare(c['document'], c['record'], c['fields'])}"
    return event["content"]


def _write(line: dict) -> None:
    with _lock:
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8", newline="
") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _step(run: dict, agent: str, at: int, received: list[dict], verdict: dict) -> dict:
    step = {
        "time": _now(),
        "run_id": run["run_id"],
        "scenario": run["scenario"],
        "n": len(run["steps"]) + 1,
        "at": at,
        "agent": agent,
        "received": received,
        "steps": verdict["steps"],
        "retrieved": [
            {k: s[k] for k in ("id", "doc_name", "article", "url", "score", "text")} for s in verdict["sources"]
        ],
        "cited": verdict["cited"],
        "dropped_citations": verdict["dropped_citations"],
        "unsourced": verdict["unsourced"],
        "finding": verdict.get("finding") or verdict.get("staff_note", ""),
        "decision": verdict["decision"],
        "confidence": verdict["confidence"],
        "sensitive": verdict["sensitive"],
        "sensitive_reason": verdict["sensitive_reason"],
        "model": CLAUDE_MODEL if PROVIDER == "anthropic" else PROVIDER,
    }
    for extra in ("gap_title", "gap", "international", "conflicts", "citizen_reply", "staff_note"):
        if verdict.get(extra):
            step[extra] = verdict[extra]
    run["steps"].append(step)
    _write(step)
    return step


def run(scenario_id: str, on_step=None, run_id: str | None = None) -> dict:
    """Play the scenario. on_step(run) is called after every step, for live progress."""
    scenario = load(scenario_id)
    run = {
        "run_id": run_id or uuid.uuid4().hex[:8],
        "scenario": scenario_id,
        "started": _now(),
        "status": "running",
        "steps": [],
    }
    inboxes: dict[str, list[dict]] = {}
    verdicts: dict[str, dict] = {}
    try:
        for event in sorted(scenario["events"], key=lambda e: e["at"]):
            delivery = {"at": event["at"], "label": event["label"], "content": _content(event)}
            if event.get("simulated"):
                delivery["simulated"] = True
            inboxes.setdefault(event["to"], []).append(delivery)
            run["current"] = event["to"]
            on_step and on_step(run)
            verdicts[event["to"]] = run_agent(event["to"], scenario["question"], inboxes[event["to"]])
            _step(run, event["to"], event["at"], inboxes[event["to"]], verdicts[event["to"]])

        run["current"] = "orchestrator"
        on_step and on_step(run)
        final = run_orchestrator(scenario["question"], verdicts)
        last_at = max(e["at"] for e in scenario["events"])
        received = [
            {"at": last_at, "label": AGENTS[k].name, "content": f"{v['decision']}: {v['finding']}"}
            for k, v in verdicts.items()
        ]
        _step(run, "orchestrator", last_at, received, final)
        run["status"] = "awaiting_human" if final["sensitive"] else "done"
    except Exception as e:  # shown on the page; the steps so far stay logged
        run["status"] = "error"
        run["error"] = str(e)
    run.pop("current", None)
    on_step and on_step(run)
    return run


def decide(run: dict, approved: bool, note: str = "") -> dict:
    """A staff member's decision on a run that stopped for human approval."""
    final = run["steps"][-1]
    step = {
        "time": _now(),
        "run_id": run["run_id"],
        "scenario": run["scenario"],
        "n": len(run["steps"]) + 1,
        "at": final["at"],
        "agent": "human",
        "received": [{"at": final["at"], "label": "المنسّق", "content": final.get("staff_note", final["finding"])}],
        "decision": "موافقة الموظف" if approved else "رفض الموظف",
        "approved": approved,
        "note": note,
    }
    run["steps"].append(step)
    run["status"] = "approved" if approved else "rejected"
    _write(step)
    return run


def latest_run(scenario_id: str) -> dict | None:
    """Rebuild the most recent run of a scenario from the log, so the page can
    show a finished run without calling the model again."""
    if not LOG.is_file():
        return None
    runs: dict[str, list[dict]] = {}
    order = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        step = json.loads(line)
        if step.get("scenario") != scenario_id:
            continue
        if step["run_id"] not in runs:
            order.append(step["run_id"])
        runs.setdefault(step["run_id"], []).append(step)
    # Latest run that reached the orchestrator; a run cut short is not a demo.
    for run_id in reversed(order):
        steps = runs[run_id]
        agents = [s["agent"] for s in steps]
        if "orchestrator" not in agents:
            continue
        final = next(s for s in steps if s["agent"] == "orchestrator")
        human = next((s for s in steps if s["agent"] == "human"), None)
        status = ("approved" if human["approved"] else "rejected") if human else (
            "awaiting_human" if final["sensitive"] else "done")
        return {"run_id": run_id, "scenario": scenario_id, "started": steps[0]["time"], "status": status, "steps": steps}
    return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        for s in all_scenarios():
            print(f"{s['id']}: {s['title']}")
        return
    names = {**{k: a.name for k, a in AGENTS.items()}, "orchestrator": "المنسّق"}

    def show(r):
        if r.get("current"):
            print(f"... {names[r['current']]} يشتغل", flush=True)

    result = run(sys.argv[1], on_step=show)
    for s in result["steps"]:
        flag = " [بدون مصدر]" if s.get("unsourced") else ""
        flag += " [حساس]" if s.get("sensitive") else ""
        print(f"\nt+{s['at']}s {names.get(s['agent'], s['agent'])}: {s['decision']} ({s.get('confidence')}){flag}")
        print(f"  {s['finding'][:300]}")
        for c in s["cited"]:
            r = next(x for x in s["retrieved"] if x["id"] == c)
            print(f"  ← {r['doc_name']} / {r['article']}")
        if s.get("gap"):
            print(f"  فجوة: {s['gap_title']}: {s['gap']}")
        if s.get("citizen_reply"):
            print(f"  للمواطن: {s['citizen_reply']}")
    print(f"\nالحالة: {result['status']} {result.get('error', '')}")


if __name__ == "__main__":
    main()
