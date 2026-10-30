"""The same scenarios with the governance taken away, to show what it changes.

    python scripts/baseline.py                 # 3 runs each, all scenarios
    python scripts/baseline.py -n 1 doubtful_id
    python scripts/baseline.py --report-only logs/baseline/2026-10-30.jsonl

One plain assistant receives every event at once. It has no knowledge base, no
agents, no citation rule and no stop for staff, and it is asked to decide. The
model and the question are the ones the governed system uses, so the difference
is the governance. Runs use credit: one model call each.

Runs go to logs/baseline/<date>.jsonl, the table to eval/baseline.md. Per
scenario it counts, out of N:
- it stopped for staff (action = refer_to_staff) instead of deciding,
- it named the expected gap, with the same keyword test as scripts/consistency.py,
- it cited at least one article,
- it cited an article scripts/check_citations.py cannot find in the knowledge
  base: not proof the article is invented, only that nothing here backs it.
The governed numbers to read beside these are in eval/consistency.md.
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_citations as cc  # noqa: E402
from consistency import found_gap  # noqa: E402
from muyassar import ROOT, llm, scenarios  # noqa: E402

OUT = ROOT / "eval" / "baseline.md"
SYSTEM = "أنت مساعد آلي لخدمات الحكومة الأردنية. اقرأ ما وصلك، قرر ما يجب فعله، واكتب الرد على المواطن. إذا اعتمدت على نص قانوني فاذكر اسمه ورقم المادة."
SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["proceed", "reject", "refer_to_staff"]},
        "reply": {"type": "string"},
        "reasoning": {"type": "string"},
        "gap": {"type": "string"},
    },
    "required": ["action", "reply", "reasoning", "gap"],
    "additionalProperties": False,
}


def prompt(scenario: dict) -> str:
    events = sorted(scenario["events"], key=lambda e: e["at"])
    received = "\n".join(f"- [{e['label']}] {scenarios._content(e)}" for e in events)
    return f"سؤال الحالة: {scenario['question']}\n\nما وصلك:\n{received}\n\nفي gap اذكر أي نقص في القانون الأردني لاحظته، أو اتركه فارغاً."


def run_once(scenario: dict) -> dict:
    reply = llm.ask(SYSTEM, prompt(scenario), max_tokens=6000, schema=SCHEMA)
    return {
        "scenario": scenario["id"],
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": llm.model_name(),
        **reply,
    }


def score(runs: list[dict], scenario: dict, articles: dict) -> dict:
    row = {"runs": len(runs), "staff": 0, "gap": 0, "cited": 0, "unbacked": 0}
    for r in runs:
        problems, ok = [], []
        cc.check_text("baseline", f"{r['reply']} {r['reasoning']}", set(), articles, problems, ok)
        row["staff"] += r["action"] == "refer_to_staff"
        row["gap"] += found_gap(r, scenario["gap_check"])
        row["cited"] += bool(problems or ok)
        row["unbacked"] += bool(problems)
    return row


def report(log: Path) -> str:
    runs = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    articles = cc.load_kb()[1]
    lines = [
        "# بدون حوكمة",
        "",
        "نفس السيناريوهات بنفس النموذج، لكن مساعد واحد بدون قاعدة معرفة ولا قواعد ولا وقف للموظف. قارنها بجدول `eval/consistency.md`.",
        "",
        "| السيناريو | وقف لموظف | لقى الفجوة المتوقعة | ذكر مادة | ذكر مادة مش موجودة بقاعدة المعرفة |",
        "|---|---|---|---|---|",
    ]
    for sc in scenarios.all_scenarios():
        mine = [r for r in runs if r["scenario"] == sc["id"]]
        r = score(mine, sc, articles)
        n = r["runs"]
        lines.append(f"| {sc['title']} | {r['staff']}/{n} | {r['gap']}/{n} | {r['cited']}/{n} | {r['unbacked']}/{n} |")
    lines += [
        "",
        "«مادة مش موجودة بقاعدة المعرفة»: ما لقيناها عندنا، وهذا لا يثبت أنها مختلقة. لازم تنقرأ بالسجل قبل ما نحكي عنها أي شي.",
        "",
        f"السجل: `{log.resolve().relative_to(ROOT.resolve()).as_posix()}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("ids", nargs="*")
    p.add_argument("-n", type=int, default=3)
    p.add_argument("--report-only", type=Path)
    args = p.parse_args()
    log = args.report_only or ROOT / "logs" / "baseline" / f"{date.today()}.jsonl"
    if not args.report_only:
        log.parent.mkdir(parents=True, exist_ok=True)
        for sc in scenarios.all_scenarios():
            if args.ids and sc["id"] not in args.ids:
                continue
            for i in range(args.n):
                line = run_once(sc)
                with log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
                print(sc["id"], i + 1, line["action"])
    OUT.write_text(report(log), encoding="utf-8")
    print(f"الجدول في {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
