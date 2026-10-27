---
name: kb-eval
description: Run the 30-question knowledge-base retrieval benchmark (recall@5), log the result to eval/results.jsonl, and analyse the misses. Use when the user runs /kb-eval or asks how good retrieval is now.
disable-model-invocation: true
argument-hint: "[note describing what changed since the last run]"
---

# /kb-eval — مقياس جودة الاسترجاع

بيقيس كم مرة بيجيب الاسترجاع المادة الصحيحة ضمن أول 5 نتائج. هاد هو الرقم اللي
بيدخل التقرير تحت معيار "جودة قاعدة المعرفة".

## الخطوات

1. شغّل من جذر المشروع:

   ```bash
   python .claude/skills/kb-eval/scripts/kb_eval.py --note "$ARGUMENTS"
   ```

   الخيارات: `--retriever module:function` (الافتراضي `muyassar.retrieval:search`)،
   `-k` (الافتراضي 5)، `--questions`، `--results`.

2. اعرض الرقم والفرق عن آخر تشغيل كما طبعه السكربت.

3. حلّل الأسئلة اللي فشلت، وصنّف كل وحدة بسبب واحد:
   - **ما انضافت**: الوثيقة أو المادة مش موجودة في `kb/` أصلًا.
   - **تقطيع**: المادة موجودة بس مقسومة على chunks بطريقة بتضيّع المعنى.
   - **بيانات وصفية**: الـ chunk الصحيح رجع بس `doc_name` أو `article` مكتوبين بشكل مختلف عن المتوقع.
   - **لغة**: السؤال بالعامية والنص بالفصحى، أو العكس.
   - **ترتيب**: الصحيح رجع بس بعد المركز 5.

   افحص `kb/` بنفسك قبل ما تحكم على السبب، وما تخمّن.

4. اقترح أهم تعديل واحد أو اثنين بيرفعوا الرقم. ما تعدّل إشي إلا إذا طلب المستخدم.

## قواعد

- ما تعدّل `eval/questions.jsonl` عشان يطلع الرقم أحسن. إذا شكّيت إنه السؤال نفسه غلط، قول هيك للمستخدم.
- `eval/results.jsonl` بيتكتب من السكربت بس، وكل تشغيل بيضيف سطر جديد.
- إذا المسترجع لسا مش موجود، السكربت بيوقف برسالة واضحة. وقتها احكي للمستخدم شو الدالة المطلوبة:
  `search(query: str, k: int) -> list[chunk]`.

## صيغة سطر السؤال

```json
{"id": "q01", "question": "...", "expected_doc": "...", "expected_article": "..."}
```

`expected_doc` و`expected_article` لازم يطابقوا `doc_name` و`article` في بيانات الـ chunk.
الأرقام العربية والإنجليزية بتتعامل كأنها نفس الشي.
