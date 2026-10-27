# Muyassar (ميسّر)

ميسّر نظام وكلاء ذكاء اصطناعي بساعد المواطن بالأردن بمعاملاته الحكومية، وكل جواب فيه مربوط بنص قانون أو سياسة أو دليل خدمة منشور، مع رقم المادة والرابط. هذا المستودع فيه قاعدة المعرفة والاسترجاع، وصفحة تجريبية بتسأل وبتجاوب مع المصادر.

Muyassar is a multi-agent assistant for Jordanian government services, built for the ITU AI for Good hackathon. Every answer is grounded in a published Jordanian law, policy or service guide and cites the article it relies on. This repository holds the knowledge base, the retrieval pipeline, the benchmark and a demo page.

## Knowledge base

15 documents, 311 chunks, in three layers. Every chunk carries `doc_name`, `article`, `entity`, `date` and `url` (enforced by a hook on `kb/`).

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
| Global (EU) | EU AI Act, selected articles (5, 6, 13, 14, 26, 27, 50, 86, Annex III point 5) | 9 sections | EU Official Journal via the Publications Office (Cellar), Arabic summaries ours |
| Global (EU) | GDPR, articles 7, 9, 22 | 3 sections | EU Official Journal via Cellar, Arabic summaries ours |
| Global (EU) | Single Digital Gateway Regulation 2018/1724, articles 9, 10, 17 | 3 sections | EU Official Journal via Cellar, Arabic summaries ours |
| Global (OECD) | OECD AI Principles (OECD/LEGAL/0449, 2024) | 11 sections | oecd.ai, Arabic summaries ours |
| Global (Estonia) | Estonia's X-Road | 4 sections | RIA, e-Estonia, NIIS |

`sources/registry.json` records, for each document, the official reference, both URLs, where the text came from and what is still unverified. Read its `verification` field before relying on a document.

Laws are chunked at article boundaries, never by word count, so an answer can cite one article. Long articles are split into parts that keep the article number. Documents without articles use `## <id> | <title>` sections in `sources/raw/`.

## Retrieval

Hybrid BM25 (custom Arabic normalisation and light stemming) plus dense `intfloat/multilingual-e5-large` in ChromaDB, fused with reciprocal rank fusion, then the top 20 reranked by `BAAI/bge-reranker-v2-m3`.

## Benchmark

81 questions (`eval/questions.jsonl`), mostly in Jordanian dialect, each with the expected document and article. Every run is appended to `eval/results.jsonl`.

| Mode | recall@5 | recall@1 |
|---|---|---|
| hybrid + reranker | **0.988** (80/81) | **0.864** (70/81) |
| hybrid (76 questions, before the global layer) | 0.908 | 0.658 |

Most recall@1 misses are a neighbouring article or the same rule in another document (for example the EU AI Act's right to explanation ranking above the Jordanian ethics charter). The questions were written by the KB owner and still need review by the team.

## Agents and scenarios

An orchestrator and four agents, one per role the competition asks for (`muyassar/agents.py`):

| Agent | Role | Sees |
|---|---|---|
| مرشد الإجراءات (procedure) | guides the citizen through the service | the citizen's request only |
| وكيل فحص الأوراق (docs_check) | compares an uploaded document with the official record | the field-by-field comparison |
| وكيل السياسات (policy) | legal advisor: what the law allows, who is responsible, where it is silent | the case question and what reaches it |
| وكيل الجهة (entity) | speaks for the government body that owns the service | the body's updates and verification results |
| المنسّق (orchestrator) | combines the verdicts, flags conflicts, writes the citizen reply and the staff note | the agents' verdicts, never raw events |

Each agent retrieves its own articles (the policy agent also always gets 3 global-layer articles, and every gap must name one of them as its global example or it is shown in red) and returns steps, a finding, a decision, a confidence, its citations and whether the decision is sensitive. Citations that were not retrieved are dropped; a verdict left with none is marked unsourced and shown in red. A sensitive final decision (rejecting a request, keeping or sending health data) stops the run until a staff member approves or rejects it, and that decision is logged too.

Three failure scenarios in `scenarios/*.json`, each an ordered list of events with a simulated time and the one agent it reaches:

1. **وثيقة مشكوك فيها:** the uploaded ID's expiry date does not match the civil registry. Expected gap: no rule on who answers for an automated verification error.
2. **بيانات صحية في طلب بطاقة الإعاقة:** the voice assistant hears a diagnosis and medication; the father says «ماشي». Expected gap: when is spoken consent to health-data processing legally enough.
3. **تغيّر الإجراء فجأة:** the passport office changes the documents for minors before the knowledge base is updated (a hypothetical event, labelled as such). Expected gap: no deadline for updating digital service information.

`python -m muyassar.scenarios <id>` runs one from the terminal; `/scenarios` on the demo server shows the timeline, every step clickable, with the staff approval step. Every step is a line in `logs/scenarios.jsonl`. `python -m muyassar.gaps` writes `reports/gaps.md` from the latest run of each scenario, in the policy agent's own words. `python scripts/consistency.py` runs each scenario 5 times into `logs/consistency/` and writes `eval/consistency.md`; `python scripts/check_citations.py` checks every cited article exists in the knowledge base and lists citations resting on secondary text. Sampling temperature cannot be fixed on Claude Sonnet 5.5, so stability is measured instead.

## ITU-T Y.3172 mapping

| Y.3172 component | In Muyassar |
|---|---|
| Source | Jordanian laws, policies and service guides (`sources/`), and citizen requests and agency events (`scenarios/`) |
| Collector | `muyassar/pdf_arabic.py` (Arabic PDF repair) and the source registry `sources/registry.json` |
| Preprocessor | `muyassar/ingest.py`: chunking at article or section boundaries, metadata on every chunk |
| Model | `muyassar/retrieval.py` (BM25 + e5 + reranker) and `muyassar/llm.py` (Claude, or a local model) |
| Policy | the policy agent, the unsourced rule and the human-approval stop for sensitive decisions |
| ML Function Orchestrator | the orchestrator agent and the scenario engine `muyassar/scenarios.py` |
| Sink / Distributor | `muyassar/server.py` and `web/`: the citizen reply, the staff note, the audit logs |
| ML Sandbox | local for now; the ITU cloud environment is not set up yet |

## Run it

Python 3.11. Models download into the Hugging Face cache on first use (about 3 GB). A GPU is optional; on a 4 GB card both models run in fp16.

```bash
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY, never commit .env
python -m muyassar.ingest     # sources/raw -> kb/chunks
python .claude/skills/kb-eval/scripts/kb_eval.py -k 5
python -m muyassar.scenarios doubtful_id   # one scenario in the terminal
python -m muyassar.gaps       # reports/gaps.md
python -m muyassar.server     # http://localhost:8765 and /scenarios
```

`MUYASSAR_RETRIEVAL` picks `rerank` (default), `hybrid`, `bm25` or `dense`. `MUYASSAR_LLM=ollama` switches answers to a local model.

## Layout

```
muyassar/      arabic.py ingest.py pdf_arabic.py retrieval.py llm.py answer.py
               agents.py scenarios.py gaps.py server.py
sources/       registry.json, raw/ (clean texts), pdf/ (original files)
kb/chunks/     one JSONL per document
eval/          questions.jsonl, results.jsonl
scenarios/     the three failure scenarios
reports/       gaps.md, generated
logs/          web.jsonl and scenarios.jsonl, append-only audit logs
web/           index.html (ask), scenarios.html (timeline)
.claude/       hooks (KB metadata check, audit log protection), kb-eval skill
```

## Known gaps

- The Arabic wording of the PDPL and the Electronic Transactions Law comes from a secondary site and still needs matching against the Official Gazette. A 2025 amendment to the Electronic Transactions Law passed the House; its publication is unconfirmed.
- Disability law: Gazette issue and page not found yet, and article 14/b/1 has a known extraction defect.
- The 2025 disability card instructions have no fee article, and the new classification list is not included.
- Service-guide fees are copied from CSPD as of 27/10/2026 and can change.
