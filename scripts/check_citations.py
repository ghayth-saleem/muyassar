"""Check that every article the agents cite exists in the knowledge base.

    python scripts/check_citations.py                       # main log + reports/gaps.md
    python scripts/check_citations.py logs/consistency/2026-10-27.jsonl

Two kinds of citation are checked:
1. Cited ids (the `cited` and `global_example_id` fields): the chunk id must
   exist in kb/chunks. Ids from runs logged before a document was re-chunked
   show up here.
2. Articles named in the text ("المادة 5/أ"، "المادتين 4 و20"، "المواد 4 و5"):
   the law is taken from the words right after the mention, or else from the
   documents the step itself retrieved, and the article number must exist in
   that law's chunks. A lettered clause (أ، ب...) is checked in the article text.

It also lists every citation that rests on a text whose text_source is
`secondary` (not yet matched against the Official Gazette).
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Longest, most specific names first: "اللائحة العامة لحماية البيانات" must
# win over "حماية البيانات".
ALIASES = [
    ("gdpr_2016", ["اللائحة العامة لحماية البيانات", "GDPR", "اللائحة الأوروبية لحماية البيانات"]),
    ("eu_sdg_2018", ["البوابة الرقمية الموحدة"]),
    ("eu_ai_act_2024", ["قانون الذكاء الاصطناعي الأوروبي", "اللائحة 2024/1689"]),
    ("hcd_card_2025", ["تعليمات إصدار البطاقة التعريفية", "تعليمات البطاقة التعريفية", "البطاقة التعريفية"]),
    ("disability_2017", ["حقوق الأشخاص ذوي الإعاقة", "قانون الإعاقة"]),
    ("etl_2015", ["المعاملات الإلكترونية"]),
    ("civil_status_2001", ["الأحوال المدنية", "الاحوال المدنية"]),
    ("pdpl_2023", ["حماية البيانات الشخصية", "حماية البيانات"]),
    ("ai_ethics_2022", ["أخلاقيات الذكاء الاصطناعي", "الميثاق"]),
]
LETTERS = "أبجدهوزحطيكلمنسعفصقرشتثخذضظغ"
MENTION = re.compile(
    r"(?:المادة|المادتين|المادتان|المواد|مادة)\s+"
    r"((?:\d+(?:/[" + LETTERS + r"\d]+)*)(?:\s*(?:و|،|,|أو)\s*\d+(?:/[" + LETTERS + r"\d]+)*)*)"
)
TEXT_FIELDS = ("finding", "gap", "global_example", "citizen_reply", "staff_note", "steps")


def load_kb():
    chunks, articles, sources = {}, defaultdict(dict), {}
    for p in (ROOT / "kb" / "chunks").glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            m = c["metadata"]
            chunks[c["id"]] = c
            num = re.search(r"\d+", m["article"])
            if num and (m["doc_id"] in dict(ALIASES)):
                articles[m["doc_id"]].setdefault(num.group(), []).append(c["text"])
            sources[m["doc_id"]] = m.get("text_source")
    return chunks, articles, sources


def doc_for(text_after: str, text_before: str = "") -> str | None:
    """The law named right after the mention ("المادة 5 من قانون ..."), else the
    one named just before it on the same line ("قانون ...، المادة 5"). Never
    crosses a line break, so a list item does not borrow the next line's law."""
    # stop at the end of the sentence too: "وفق المادة 6. ونصوص GDPR..." is not GDPR's article 6
    after = re.split(r"\n|\.\s|؛", text_after, maxsplit=1)[0][:80]
    for doc_id, names in ALIASES:
        if any(n in after for n in names):
            return doc_id
    before = text_before.rsplit("\n", 1)[-1][-120:]
    best = None
    for doc_id, names in ALIASES:
        for n in names:
            i = before.rfind(n)
            if i >= 0 and (best is None or i > best[0]):
                best = (i, doc_id)
    return best[1] if best else None


def clause_present(texts: list[str], clause: str) -> bool:
    # "أ-", "أ.", "(أ)", or a bare letter opening a line ("أ لكل شخص": the source dropped the dash)
    pattern = re.compile(rf"(^|\n|\s|\(){re.escape(clause)}(\s*[-–.)]|\s*\))|(^|\n){re.escape(clause)}\s", re.M)
    return any(pattern.search(t) for t in texts)


def mentions(text: str):
    for m in MENTION.finditer(text):
        for ref in re.split(r"\s*(?:و|،|,|أو)\s*", m.group(1)):
            if ref:
                yield ref, text[m.end():], text[:m.start()]


def check_text(where: str, text: str, retrieved_docs: set[str], articles, problems, ok):
    for ref, after, before in mentions(text):
        num, *clauses = ref.split("/")
        doc = doc_for(after, before)
        candidates = [doc] if doc else sorted(d for d in retrieved_docs if d in articles)
        if not candidates:
            problems.append((where, ref, "ما عرفنا أي قانون (ما في اسم بعدها ولا مصدر مسترجع مرقّم)"))
            continue
        hits = [d for d in candidates if num in articles[d]]
        if not hits:
            problems.append((where, ref, f"المادة {num} مش موجودة في {', '.join(candidates)}"))
            continue
        letter = next((c for c in clauses if c in LETTERS or (len(c) == 1 and not c.isdigit())), None)
        if letter and not any(clause_present(articles[d][num], letter) for d in hits):
            problems.append((where, ref, f"المادة {num} موجودة في {hits[0]}، بس البند ({letter}) ما لقيناه بنصها"))
            continue
        ok.append((where, ref, hits[0] if len(hits) == 1 else "/".join(hits)))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    logs = [Path(a) for a in sys.argv[1:]] or [ROOT / "logs" / "scenarios.jsonl"]
    chunks, articles, text_source = load_kb()
    problems, ok, bad_ids, secondary = [], [], [], defaultdict(set)

    for log in logs:
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            s = json.loads(line)
            where = f"{s['scenario']}/{s['run_id']}#{s['n']} {s['agent']}"
            ids = list(s.get("cited", [])) + ([s["global_example_id"]] if s.get("global_example_id") else [])
            for cid in ids:
                if cid not in chunks:
                    bad_ids.append((where, cid))
                    continue
                doc = chunks[cid]["metadata"]["doc_id"]
                if text_source.get(doc) == "secondary":
                    secondary[cid].add(where)
            retrieved_docs = {r["id"].split(":")[0] for r in s.get("retrieved", [])}
            for field in TEXT_FIELDS:
                value = s.get(field)
                for text in (value if isinstance(value, list) else [value] if value else []):
                    check_text(where + f" [{field}]", text, retrieved_docs, articles, problems, ok)

    gaps = ROOT / "reports" / "gaps.md"
    if gaps.is_file():
        for i, block in enumerate(gaps.read_text(encoding="utf-8").split("\n## ")[1:], 1):
            check_text(f"gaps.md القسم {i}", block, set(articles), articles, problems, ok)

    print(f"## استشهادات بمعرّف (cited / global_example_id) مش موجودة بالقاعدة: {len(bad_ids)}")
    for where, cid in bad_ids:
        print(f"- {where}: {cid}")
    print(f"\n## مواد مذكورة بالنص ومش موجودة: {len(problems)} (تحققنا من {len(ok)} ذكر)")
    for where, ref, why in problems:
        print(f"- {where}: «{ref}» {why}")
    print(f"\n## استشهادات على نص ثانوي (text_source: secondary): {len(secondary)} مقطع")
    for cid, wheres in sorted(secondary.items()):
        print(f"- {cid}: {len(wheres)} خطوة")


if __name__ == "__main__":
    main()
