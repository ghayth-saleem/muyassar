"""Answer a citizen's question from the knowledge base, with its sources.

The model sees only the retrieved articles and must cite them by id; any
id it cites that was not retrieved is dropped, so an answer can never point
at an article the system did not actually read. Every question is appended
to logs/web.jsonl (the audit log the judges see).
"""
import json
import time
from datetime import datetime, timezone

from muyassar import ROOT
from muyassar.llm import CLAUDE_MODEL, PROVIDER, ask
from muyassar.retrieval import search

LOG = ROOT / "logs" / "web.jsonl"
K = 5

SYSTEM = """أنت «ميسّر»، مساعد يشرح للمواطن في الأردن حقوقه وإجراءاته الحكومية.
- جاوب فقط من النصوص القانونية المرفقة. لا تضف معلومة من خارجها.
- اكتب بلغة عربية بسيطة وقريبة، بجمل قصيرة، وخاطب المواطن مباشرة.
- اذكر في الجواب رقم المادة واسم القانون لكل حكم تذكره.
- ضع في cited معرّفات النصوص (id) التي بنيت عليها الجواب فقط.
- إذا النصوص لا تجيب عن السؤال، اجعل covered = false وقل ذلك بوضوح، واقترح الجهة الأقرب إن وردت في النصوص.
- لا تقدم استشارة قانونية شخصية؛ هذا شرح للنص."""

SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "covered": {"type": "boolean"},
        "cited": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "covered", "cited"],
    "additionalProperties": False,
}


def _source(hit: dict) -> dict:
    m = hit["metadata"]
    body = hit["text"].split("\n", 1)[-1]
    return {
        "id": hit["id"],
        "doc_name": m["doc_name"],
        "article": m["article"],
        "entity": m.get("entity"),
        "text": body,
        "url": m.get("url"),
        "official_ref": m.get("official_ref"),
        "text_source": m.get("text_source"),
        "score": hit["score"],
    }


def answer(question: str) -> dict:
    started = time.perf_counter()
    sources = [_source(h) for h in search(question, K)]
    context = "\n\n".join(f"[id: {s['id']}] {s['doc_name']} - المادة {s['article']}\n{s['text']}" for s in sources)
    reply = ask(SYSTEM, f"النصوص:\n{context}\n\nسؤال المواطن: {question}", max_tokens=4000, schema=SCHEMA)

    known = {s["id"] for s in sources}
    cited = [c for c in reply["cited"] if c in known]
    result = {
        "question": question,
        "answer": reply["answer"],
        "covered": reply["covered"],
        "cited": cited,
        "dropped_citations": [c for c in reply["cited"] if c not in known],
        "sources": sources,
        "model": CLAUDE_MODEL if PROVIDER == "anthropic" else PROVIDER,
        "ms": round((time.perf_counter() - started) * 1000),
    }
    _log(result)
    return result


def _log(result: dict) -> None:
    LOG.parent.mkdir(exist_ok=True)
    line = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agent": "web",
        "input": result["question"],
        "retrieved": [f"{s['doc_name']} / {s['article']} ({s['score']})" for s in result["sources"]],
        "decision": "answered" if result["covered"] else "not_covered",
        "cited": result["cited"],
        "dropped_citations": result["dropped_citations"],
        "model": result["model"],
        "ms": result["ms"],
    }
    with LOG.open("a", encoding="utf-8", newline="
") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
