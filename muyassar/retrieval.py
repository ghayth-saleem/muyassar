"""Knowledge-base search: search(query, k) -> list of chunks, best first.

Two retrievers, fused with reciprocal rank fusion:
- BM25 over normalised Arabic tokens. Catches exact legal terms and numbers.
- Dense vectors from multilingual-e5 in ChromaDB (same store as the ITU
  reference code). Catches dialect and paraphrase: "بدي أمسح بياناتي"
  against "محو البيانات".

By default ("rerank") the top 30 fused candidates are then re-scored by a
cross-encoder (bge-reranker-v2-m3), which reads query and article together
instead of comparing two separate vectors. That is what decides rank 1:
on the 30-question set it took recall@1 from 0.733 to 0.933.

The index is rebuilt automatically whenever kb/chunks/*.jsonl changes.
Set MUYASSAR_RETRIEVAL=bm25 to skip the embedding model (fast, no GPU).
"""
import hashlib
import json
import math
import os
from collections import Counter

from muyassar import ROOT
from muyassar.arabic import tokens

# sentence-transformers otherwise imports TensorFlow too, which adds a minute.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

CHUNKS = ROOT / "kb" / "chunks"
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION = "kb_main"
EMBED_MODEL = os.environ.get("MUYASSAR_EMBED_MODEL", "intfloat/multilingual-e5-large")
RERANK_MODEL = os.environ.get("MUYASSAR_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
RRF_K = 60
CANDIDATES = 50
# 30, not 20: with the Civil Status Law in the base, q32's article fused at rank
# 30 and never reached the reranker. 30 brought it back and lost nothing on the
# 84 questions; 40 and 50 lost q37. Median search time 398 -> 596 ms.
RERANK_CANDIDATES = 30


def load_chunks() -> list[dict]:
    chunks = []
    for path in sorted(CHUNKS.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunks.append(json.loads(line))
    return chunks


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = [Counter(d) for d in docs], k1, b
        self.lengths = [len(d) for d in docs]
        self.avg = sum(self.lengths) / max(len(docs), 1)
        df = Counter(t for d in self.docs for t in d)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for doc, length in zip(self.docs, self.lengths):
            s = 0.0
            for t in query:
                tf = doc.get(t)
                if tf:
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.avg))
            out.append(s)
        return out


def _half_on_gpu(model):
    """fp16 on GPU: e5-large and the reranker together need ~4.5 GB in fp32,
    more than a 4 GB laptop card, which then spills to shared memory and
    runs many times slower. fp16 halves that with no change in ranking."""
    if model.device.type == "cuda":
        model.half()
    return model


class Index:
    def __init__(self, chunks: list[dict], fingerprint: str, dense: bool):
        self.chunks = chunks
        self.bm25 = BM25([tokens(c["text"]) for c in chunks])
        self.model = self.collection = None
        if dense:
            self._open_dense(fingerprint)

    def _open_dense(self, fingerprint: str) -> None:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer

        self.model = _half_on_gpu(SentenceTransformer(EMBED_MODEL))
        client = chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))
        name = f"{COLLECTION}_{EMBED_MODEL.split('/')[-1]}"
        try:
            col = client.get_collection(name)
            if (col.metadata or {}).get("fingerprint") != fingerprint:
                client.delete_collection(name)
                col = None
        except Exception:
            col = None
        if col is None:
            col = client.create_collection(name, metadata={"hnsw:space": "cosine", "fingerprint": fingerprint})
            texts = [c["text"] for c in self.chunks]
            vectors = self.model.encode([f"passage: {t}" for t in texts], normalize_embeddings=True, batch_size=16)
            col.add(
                ids=[c["id"] for c in self.chunks],
                documents=texts,
                embeddings=vectors.tolist(),
                metadatas=[{k: v for k, v in c["metadata"].items() if isinstance(v, (str, int, float, bool))} for c in self.chunks],
            )
        self.collection = col

    def bm25_ranking(self, query: str, layer: str | None = None) -> list[int]:
        scores = self.bm25.scores(tokens(query))
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
        if layer:
            ranked = [i for i in ranked if self.chunks[i]["metadata"].get("layer") == layer]
        return [i for i in ranked[:CANDIDATES] if scores[i] > 0]

    def dense_ranking(self, query: str, layer: str | None = None) -> list[int]:
        vector = self.model.encode([f"query: {query}"], normalize_embeddings=True)[0]
        n = min(CANDIDATES, len(self.chunks))
        where = {"layer": layer} if layer else None
        hits = self.collection.query(query_embeddings=[vector.tolist()], n_results=n, where=where, include=[])
        position = {c["id"]: i for i, c in enumerate(self.chunks)}
        return [position[i] for i in hits["ids"][0] if i in position]


_cache: dict = {}


def _fingerprint() -> str:
    h = hashlib.sha1(EMBED_MODEL.encode())
    for path in sorted(CHUNKS.glob("*.jsonl")):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def get_index(mode: str) -> Index:
    key = (_fingerprint(), mode)
    if _cache.get("key") != key:
        chunks = load_chunks()
        if not chunks:
            raise RuntimeError(f"قاعدة المعرفة فاضية: ما في ملفات في {CHUNKS}")
        _cache.update(key=key, index=Index(chunks, key[0], dense=mode != "bm25"))
    return _cache["index"]


def _reranker():
    if "reranker" not in _cache:
        from sentence_transformers import CrossEncoder

        reranker = CrossEncoder(RERANK_MODEL, max_length=512)
        _half_on_gpu(reranker.model)
        _cache["reranker"] = reranker
    return _cache["reranker"]


def search(query: str, k: int = 5, mode: str | None = None, layer: str | None = None) -> list[dict]:
    """Top-k chunks for query. mode: rerank (default), hybrid, bm25 or dense.
    layer limits the search to one knowledge-base layer, e.g. "global"."""
    mode = mode or os.environ.get("MUYASSAR_RETRIEVAL", "rerank")
    index = get_index("hybrid" if mode == "rerank" else mode)
    rankings = []
    if mode in ("hybrid", "rerank", "bm25"):
        rankings.append(index.bm25_ranking(query, layer))
    if mode in ("hybrid", "rerank", "dense"):
        rankings.append(index.dense_ranking(query, layer))

    fused = Counter()
    for ranking in rankings:
        for rank, i in enumerate(ranking):
            fused[i] += 1 / (RRF_K + rank + 1)
    ranked = fused.most_common(RERANK_CANDIDATES if mode == "rerank" else k)

    if mode == "rerank" and ranked:
        pairs = [(query, index.chunks[i]["text"]) for i, _ in ranked]
        scores = _reranker().predict(pairs, batch_size=8)
        ranked = sorted(zip((i for i, _ in ranked), scores), key=lambda x: -x[1])

    return [{**index.chunks[i], "score": round(float(score), 5)} for i, score in ranked[:k]]


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    for hit in search(" ".join(sys.argv[1:]) or "متى لازم يبلغوني إذا تسربت بياناتي"):
        m = hit["metadata"]
        print(f"{hit['score']:.4f}  {m['doc_name']} / المادة {m['article']}  ({hit['id']})")
