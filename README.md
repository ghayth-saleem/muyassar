# Muyassar (ميسّر)

ميسّر نظام وكلاء ذكاء اصطناعي بساعد المواطن بالأردن بمعاملاته الحكومية، وكل جواب فيه مربوط بنص قانون أو سياسة أو دليل خدمة منشور، مع رقم المادة والرابط. هذا المستودع فيه قاعدة المعرفة والاسترجاع، وصفحة تجريبية بتسأل وبتجاوب مع المصادر.

Muyassar is a multi-agent assistant for Jordanian government services, built for the ITU AI for Good hackathon. Every answer is grounded in a published Jordanian law, policy or service guide and cites the article it relies on. This repository holds the knowledge base, the retrieval pipeline, the benchmark and a demo page.

## Knowledge base

16 documents, 375 chunks, in three layers. Every chunk carries `doc_name`, `article`, `entity`, `date` and `url` (enforced by a hook on `kb/`).

| Layer | Document | Units | Text source |
|---|---|---|---|
| Law | Personal Data Protection Law No. 24 of 2023 | 25 articles | secondary (jordan-lawyer.com), checked against MoDEE's official English translation |
| Law | Rights of Persons with Disabilities Law No. 20 of 2017 | 52 articles | official PDF (portal.jordan.gov.jo) |
| Law | Electronic Transactions Law No. 15 of 2015 | 29 articles | secondary, checked article by article against MoDEE's PDF |
| Law | Civil Status Law No. 9 of 2001, as amended | 62 articles | secondary (jordan-lawyer.com, amendments to 2023), checked against the CSPD consolidated PDF (to 2015); arts 4, 30, 32 differ |
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

Hybrid BM25 (custom Arabic normalisation and light stemming) plus dense `intfloat/multilingual-e5-large` in ChromaDB, fused with reciprocal rank fusion, then the top 30 reranked by `BAAI/bge-reranker-v2-m3` (30 rather than 20 since the Civil Status Law was added: it recovered q32 and cost about 200 ms per search, median 398 to 596 ms on the dev laptop).

## Benchmark

87 questions (`eval/questions.jsonl`), mostly in Jordanian dialect, each with the expected document and article. Every run is appended to `eval/results.jsonl`.

| Mode | recall@5 | recall@1 |
|---|---|---|
| hybrid + reranker (window 30) | **0.977** (85/87) | **0.839** (73/87) |
| hybrid (76 questions, before the global layer) | 0.908 | 0.658 |

Of the three disability-law questions added last, q85 (a screen-reader complaint in dialect) misses the top 5 because its words share little with art. 32, and q86 ranks third behind art. 2, which defines the accessible formats it asks about. Adding the Civil Status Law pushed q32 (ETL art. 6) out of the top 5 until the rerank window was widened to 30, and took rank 1 on q67 with its art. 14, which states the same rule as the birth-registration guide the question expects. Most recall@1 misses are a neighbouring article or the same rule in another document (for example the EU AI Act's right to explanation ranking above the Jordanian ethics charter). The questions were written by the KB owner and still need review by the team.

## Agents and scenarios

All personal data in the scenarios and in the voice test recording is fictitious, written for testing: names, ages, diagnoses, medication, ID numbers and registry records.

An orchestrator and four agents, one per role the competition asks for (`muyassar/agents.py`):

| Agent | Role | Sees |
|---|---|---|
| مرشد الإجراءات (procedure) | guides the citizen through the service | the citizen's request only |
| وكيل فحص الأوراق (docs_check) | compares an uploaded document with the official record | the field-by-field comparison |
| وكيل السياسات (policy) | legal advisor: what the law allows, who is responsible, where it is silent | the case question and what reaches it |
| وكيل الجهة (entity) | speaks for the government body that owns the service | the body's updates and verification results |
| المنسّق (orchestrator) | combines the verdicts, flags conflicts, writes the citizen reply and the staff note | the agents' verdicts, never raw events |

Each agent retrieves its own articles (the policy agent also always gets 3 global-layer articles, and every gap must name one of them as its global example or it is shown in red) and returns steps, a finding, a decision, a confidence, its citations and whether the decision is sensitive. Citations that were not retrieved are dropped; a verdict left with none is marked unsourced and shown in red. A sensitive final decision (rejecting a request, keeping or sending health data) stops the run until a staff member approves or rejects it, and that decision is logged too. One stop is a rule in code, not left to the model: when the entity agent points to a retrieved published guide that its agency's update contradicts, the final decision is sensitive, and the step records `sensitive_by: rule`.

Three failure scenarios in `scenarios/*.json`, each an ordered list of events with a simulated time and the one agent it reaches:

1. **وثيقة مشكوك فيها:** the uploaded ID's expiry date does not match the civil registry. Expected gap: no rule on who answers for an automated verification error.
2. **بيانات صحية في طلب بطاقة الإعاقة:** the voice assistant hears a diagnosis and medication; the father says «ماشي». Expected gap: when is spoken consent to health-data processing legally enough.
3. **تغيّر الإجراء فجأة:** the passport office changes the documents for minors before the knowledge base is updated (a hypothetical event, labelled as such). Expected gap: no deadline for updating digital service information.

`python -m muyassar.scenarios <id>` runs one from the terminal; `/scenarios` on the demo server shows the timeline, every step clickable, with the staff approval step. Every step is a line in `logs/scenarios.jsonl`. `python -m muyassar.gaps` writes `reports/gaps.md` from the latest run of each scenario, in the policy agent's own words. `python scripts/consistency.py` runs each scenario 5 times into `logs/consistency/` and writes `eval/consistency.md`; `python scripts/check_citations.py` checks every cited article exists in the knowledge base and lists citations resting on secondary text. Sampling temperature cannot be fixed on Claude Sonnet 5.5, so stability is measured instead.

## Identity

The mark is the square-kufic meem of «ميسّر», drawn as SVG on a 32-unit grid (`web/brand/`). One identity colour, ink teal `#0e5e6f` (`#6cc3d1` in dark mode); red, amber and green each keep one meaning (no source, sensitive decision, approved), and every state also has a word. Noto Kufi Arabic for headings, IBM Plex Sans Arabic for reading. All tokens live in `web/site.css`; `/brand` on the demo server is the brand sheet, with the three directions considered, the mark at real sizes and the contrast of every colour pair. A demo strip on every page says the site is a test prototype with fictitious data.

## Model providers, replay and tests

Every model call goes through one interface (`muyassar/providers.py`); `MUYASSAR_LLM` in `.env` picks `anthropic` (default), `gemini` (written against the google-genai SDK docs, not yet run against the API; needs `pip install google-genai` and `GEMINI_API_KEY`) or `ollama`.

**Replay mode:** the scenarios page replays any logged run step by step, as it looked live, with a banner saying it is a replay and no model call; a replay never logs a staff decision. `/scenarios?replay=<run_id>#<scenario>` starts one on load (used for the demo video). Without a model key the page disables live runs and offers replay only.

**Tests:** `cd tests && python -m unittest` runs 25 tests with no network, no API and no models: the scenario engine end to end on a `ReplayProvider` (the replies a model once gave, from `tests/fixtures/`) with search stubbed to the logged articles, the citation rule, the global-example rule, the conflict rule, and `scripts/check_citations.py`.

## Voice assistant

`muyassar/voice.py` transcribes Arabic speech locally with faster-whisper `large-v3-turbo` (int8). On the scenarios page, the health-data scenario has a record button (MediaRecorder) and an audio upload; `POST /api/voice` returns the transcript and a `voice_id`, and running the scenario with it replaces the father's request with what was heard. The audio is decoded in memory and never written or logged; only the text is kept, and every step that acted on it records `input_source: voice`.

It runs on the CPU by default. On a 4 GB RTX 3050 the retrieval models already hold 3.2–3.8 GB, and next to them Whisper took 17–22 s for a 13.9 s clip; on the CPU it took 14.6 s, alone on the GPU 1.3 s (`large-v3`: 2.8 s). A real 12.1 s recording in Jordanian dialect took 9.0 s on the CPU once the model was loaded (18 s on the first request). Whisper misspelled a few dialect words in it («تعرفية» for «تعريفية», «لابن» for «لابني», «السن الماضي» for «السنة الماضية»); the policy agent still found the spoken-consent gap. `MUYASSAR_WHISPER_DEVICE=cuda` uses the GPU where there is room. The model downloads into `models/whisper/` (git-ignored) on first use.

## ITU AI Readiness 2.0 mapping

From *AI Ready – Analysis Towards a Standardized Readiness Framework, Report 2.0* (ITU, January 2026): six factors (Data, Research, Deployment Support, Standards, Open source and Code, Sandbox Environments) and thirteen dimensions derived from the Plugfest projects. Muyassar touches D1 Data/model Marketplace, D4 Contextualization and Regional Impact (Jordanian dialect, Jordanian law), D5 Level of Integration of AI in Workflows, D6 Human Interface, D8 Collaboration with AI, D9 Impacts of Humans in AI Integration (staff approval), D10 AI & Policies (gap detection), D11 AI for Inclusion (voice, disability services) and D13 Digital Infrastructure. The report states the factor for every dimension except D9 and D11; the technical report draft gives the node-by-node table.

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
muyassar/      arabic.py ingest.py pdf_arabic.py retrieval.py llm.py providers.py answer.py
               agents.py scenarios.py gaps.py voice.py server.py
tests/         offline unit tests and logged-run fixtures
docs/          video-script.md
scripts/       consistency.py check_citations.py
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
- Disability law: Gazette issue and page not found yet. Article 14/b was corrected from the HCD's official copy (read from the page image: its font has no text layer); the other articles have not been compared with that copy.
- The 2025 disability card instructions have no fee article, and the new classification list is not included.
- Service-guide fees are copied from CSPD as of 27/10/2026 and can change.
