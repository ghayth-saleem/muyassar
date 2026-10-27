"""Policy gap report from the latest logged run of every scenario.

    python -m muyassar.gaps          # writes reports/gaps.md

Each gap is what the policy agent found in its own words, with the Jordanian
articles it retrieved and cited and any international example it named, next
to the gap the scenario was designed to expose. Nothing here is written by
hand, so the report shows what the agents found, not what we expected.
"""
import sys

from muyassar import ROOT
from muyassar.scenarios import all_scenarios, latest_run

OUT = ROOT / "reports" / "gaps.md"


def _ref(step: dict, cid: str) -> str:
    s = next(r for r in step["retrieved"] if r["id"] == cid)
    unit = f"المادة {s['article']}" if s["article"].split()[0].isdigit() else s["article"]
    return f"{s['doc_name']}، {unit}"


def build() -> str:
    lines = [
        "# تقرير الفجوات",
        "",
        "مولّد آلياً من آخر تشغيل لكل سيناريو في `logs/scenarios.jsonl` (`python -m muyassar.gaps`).",
        "الفجوة كما وصفها وكيل السياسات، والمواد التي استند إليها، والمثال العالمي إن ذكره.",
        "",
    ]
    for i, sc in enumerate(all_scenarios(), 1):
        run = latest_run(sc["id"])
        lines += [f"## {i}. {sc['title']} ({sc['service']})", "", f"**سؤال الحالة:** {sc['question']}", "",
                  f"**الفجوة المتوقعة عند التصميم:** {sc['expected_gap']}", ""]
        if not run:
            lines += ["_لم يُشغَّل بعد._", ""]
            continue
        policy = [s for s in run["steps"] if s["agent"] == "policy"]
        final = next(s for s in run["steps"] if s["agent"] == "orchestrator")
        found = [s for s in policy if s.get("gap")]
        if found:
            for s in found:
                lines += [f"**الفجوة التي وجدها الوكيل:** {s['gap_title']}", "", s["gap"], ""]
                if s["cited"]:
                    lines += ["**النصوص الأردنية الأقرب:**", ""] + [f"- {_ref(s, c)}" for c in s["cited"]] + [""]
                if s.get("international"):
                    lines += [f"**مثال عالمي:** {s['international']}", ""]
        else:
            lines += ["**لم يجد وكيل السياسات فجوة.** " + (policy[-1]["finding"] if policy else ""), ""]
        if final.get("conflicts"):
            lines += ["**تعارض بين الوكلاء:**", ""] + [f"- {c}" for c in final["conflicts"]] + [""]
        lines += [f"**قرار المنسّق:** {final['decision']} (ثقة {final['confidence']})"
                  + ("، بانتظار موافقة موظف" if run["status"] == "awaiting_human" else ""), "",
                  f"_التشغيل `{run['run_id']}` بتاريخ {run['started'][:10]}._", ""]
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build(), encoding="utf-8", newline="\n")
    print(f"كتبت {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
