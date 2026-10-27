"""The four Muyassar agents and the orchestrator that combines them.

Each agent covers one of the roles the competition asks for:
- procedure (مرشد الإجراءات): tells the citizen what to do. The innovative solution.
- docs_check (وكيل فحص الأوراق): compares an uploaded document with the official record.
- policy (وكيل السياسات): reads the law, says what it allows and where it is silent. The legal advisor.
- entity (وكيل الجهة): speaks for the government body that owns the service. The institutional participant.
The orchestrator (المنسّق) never sees raw events, only what the agents concluded,
and is what makes it multi-agent coordination.

Every agent gets only the information delivered to it, retrieves its own
articles, and returns a structured verdict. Cited ids that were not retrieved
are dropped, and a verdict with no surviving citation is marked unsourced so
the page shows it in red.
"""
from dataclasses import dataclass

from muyassar.llm import ask
from muyassar.retrieval import search

K = 5

COMMON = """قواعد ثابتة:
- اعتمد فقط على النصوص المرفقة وعلى المعلومات التي وصلتك. لا تفترض شيئاً لم يصلك.
- ضع في cited معرّفات النصوص (id) التي بنيت عليها حكمك فقط. إذا لم يدعم أي نص حكمك اترك cited فارغة وقل ذلك في finding.
- steps: من 2 إلى 4 خطوات قصيرة تشرح كيف وصلت للحكم.
- confidence: رقم بين 0 و1 يعبّر عن ثقتك بالحكم بناءً على اكتمال المعلومات ووضوح النص.
- sensitive = true إذا كان حكمك يعني رفض طلب مواطن، أو حفظ بيانات صحية أو حساسة، أو إرسالها لجهة أخرى. هذه قرارات لا تُنفذ بدون موافقة موظف.
- اكتب بالعربية الفصحى البسيطة وبجمل قصيرة."""

AGENT_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "array", "items": {"type": "string"}},
        "finding": {"type": "string"},
        "decision": {"type": "string"},
        "confidence": {"type": "number"},
        "cited": {"type": "array", "items": {"type": "string"}},
        "sensitive": {"type": "boolean"},
        "sensitive_reason": {"type": "string"},
        "gap_title": {"type": "string"},
        "gap": {"type": "string"},
        "international": {"type": "string"},
    },
    "required": ["steps", "finding", "decision", "confidence", "cited", "sensitive",
                 "sensitive_reason", "gap_title", "gap", "international"],
    "additionalProperties": False,
}

NO_GAP = "اترك gap_title وgap وinternational فارغة؛ كشف الفجوات من عمل وكيل السياسات."


@dataclass(frozen=True)
class Agent:
    key: str
    name: str
    role: str
    system: str
    focus: str  # added to the retrieval query so each agent pulls articles for its own job
    sees_question: bool = True  # the case's legal question; the guide and the checker stick to their own job


AGENTS = {
    a.key: a
    for a in [
        Agent(
            "procedure", "مرشد الإجراءات", "يرشد المواطن لخطوات المعاملة",
            f"""أنت «مرشد الإجراءات» في نظام ميسّر. تشرح للمواطن خطوات معاملته الحكومية والأوراق والرسوم والجهة، من أدلة الخدمات والتعليمات المرفقة.
decision: تسمية قصيرة مثل «إرشاد بالخطوات» أو «لا يوجد دليل للخدمة».
{NO_GAP}
{COMMON}""",
            "الخطوات الوثائق المطلوبة الرسوم الجهة",
            sees_question=False,
        ),
        Agent(
            "docs_check", "وكيل فحص الأوراق", "يطابق الوثيقة المرفوعة مع السجل الرسمي",
            f"""أنت «وكيل فحص الأوراق» في نظام ميسّر. تصلك نتيجة مقارنة آلية بين حقول وثيقة رفعها المواطن وسجل الجهة الرسمي.
مهمتك: تفسير نتيجة المقارنة، وتقدير ما إذا كان الفرق خطأ قراءة آلية أو اختلافاً حقيقياً، وما يجب التحقق منه بعد ذلك.
لا تقرر رفض الطلب؛ هذا ليس دورك. decision: «مطابق» أو «غير مطابق - يحتاج تحقق» أو «تعذّر الفحص».
{NO_GAP}
{COMMON}""",
            "صحة الوثيقة السجل الإلكتروني التحقق دقة البيانات",
            sees_question=False,
        ),
        Agent(
            "policy", "وكيل السياسات", "يقرأ القانون ويكشف الفجوات",
            f"""أنت «وكيل السياسات» في نظام ميسّر، المستشار القانوني. تقرأ القوانين والسياسات الأردنية المرفقة وتجيب عن سؤال الحالة: ماذا يسمح النص، ومن المسؤول، وأين يسكت.
- إذا لم يحدد أي نص أردني مرفق الجواب، فهذه فجوة: اكتب gap_title (عنوان قصير) وgap (وصف الفجوة بجملتين أو ثلاث، مع ذكر المواد الأردنية الأقرب).
- international: إذا وجدت في النصوص المرفقة مثالاً عالمياً (قانون الذكاء الاصطناعي الأوروبي، مبادئ OECD، إكس-رود) يعالج النقطة، اذكره برقم المادة أو المبدأ. وإلا اتركه فارغاً.
- لا تخترع فجوة إذا كان النص الأردني واضحاً؛ اترك الحقول فارغة.
decision: تسمية قصيرة مثل «النص يحدد المسؤول» أو «فجوة: لا نص يحدد المسؤول».
{COMMON}""",
            "المسؤولية الموافقة حقوق صاحب البيانات القرار الآلي الإشراف البشري",
        ),
        Agent(
            "entity", "وكيل الجهة", "يمثل الجهة الحكومية صاحبة الخدمة",
            f"""أنت «وكيل الجهة» في نظام ميسّر، تمثل الجهة الحكومية صاحبة الخدمة (مثل دائرة الأحوال المدنية أو المجلس الأعلى لحقوق الأشخاص ذوي الإعاقة).
تصلك تحديثات الجهة ونتائج التحقق من أنظمتها. مهمتك: ما موقف الجهة من الطلب، وما الذي تطلبه، وهل يتعارض مع ما في قاعدة المعرفة المرفقة.
إذا كان التحديث الذي وصلك يختلف عن النصوص المرفقة، قل ذلك صراحة في finding.
decision: تسمية قصيرة مثل «الجهة تطلب استكمال» أو «تحديث يخالف قاعدة المعرفة».
{NO_GAP}
{COMMON}""",
            "الجهة المختصة اللجنة الطلب القرار الاعتراض",
        ),
    ]
}

ORCHESTRATOR_SYSTEM = f"""أنت «المنسّق» في نظام ميسّر. لا ترى الأحداث الخام، بل ترى ما توصل إليه كل وكيل ومصادره.
مهمتك:
1. تجمع أحكام الوكلاء وتكشف أي تعارض بينها (conflicts).
2. تكتب citizen_reply: رد للمواطن بلغة بسيطة وقريبة، يقول له ما الذي يحدث الآن وما الذي عليه فعله، بدون أن تعلن قراراً حساساً لم يوافق عليه موظف.
3. تكتب staff_note: ملاحظة للموظف المختص تلخص الحالة وما ينتظر قراره.
4. decision: تسمية قصيرة للقرار النهائي المقترح.
- cited: معرّفات النصوص من مصادر الوكلاء التي يعتمد عليها ردك فقط.
- sensitive = true إذا كان القرار المقترح رفض طلب أو حفظ أو إرسال بيانات صحية أو حساسة.
{COMMON}"""

ORCHESTRATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "array", "items": {"type": "string"}},
        "conflicts": {"type": "array", "items": {"type": "string"}},
        "citizen_reply": {"type": "string"},
        "staff_note": {"type": "string"},
        "decision": {"type": "string"},
        "confidence": {"type": "number"},
        "cited": {"type": "array", "items": {"type": "string"}},
        "sensitive": {"type": "boolean"},
        "sensitive_reason": {"type": "string"},
    },
    "required": ["steps", "conflicts", "citizen_reply", "staff_note", "decision", "confidence",
                 "cited", "sensitive", "sensitive_reason"],
    "additionalProperties": False,
}


def source(hit: dict) -> dict:
    m = hit["metadata"]
    return {
        "id": hit["id"],
        "doc_name": m["doc_name"],
        "article": m["article"],
        "entity": m.get("entity"),
        "url": m.get("url"),
        "text": hit["text"].split("\n", 1)[-1],
        "score": hit["score"],
    }


def _context(sources: list[dict]) -> str:
    return "\n\n".join(f"[id: {s['id']}] {s['doc_name']} - {s['article']}\n{s['text']}" for s in sources)


def _clamp(x) -> float:
    return round(min(max(float(x), 0.0), 1.0), 2)


def run_agent(key: str, question: str, inbox: list[dict]) -> dict:
    """One agent's verdict on everything delivered to it so far."""
    agent = AGENTS[key]
    received = "\n".join(f"- [{d['label']}] {d['content']}" for d in inbox)
    question = question if agent.sees_question else ""
    query = f"{question} {inbox[-1]['content']} {agent.focus}".strip()
    sources = [source(h) for h in search(query, K)]
    case = f"سؤال الحالة: {question}\n\n" if question else ""
    reply = ask(
        agent.system,
        f"{case}المعلومات التي وصلتك حتى الآن:\n{received}\n\nالنصوص:\n{_context(sources)}",
        max_tokens=6000,
        schema=AGENT_SCHEMA,
    )
    return _verdict(reply, sources)


def run_orchestrator(question: str, verdicts: dict[str, dict]) -> dict:
    """Combine the agents' latest verdicts into one reply."""
    pool = {s["id"]: s for v in verdicts.values() for s in v["sources"]}
    summary = "\n\n".join(
        f"## {AGENTS[k].name}\nالحكم: {v['decision']} (ثقة {v['confidence']})\n{v['finding']}\n"
        f"مصادره: {', '.join(v['cited']) or 'بدون مصدر'}"
        + (f"\nفجوة: {v['gap_title']}: {v['gap']}" if v.get("gap") else "")
        + (f"\nقرار حساس: {v['sensitive_reason']}" if v["sensitive"] else "")
        for k, v in verdicts.items()
    )
    reply = ask(
        ORCHESTRATOR_SYSTEM,
        f"سؤال الحالة: {question}\n\nأحكام الوكلاء:\n{summary}\n\nنصوص مصادرهم:\n{_context(list(pool.values()))}",
        max_tokens=8000,
        schema=ORCHESTRATOR_SCHEMA,
    )
    out = _verdict(reply, list(pool.values()))
    # A sensitive call by any agent stays sensitive: the orchestrator may not
    # quietly drop the need for a human.
    flagged = [AGENTS[k].name for k, v in verdicts.items() if v["sensitive"]]
    if flagged and not out["sensitive"]:
        out["sensitive"] = True
        out["sensitive_reason"] = "وكيل وصف القرار بأنه حساس: " + "، ".join(flagged)
    return out


def _verdict(reply: dict, sources: list[dict]) -> dict:
    known = {s["id"] for s in sources}
    cited = [c for c in reply["cited"] if c in known]
    return {
        **reply,
        "confidence": _clamp(reply["confidence"]),
        "cited": cited,
        "dropped_citations": [c for c in reply["cited"] if c not in known],
        "unsourced": not cited,
        "sources": sources,
    }
