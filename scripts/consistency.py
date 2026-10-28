"""Run every scenario N times and measure how stable the outcome is.

    python scripts/consistency.py              # 5 runs each, all scenarios
    python scripts/consistency.py -n 3 doubtful_id
    python scripts/consistency.py --log logs/consistency/x.jsonl procedure_change
    python scripts/consistency.py --report-only logs/consistency/a.jsonl logs/consistency/b.jsonl

With several logs, each scenario's row comes from the last log that has runs
of it, so a re-measured scenario replaces its older runs in the table.

Runs go to logs/consistency/<date>.jsonl, never to the main scenario log, and
the table is written to eval/consistency.md. Per scenario it counts, out of N:
- the policy agent found the expected gap: its gap text contains at least one
  word from every group in the scenario's `gap_check` (a transparent keyword
  test, not a model judge; read the gap texts in the log when it disagrees),
- the run stopped for staff approval, and how many of those stops the
  conflict rule caused (code, not the model; see muyassar/agents.py),
- some agent step had no surviving citation (unsourced),
- the gap came with a global-layer article the agent retrieved.

Sampling cannot be pinned: Claude Sonnet 5.5 rejects a non-default
temperature, so this measures the model as it runs in the demo.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from muyassar import ROOT, scenarios  # noqa: E402

OUT = ROOT / "eval" / "consistency.md"


def found_gap(step: dict, groups: list[list[str]]) -> bool:
    text = f"{step.get('gap_title', '')} {step.get('gap', '')}"
    return bool(step.get("gap")) and all(any(w in text for w in g) for g in groups)


def score(runs: list[dict], scenario: dict) -> dict:
    row = {"runs": len(runs), "gap": 0, "human": 0, "rule": 0, "unsourced": 0, "global": 0, "errors": 0}
    for run in runs:
        steps = run["steps"]
        policy = [s for s in steps if s["agent"] == "policy"]
        final = [s for s in steps if s["agent"] == "orchestrator"]
        if not final:
            row["errors"] += 1
            continue
        row["gap"] += any(found_gap(s, scenario["gap_check"]) for s in policy)
        row["human"] += final[0]["sensitive"]
        row["rule"] += bool(final[0].get("sensitive_rule"))
        row["unsourced"] += any(s.get("unsourced") for s in steps)
        row["global"] += any(s.get("gap") and s.get("global_example_id") for s in policy)
    return row


def runs_from_log(path: Path) -> dict[str, list[dict]]:
    by_run: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            s = json.loads(line)
            by_run.setdefault(s["run_id"], {"scenario": s["scenario"], "steps": []})["steps"].append(s)
    out: dict[str, list[dict]] = {}
    for run in by_run.values():
        out.setdefault(run["scenario"], []).append(run)
    return out


def report(logs: list[Path]) -> str:
    runs, source = {}, {}
    for log in logs:
        for sid, rs in runs_from_log(log).items():
            runs[sid], source[sid] = rs, log.resolve().relative_to(ROOT.resolve()).as_posix()
    lines = [
        "# ثبات النتائج",
        "",
        "كل سيناريو انشغّل أكثر من مرة بنفس المدخلات.",
        "النموذج Claude Sonnet 5.5 لا يقبل تغيير temperature، فالأرقام تقيس النظام كما يعمل في العرض.",
        "",
        "| السيناريو | لقى الفجوة المتوقعة | وقف لموافقة موظف | منها بقاعدة التعارض | خطوة بدون مصدر | مثال عالمي مسترجع | أخطاء | السجل |",
        "|---|---|---|---|---|---|---|---|",
    ]
    weak = []
    for sc in scenarios.all_scenarios():
        r = score(runs.get(sc["id"], []), sc)
        n = r["runs"] - r["errors"]  # a run cut short (e.g. out of API credit) is counted under errors, not scored
        lines.append(f"| {sc['title']} | {r['gap']}/{n} | {r['human']}/{n} | {r['rule']}/{n} | {r['unsourced']}/{n} | {r['global']}/{n} | {r['errors']} | `{source.get(sc['id'], '')}` |")
        if n and r["gap"] < 4 * n / 5:
            weak.append(sc["title"])
    lines += [
        "",
        "«منها بقاعدة التعارض»: التوقف فرضه الكود لأن وكيل الجهة أشار لدليل منشور مسترجع يخالفه ما وصله من الجهة.",
        "",
        "«لقى الفجوة المتوقعة»: نص الفجوة عند وكيل السياسات فيه كلمة واحدة على الأقل من كل مجموعة في `gap_check` بملف السيناريو. فحص بالكلمات، مش حكم نموذج.",
        "",
        "**تحت 4 من 5:** " + ("، ".join(weak) if weak else "لا يوجد."),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("ids", nargs="*")
    p.add_argument("-n", type=int, default=5)
    p.add_argument("--log", type=Path, help="log to write the runs to (default logs/consistency/<date>.jsonl)")
    p.add_argument("--report-only", type=Path, nargs="+")
    args = p.parse_args()

    log = args.log or ROOT / "logs" / "consistency" / f"{date.today().isoformat()}.jsonl"
    if not args.report_only:
        log.parent.mkdir(parents=True, exist_ok=True)
        scenarios.LOG = log  # keep these runs out of the main scenario log
        for sid in args.ids or [s["id"] for s in scenarios.all_scenarios()]:
            for i in range(args.n):
                r = scenarios.run(sid)
                print(f"{sid} {i + 1}/{args.n}: {r['status']} {r.get('error', '')}", flush=True)
    OUT.write_text(report(args.report_only or [log]), encoding="utf-8", newline="\n")
    print(f"كتبت {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
