# Muyassar (ميسّر)

ميسّر نظام وكلاء ذكاء اصطناعي بساعد المواطن بالأردن بمعاملاته الحكومية، وكل جواب فيه مربوط بنص قانون أو سياسة أو دليل خدمة منشور، مع رقم المادة والرابط. هذا المستودع فيه قاعدة المعرفة والاسترجاع، وصفحة تجريبية بتسأل وبتجاوب مع المصادر.

Muyassar is a multi-agent assistant for Jordanian government services, built for the ITU AI for Good hackathon. Every answer is grounded in a published Jordanian law, policy or service guide and cites the article it relies on. This repository holds the knowledge base, the retrieval pipeline, the benchmark and a demo page.

## Knowledge base

13 documents, 286 chunks, in three layers. Every chunk carries `doc_name`, `article`, `entity`, `date` and `url` (enforced by a hook on `kb/`).

| Layer | Document | Units | Text source |
|---|---|---|---|
| Law | Personal Data Protection Law No. 24 of 2023 | 25 articles | secondary (jordan-lawyer.com), checked against MoDEE's official English translation |
| Law | Rights of Persons with Disabilities Law No. 20 of 2017 | 52 articles | official PDF (portal.jordan.gov.jo) |
| Law | Electronic Transactions Law No. 15 of 2015 | 29 articles | secondary, checked article by article against MoDEE's PDF |
| Policy | Jordan AI Strategy and Implementation Plan 2023–2027 | 18 sections | official PDF (MoDEE) |
| Policy | National AI Code of Ethics 2022 | 16 sections | official PDF (MoDEE) |
| Policy | Digital Transformation Strategic Direction 2021–2025 | 14 sections | official PDF in English, Arabic translation ours |
| Procedure | Disability ID card instructions 2025 (Gazette 6017) | 10 articles | HCD website (Qistas copy) |
| Procedure | Passport renewal guide (office and online) | 7 sections | CSPD website |
| Procedure | Birth registration guide | 6 sections | CSPD website |
| Procedure | Smart ID card renewal guide | 3 sections | CSPD website |
| International | EU AI Act, selected articles (5, 6, 13, 14, 26, 27, 50, 86, Annex III) | 9 sections | official text via artificialintelligenceact.eu, Arabic summaries ours |
| International | OECD AI Principles (OECD/LEGAL/0449, 2024) | 11 sections | oecd.ai, Arabic summaries ours |
| International | Estonia's X-Road | 4 sections | RIA, e-Estonia, NIIS |

`sources/registry.json` records, for each document, the official reference, both URLs, where the text came from and what is still unverified. Read its `verification` field before relying on a document.

Laws are chunked at article boundaries, never by word count, so an answer can cite one article. Long articles are split into parts that keep the article number. Documents without articles use `## <id> | <title>` sections in `sources/raw/`.

## Retrieval

Hybrid BM25 (custom Arabic normalisation and light stemming) plus dense `intfloat/multilingual-e5-large` in ChromaDB, fused with reciprocal rank fusion, then the top 20 reranked by `BAAI/bge-reranker-v2-m3`.

## Benchmark

76 questions (`eval/questions.jsonl`), mostly in Jordanian dialect, each with the expected document and article. Every run is appended to `eval/results.jsonl`.

| Mode | recall@5 | recall@1 |
|---|---|---|
| hybrid + reranker | **0.987** (75/76) | **0.868** (66/76) |
| hybrid | 0.908 | 0.658 |

Most recall@1 misses are a neighbouring article or the same rule in another document (for example the EU AI Act's right to explanation ranking above the Jordanian ethics charter). The questions were written by the KB owner and still need review by the team.

## Run it

Python 3.11. Models download into the Hugging Face cache on first use (about 3 GB). A GPU is optional; on a 4 GB card both models run in fp16.

```bash
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY, never commit .env
python -m muyassar.ingest     # sources/raw -> kb/chunks
python .claude/skills/kb-eval/scripts/kb_eval.py -k 5
python -m muyassar.server     # http://localhost:8765
```

`MUYASSAR_RETRIEVAL` picks `rerank` (default), `hybrid`, `bm25` or `dense`. `MUYASSAR_LLM=ollama` switches answers to a local model.

## Layout

```
muyassar/      arabic.py ingest.py pdf_arabic.py retrieval.py llm.py answer.py server.py
sources/       registry.json, raw/ (clean texts), pdf/ (original files)
kb/chunks/     one JSONL per document
eval/          questions.jsonl, results.jsonl
logs/          web.jsonl, append-only audit log of every question
web/           index.html demo page
.claude/       hooks (KB metadata check, audit log protection), kb-eval skill
```

## Known gaps

- The Arabic wording of the PDPL and the Electronic Transactions Law comes from a secondary site and still needs matching against the Official Gazette. A 2025 amendment to the Electronic Transactions Law passed the House; its publication is unconfirmed.
- Disability law: Gazette issue and page not found yet, and article 14/b/1 has a known extraction defect.
- The 2025 disability card instructions have no fee article, and the new classification list is not included.
- Service-guide fees are copied from CSPD as of 27/10/2026 and can change.
