"""Local web server for the Muyassar demo page.

    python -m muyassar.server          # http://localhost:8765

GET  /            web/index.html
GET  /api/stats   documents in the knowledge base and the latest benchmark runs
POST /api/ask     {"question": "..."} → answer with its cited sources

Models load once at startup, so the first question isn't slow.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from muyassar import ROOT
from muyassar.answer import answer
from muyassar.retrieval import search

PORT = 8765
WEB = ROOT / "web"


def stats() -> dict:
    registry = json.loads((ROOT / "sources" / "registry.json").read_text(encoding="utf-8"))
    chunks = {p.stem: sum(1 for _ in p.open(encoding="utf-8")) for p in (ROOT / "kb" / "chunks").glob("*.jsonl")}
    docs = [
        {
            "doc_name": d["doc_name"],
            "entity": d["entity"],
            "layer": d["layer"],
            "text_source": d["text_source"],
            "official_ref": d.get("official_ref"),
            "url": d["url"],
            "chunks": chunks.get(doc_id, 0),
        }
        for doc_id, d in registry.items()
    ]
    runs = []
    results = ROOT / "eval" / "results.jsonl"
    if results.is_file():
        runs = [json.loads(l) for l in results.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Latest run per k for the retrieval mode this server answers with (the
    # run's note starts with the mode), so the page shows recall@1 and recall@5
    # side by side and never a comparison run of another mode.
    mode = os.environ.get("MUYASSAR_RETRIEVAL", "rerank")
    latest = {}
    for run in runs:
        if run.get("note", "").startswith(mode):
            latest[run["k"]] = run
    return {"documents": docs, "benchmark": [latest[k] for k in sorted(latest)]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/stats":
            self._json(200, stats())
        else:
            self._json(404, {"error": "مش موجود"})

    def do_POST(self):
        if self.path != "/api/ask":
            return self._json(404, {"error": "مش موجود"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            question = json.loads(self.rfile.read(length) or b"{}").get("question", "").strip()
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "طلب غير صالح"})
        if not question or len(question) > 500:
            return self._json(400, {"error": "اكتب سؤال بين حرف و500 حرف"})
        try:
            self._json(200, answer(question))
        except Exception as e:  # shown to the user in the page, so keep it readable
            self._json(500, {"error": f"صار خطأ: {e}"})

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.address_string()} {fmt % args}\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    print("بحمّل النماذج...")
    search("تحميل", 1)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"ميسّر شغّال على http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
