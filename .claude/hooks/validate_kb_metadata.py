"""PostToolUse hook: every knowledge-base chunk must carry its source.

Runs after Claude writes or edits a .json/.jsonl file under kb/. Each chunk
needs non-empty metadata for: doc_name, article, entity, date, url. Without
them an agent's answer cannot cite its source, which is what the
transparency and knowledge-base criteria are judged on.

Accepted chunk shapes (one per line in .jsonl, or a list / single object in .json):
  {"text": "...", "metadata": {"doc_name": ..., "article": ..., ...}}
  {"text": "...", "doc_name": ..., "article": ..., ...}

Exit 2 reports the problems back to Claude so it fixes them.
"""
import json
import re
import sys
from pathlib import Path

REQUIRED = ("doc_name", "article", "entity", "date", "url")
KB_FILE = re.compile(r"(^|[\\/])kb[\\/].+\.jsonl?$", re.IGNORECASE)
MAX_REPORTED = 15


def chunks_from(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".jsonl":
        for n, line in enumerate(text.splitlines(), 1):
            if line.strip():
                yield f"سطر {n}", json.loads(line)
    else:
        data = json.loads(text)
        items = data if isinstance(data, list) else [data]
        for n, item in enumerate(items, 1):
            yield f"عنصر {n}", item


def missing_fields(chunk) -> list[str]:
    if not isinstance(chunk, dict):
        return list(REQUIRED)
    meta = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else chunk
    return [f for f in REQUIRED if not str(meta.get(f, "") or "").strip()]


def main() -> None:
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    path_str = (data.get("tool_input") or {}).get("file_path", "")
    if not KB_FILE.search(path_str):
        return
    path = Path(path_str)
    if not path.is_file():
        return

    problems = []
    try:
        for where, chunk in chunks_from(path):
            missing = missing_fields(chunk)
            if missing:
                problems.append(f"  {where}: ناقص {', '.join(missing)}")
    except json.JSONDecodeError as e:
        problems.append(f"  JSON غير صالح: {e}")

    if problems:
        shown = problems[:MAX_REPORTED]
        if len(problems) > MAX_REPORTED:
            shown.append(f"  ... و{len(problems) - MAX_REPORTED} غيرهم")
        print(
            f"بيانات وصفية ناقصة في {path.name} "
            f"(الحقول المطلوبة: {', '.join(REQUIRED)}):\n" + "\n".join(shown),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
