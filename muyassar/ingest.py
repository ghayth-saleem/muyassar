"""Turn the documents listed in sources/registry.json into kb/chunks/<doc_id>.jsonl.

Laws are cut at article boundaries, never by word count: an answer has to
cite one article, so one article must not be spread over several chunks
with other articles mixed in. An article longer than MAX_CHARS is split
into parts on line breaks, and every part keeps the same article number.

Strategies, charters, service guides and foreign texts have no Jordanian
articles. Their registry entry sets "structure": "sections" and the raw file
marks each section with a line "## <id> | <title>"; the id plays the role
of the article number (what an answer cites), the title goes in the header.

    python -m muyassar.ingest            # every document in the registry
    python -m muyassar.ingest pdpl_2023  # just these
"""
import argparse
import json
import re
import sys

from muyassar import ROOT
from muyassar.arabic import clean

SOURCES = ROOT / "sources"
CHUNKS = ROOT / "kb" / "chunks"
MAX_CHARS = 1200

# "المادة 5" / "المادة (5)" / "المادة 5 مكررة" on a line of its own.
ARTICLE = re.compile(r"^المادة\s*\(?\s*(\d+)\s*\)?\s*(مكرر[ةه]?)?\s*[:.-]?\s*$", re.M)
# "## 3.2 | حوكمة البيانات" for documents with "structure": "sections".
SECTION = re.compile(r"^##\s*([^|\n]+?)\s*\|\s*(.+?)\s*$", re.M)

# Registry fields copied onto every chunk. The first five are what the kb/
# hook requires; the rest let an agent say how far to trust the text.
META_FIELDS = ("doc_name", "entity", "date", "url", "layer", "official_ref", "official_url", "text_source")


def split_articles(text: str) -> list[tuple[str, str]]:
    heads = list(ARTICLE.finditer(text))
    if not heads:
        raise ValueError("ما لقيت ولا عنوان «المادة N» في النص")
    out = []
    for head, nxt in zip(heads, heads[1:] + [None]):
        number = head.group(1) + (" مكرر" if head.group(2) else "")
        body = text[head.end(): nxt.start() if nxt else len(text)].strip()
        out.append((number, body))
    numbers = [n for n, _ in out]
    if len(set(numbers)) != len(numbers):
        dupes = sorted({n for n in numbers if numbers.count(n) > 1})
        raise ValueError(f"أرقام مواد مكررة: {dupes}")
    return out


def split_sections(text: str) -> list[tuple[str, str, str]]:
    heads = list(SECTION.finditer(text))
    if not heads:
        raise ValueError("ما لقيت ولا عنوان «## id | title» في النص")
    out = []
    for head, nxt in zip(heads, heads[1:] + [None]):
        body = text[head.end(): nxt.start() if nxt else len(text)].strip()
        out.append((head.group(1), head.group(2), body))
    ids = [i for i, _, _ in out]
    if len(set(ids)) != len(ids):
        raise ValueError(f"معرّفات أقسام مكررة: {sorted({i for i in ids if ids.count(i) > 1})}")
    return out


def split_long(body: str, limit: int = MAX_CHARS) -> list[str]:
    parts, current = [], ""
    for line in body.splitlines():
        if current and len(current) + len(line) + 1 > limit:
            parts.append(current)
            current = ""
        current = f"{current}\n{line}" if current else line
    return parts + [current] if current else parts


def chunk_document(doc_id: str, doc: dict) -> list[dict]:
    text = clean((SOURCES / doc["raw"]).read_text(encoding="utf-8"))
    if doc.get("structure") == "sections":
        units = [(sid, f"{sid}: {title}", body) for sid, title, body in split_sections(text)]
    else:
        units = [(n, f"المادة {n}", body) for n, body in split_articles(text)]
    chunks = []
    for article, label, body in units:
        parts = split_long(body)
        for i, part in enumerate(parts, 1):
            header = f"{doc['short_name']} - {label}"
            if len(parts) > 1:
                header += f" (جزء {i} من {len(parts)})"
            meta = {f: doc[f] for f in META_FIELDS if doc.get(f)}
            meta.update(doc_id=doc_id, article=article, part=i)
            chunks.append({"id": f"{doc_id}:{article}:{i}", "text": f"{header}\n{part}", "metadata": meta})
    return chunks


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("doc_ids", nargs="*")
    args = parser.parse_args()

    registry = json.loads((SOURCES / "registry.json").read_text(encoding="utf-8"))
    unknown = set(args.doc_ids) - registry.keys()
    if unknown:
        sys.exit(f"مش موجودين في السجل: {sorted(unknown)}")

    CHUNKS.mkdir(parents=True, exist_ok=True)
    for doc_id in args.doc_ids or registry:
        chunks = chunk_document(doc_id, registry[doc_id])
        out = CHUNKS / f"{doc_id}.jsonl"
        with out.open("w", encoding="utf-8", newline="\n") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        articles = len({c["metadata"]["article"] for c in chunks})
        unit = "قسم" if registry[doc_id].get("structure") == "sections" else "مادة"
        print(f"{doc_id}: {articles} {unit}، {len(chunks)} chunk → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
