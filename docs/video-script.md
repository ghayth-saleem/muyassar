# Muyassar – demo video script (draft, 7 minutes)

Recorded entirely in **replay mode**: every scenario is a logged run played back step by step from `logs/scenarios.jsonl`, with no model call. The page says so in a banner on every replay; keep it in frame. All personal data shown is fictitious.

Open the server with `python -m muyassar.server`, then use the replay links below. A link like `/scenarios?replay=<run_id>#<scenario>` starts the replay on load.

| Part | Time | Competition section |
|---|---|---|
| 1. The problem and the setup | 0:00–1:00 | Setup |
| 2. What the system does | 1:00–2:15 | Functions |
| 3. Scenario 1, doubtful document | 2:15–3:45 | Expected / actual |
| 4. Scenario 2, health data by voice | 3:45–5:15 | Expected / actual |
| 5. Scenario 3, procedure changed | 5:15–6:30 | Expected / actual |
| 6. Results and limits | 6:30–7:00 | Actual result |

---

## 1. The problem and the setup (0:00–1:00)

**On screen:** the home page (`/`), then the knowledge-base section scrolled into view.

**Voice-over:**
"A citizen in Jordan who renews an ID, registers a birth or applies for a disability card learns the steps from scattered pages, and rarely knows which law governs a decision about them. Muyassar is a multi-agent assistant that answers in plain Arabic, including Jordanian dialect, and ties every statement to the article it comes from.

It runs on a laptop: sixteen documents in three layers. Jordanian laws and policies, the service guides of the Civil Status Department and the Higher Council for the Rights of Persons with Disabilities, and a global layer with the GDPR, the EU AI Act, the EU Single Digital Gateway Regulation, the OECD principles and Estonia's X-Road. Search is hybrid, BM25 plus multilingual vectors with a reranker, and on 87 questions with known answers the right article is in the top five 97.7 percent of the time (85 of 87)."

**On screen at the end:** the benchmark numbers on the home page.

## 2. What the system does (1:00–2:15)

**On screen:** the scenarios page (`/scenarios`), the three scenario cards, then the legend (red = no source, amber = sensitive decision, green = tied to an article).

**Voice-over:**
"Four agents and an orchestrator cover the roles the competition asks for. The procedure guide tells the citizen what to do. The document checker compares an uploaded document with the official record. The policy agent is the legal adviser: it says what the law allows, who is responsible, and where the law is silent. The entity agent speaks for the government body. The orchestrator never sees the raw events, only what the agents concluded.

Three rules are enforced in code, not left to the model. A verdict that cites no article the agent actually retrieved is shown in red. A gap must be compared with a global article the policy agent retrieved, or it is red too. And a sensitive decision, rejecting a request or keeping health data, stops the run until a staff member approves it. Every step is one line in an append-only audit log."

**On screen:** click any card to show the detail panel: what the agent received, its steps, its decision and confidence, the articles it retrieved with the cited ones marked.

## 3. Scenario 1 – doubtful document (2:15–3:45)

**Replay:** `/scenarios?replay=15fb1470#doubtful_id`

**Expected (say before the replay):**
"A citizen uploads her ID. The expiry date read by the machine does not match the civil registry. Two minutes later the registry's own check proposes rejecting the request automatically. The question: who decides the rejection, what is she told, and who answers for an automated error? We expect a gap: no Jordanian text assigns responsibility for an automated verification error."

**Actual (narrate as the steps appear):**
- The document checker flags the mismatch. In this logged run it is **red**: it gave its finding without citing an article. That is the citation rule working, and it is why the checker now always retrieves the service guide (point out the red card; mention that later runs cite the ID guide and the Civil Status Law, art. 9).
- The entity agent passes on the proposed automatic rejection and marks it sensitive.
- The policy agent reports the gap: no Jordanian text on automated rejection or on responsibility for a verification error, compared with **GDPR art. 22** (the right not to be subject to a decision based solely on automated processing).
- The orchestrator suspends the rejection and refers the case to staff; the run stops at «النظام وقف هون».

[TODO: when the API key is back, record a fresh doubtful_id run on the main log so the replay shows the document checker citing its sources, and replace the run id above.]

## 4. Scenario 2 – health data by voice (3:45–5:15)

**Replay:** `/scenarios?replay=c6fe953b#health_data`

**Expected:**
"A father applies for his son's disability card by voice and mentions a diagnosis and daily medication. Asked whether to keep the details, he says «ماشي», okay. The Council then asks for all medical details and a copy kept for later requests. We expect a gap on whether spoken consent to health-data processing is legally enough."

**Actual:**
- Show the first card: the request is tagged **من صوت**. It was a recorded request, transcribed locally with Whisper; the audio was never stored, only the text, marked `source: voice`.
- The policy agent reports the gap, spoken consent and sending a minor's health data, citing PDPL art. 5 (documented consent), and compares it with **GDPR art. 9** (health data needs explicit consent for a specified purpose).
- The orchestrator stops storage and sending until documented consent or a staff decision.

**Mention:** Whisper misspelled three dialect words in the recording; the result did not change.

## 5. Scenario 3 – procedure changed suddenly (5:15–6:30)

**Replay:** `/scenarios?replay=bba8c8ab#procedure_change`

**Expected:**
"The passport office changes the documents for minors (a hypothetical event for the test). The update reaches the entity agent before the knowledge base is updated, and a minute later a citizen asks. What does Muyassar say in between? We expect a gap: no deadline for updating digital service information."

**Actual:**
- The entity agent flags that the update contradicts the published guide's e-service conditions.
- The procedure guide, which only sees the citizen's question, answers from the published guide: online renewal is allowed. The two agents disagree, which is the point.
- The policy agent reports the gap and compares it with the **EU Single Digital Gateway Regulation, art. 9**: information must be kept up to date and dated, but no deadline is set. We found no official source that sets one.
- The final card is amber with the tag **قرار حساس بقاعدة التعارض**: the stop was made by the conflict rule in code, not by the model.

## 6. Results and limits (6:30–7:00)

**On screen:** `eval/consistency.md` (or its table in the report), then the replay banner.

**Voice-over:**
"Each scenario was run five times. All three found their expected gap at least four times in five, every gap came with a retrieved global example, and after the conflict rule the third scenario stopped for staff approval five times in five.

Limits: the Arabic text of some laws comes from a secondary site and still needs matching against the Official Gazette, the benchmark questions were written by the author, and what you saw is a replay of logged runs. Live runs need a model key."

---

### Before recording

- Check the run ids above still exist: `GET /api/scenarios/<id>/runs`.
- Check the recall@5 value against the latest `eval/results.jsonl` line with `k: 5` (0.977 when this was written).
- Record at 1920×1080; the page is RTL, so the timeline is on the right and the detail panel on the left.
