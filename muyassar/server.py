"""Local web server for the Muyassar demo page.

    python -m muyassar.server          # http://localhost:8765

GET  /                              web/index.html
GET  /scenarios                     web/scenarios.html, the scenario timeline
GET  /api/stats                     documents in the knowledge base and the latest benchmark runs
POST /api/ask                       {"question": "..."} → answer with its cited sources
GET  /api/scenarios                 scenarios, each with its latest logged run
POST /api/scenarios/<id>/run        start a live run → {"run_id": ...}
GET  /api/runs/<run_id>             a run's steps so far, polled by the page
POST /api/runs/<run_id>/decide      {"approved": bool, "note": "..."} → the staff decision

Models load once at startup, so the first question isn't slow.
"""
import json
import os
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from muyassar import ROOT
from muyassar.answer import answer
from muyassar.retrieval import search
from muyassar import scenarios

PORT = 8765
WEB = ROOT / "web"
# Runs this server started or loaded from the log, by run_id.
RUNS: dict[str, dict] = {}


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

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        parts = path.strip("/").split("/")
        if path in ("/", "/index.html"):
            self._send(200, (WEB / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path in ("/scenarios", "/scenarios.html"):
            self._send(200, (WEB / "scenarios.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/stats":
            self._json(200, stats())
        elif path == "/api/scenarios":
            out = []
            for s in scenarios.all_scenarios():
                last = scenarios.latest_run(s["id"])
                if last:
                    RUNS.setdefault(last["run_id"], last)
                    last = RUNS[last["run_id"]]
                out.append({**s, "latest": last})
            self._json(200, out)
        elif len(parts) == 3 and parts[:2] == ["api", "runs"] and parts[2] in RUNS:
            self._json(200, RUNS[parts[2]])
        else:
            self._json(404, {"error": "مش موجود"})

    def do_POST(self):
        parts = self.path.split("?")[0].strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "scenarios"] and parts[3] == "run":
            return self._start_run(parts[2])
        if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "decide":
            return self._decide(parts[2])
        if self.path != "/api/ask":
            return self._json(404, {"error": "مش موجود"})
        try:
            question = self._body().get("question", "").strip()
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "طلب غير صالح"})
        if not question or len(question) > 500:
            return self._json(400, {"error": "اكتب سؤال بين حرف و500 حرف"})
        try:
            self._json(200, answer(question))
        except Exception as e:  # shown to the user in the page, so keep it readable
            self._json(500, {"error": f"صار خطأ: {e}"})

    def _start_run(self, scenario_id: str) -> None:
        if scenario_id not in {s["id"] for s in scenarios.all_scenarios()}:
            return self._json(404, {"error": "السيناريو مش موجود"})
        run_id = uuid.uuid4().hex[:8]
        RUNS[run_id] = {"run_id": run_id, "scenario": scenario_id, "status": "running", "steps": []}

        def update(run):
            RUNS[run_id] = {**run, "steps": list(run["steps"])}

        threading.Thread(target=scenarios.run, args=(scenario_id, update, run_id), daemon=True).start()
        self._json(202, {"run_id": run_id})

    def _decide(self, run_id: str) -> None:
        run = RUNS.get(run_id)
        if not run:
            return self._json(404, {"error": "التشغيل مش موجود"})
        if run["status"] != "awaiting_human":
            return self._json(409, {"error": "هالتشغيل مش بانتظار موافقة"})
        try:
            body = self._body()
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"error": "طلب غير صالح"})
        self._json(200, scenarios.decide(run, bool(body.get("approved")), str(body.get("note", ""))[:500]))

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
