"""Knowledge-base retrieval benchmark: recall@k over eval/questions.jsonl.

Each question line:
  {"id": "q01", "question": "...", "expected_doc": "...", "expected_article": "..."}

A question counts as a hit when one of the top-k retrieved chunks has the
same doc_name and article as expected (digits normalised, so ١٥ == 15).

The retriever is any function search(query: str, k: int) -> list[chunk],
where a chunk carries doc_name/article either at top level or under
"metadata" (same shape the kb/ metadata hook enforces).

Every run is appended to eval/results.jsonl so runs can be compared.
"""
import argparse
import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def norm(value) -> str:
    return " ".join(str(value or "").translate(ARABIC_DIGITS).split()).casefold()


def meta(chunk) -> dict:
    if isinstance(chunk, dict) and isinstance(chunk.get("metadata"), dict):
        return chunk["metadata"]
    return chunk if isinstance(chunk, dict) else {}


def load_retriever(spec: str):
    module_name, _, func_name = spec.partition(":")
    sys.path.insert(0, str(Path.cwd()))
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        sys.exit(f"ما قدرت أستورد المسترجع '{module_name}': {e}")
    func = getattr(module, func_name or "search", None)
    if not callable(func):
        sys.exit(f"'{spec}' مش دالة. لازم يكون search(query, k) -> list")
    return func


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="eval/questions.jsonl")
    parser.add_argument("--results", default="eval/results.jsonl")
    parser.add_argument("--retriever", default="muyassar.retrieval:search")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    qpath = Path(args.questions)
    if not qpath.is_file():
        sys.exit(f"ملف الأسئلة مش موجود: {qpath}")
    questions = [
        json.loads(line) for line in qpath.read_text(encoding="utf-8-sig").splitlines() if line.strip()
    ]
    if not questions:
        sys.exit(f"ملف الأسئلة فاضي: {qpath}")

    search = load_retriever(args.retriever)
    misses = []
    for q in questions:
        results = search(q["question"], args.k)[: args.k]
        want = (norm(q["expected_doc"]), norm(q["expected_article"]))
        got = [(norm(meta(c).get("doc_name")), norm(meta(c).get("article"))) for c in results]
        if want not in got:
            misses.append({
                "id": q.get("id"),
                "question": q["question"],
                "expected": f'{q["expected_doc"]} / {q["expected_article"]}',
                "top": [f"{meta(c).get('doc_name')} / {meta(c).get('article')}" for c in results[:3]],
            })

    total = len(questions)
    hits = total - len(misses)
    recall = round(hits / total, 3)
    run = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": git_commit(),
        "k": args.k,
        "questions": total,
        "hits": hits,
        f"recall@{args.k}": recall,
        "missed_ids": [m["id"] for m in misses],
        "note": args.note,
    }

    rpath = Path(args.results)
    previous = None
    if rpath.is_file():
        lines = [l for l in rpath.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            previous = json.loads(lines[-1])
    rpath.parent.mkdir(parents=True, exist_ok=True)
    with rpath.open("a", encoding="utf-8") as f:
        f.write(json.dumps(run, ensure_ascii=False) + "\n")

    print(f"recall@{args.k} = {recall}  ({hits}/{total})")
    if previous and f"recall@{args.k}" in previous:
        delta = recall - previous[f"recall@{args.k}"]
        print(f"مقارنة بآخر تشغيل ({previous['timestamp']}): {delta:+.3f}")
    if total < 30:
        print(f"تنبيه: {total} سؤال بس، الخطة بتطلب 30.")
    for m in misses:
        print(f"\n✗ {m['id']}: {m['question']}\n  المتوقع: {m['expected']}\n  أول 3: {m['top']}")


if __name__ == "__main__":
    main()
