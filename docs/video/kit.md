# عدّة فيديو «ميسّر، نشمي بجيبك»

فيديو مدته حوالي 75 ثانية لعرض الفكرة بالهاكاثون، مش للنشر. الشخصية مولّدة بالذكاء الاصطناعي.

الخطة الكاملة والأسباب في `docs/video-nashmi.md`. هون كل إشي جاهز للنسخ: الصور، والوصف لكل لقطة، والسكربت.

## الصور

| الملف | شو فيه | لأي لقطة |
|---|---|---|
| `keyframe-desk.png` | ميسّر قاعد على المكتب والتليفون بإيديه، بيضحك للكاميرا | إطار البداية للقطات 1 و2 و3 و5 |
| `keyframe-phone.png` | من ورا كتفه، التليفون بنص الكادر وشاشته بيضا | إطار النهاية للقطة 3، والخلفية للقطة 4 |
| `phone-doubtful-id.mp4` | تسجيل حقيقي لشاشة الموقع، 20 ثانية | اللقطة 4 |
| `endcard.png` | شاشة النهاية | اللقطة 6 |

## الإعدادات بكل اللقطات

- المقاس 16:9، والمدة 8 ثواني (أو 5 بـ Kling)، والدقة 1080p.
- **وصف سلبي (negative prompt)، انسخه لكل لقطة:**

```
text, letters, subtitles, captions, watermark, logo on screen, distorted hands, extra fingers, face change, different person, different scarf pattern, camera shake, cartoon, blurry face
```

- **صوت ولّا بدون صوت:**
  - **بـ Google Flow (Veo):** استعمل نسخة «مع حكي». Veo بيطلّع صوت وحركة شفايف مع بعض. اللهجة الأردنية مش مضمونة، فجرّبها أول إشي على اللقطة 1 لأنها أقصر جملة.
  - **بـ Kling:** استعمل نسخة «بدون حكي». بعدها بتسجّل الجمل بصوتك، وبتعمل مزامنة شفايف بأداة Lip Sync بـ Kling.

---

## اللقطة 1: التحية (0:00 – 0:07)

إطار البداية: `keyframe-desk.png`

الجملة: **«مرحبا! أنا ميسّر.»**

بدون حكي (Kling):
```
Static wide shot, no camera movement. The man sitting at the wooden desk looks down at the phone in his hands, then raises his head, looks straight into the camera and gives a warm, confident smile and a small nod. Natural office light, shallow depth of field, photorealistic. His face, grey blazer and red-and-white keffiyeh stay exactly the same.
```

مع حكي (Flow / Veo):
```
Static wide shot, no camera movement. The man sitting at the wooden desk looks down at his phone, then raises his head, looks straight into the camera, smiles warmly and says in a friendly Jordanian Arabic accent: "مرحبا! أنا ميسّر." Quiet office ambience, no music. Natural light, photorealistic. His face, grey blazer and red-and-white keffiyeh stay exactly the same.
```

## اللقطة 2: المشكلة (0:07 – 0:20)

إطار البداية: `keyframe-desk.png`. اللقطة طويلة، فاعملها لقطتين كل وحدة 6–8 ثواني، كل وحدة بجملة.

الجملة (2أ): **«بدك تجدد هويتك؟ تطلّع بطاقة إعاقة لابنك؟»**

الجملة (2ب): **«بتلف على عشر صفحات، وآخر إشي ما بتعرف أي قانون بيحكي عنك.»**

بدون حكي:
```
Medium shot, very slow dolly-in toward the man. He talks to the camera in a relaxed, friendly way, one hand holding the phone on the desk and the other hand open, gesturing as he explains, slight head tilt, expressive eyebrows. Natural office light, shallow depth of field, photorealistic. Same face, same grey blazer, same red-and-white keffiyeh.
```

مع حكي (2أ):
```
Medium shot, very slow dolly-in. The man talks to the camera in a friendly Jordanian Arabic accent, gesturing with his open hand: "بدك تجدد هويتك؟ تطلّع بطاقة إعاقة لابنك؟" Quiet office ambience, no music. Photorealistic. Same face, same blazer, same keffiyeh.
```

مع حكي (2ب):
```
Medium shot, very slow dolly-in. The man shakes his head slightly with an understanding smile and says in a Jordanian Arabic accent: "بتلف على عشر صفحات، وآخر إشي ما بتعرف أي قانون بيحكي عنك." Quiet office ambience, no music. Photorealistic. Same face, same blazer, same keffiyeh.
```

## اللقطة 3: «تعال أوريك» (0:20 – 0:28)

إطار البداية: `keyframe-desk.png`. إطار النهاية: `keyframe-phone.png`. Kling وFlow بيقبلوا إطار نهاية بنموذج «start and end frame».

الجملة: **«تعال أوريك.»** هون بيطّلع على التليفون، فما في داعي لمزامنة شفايف. حط الصوت فوق اللقطة بس.

```
Smooth camera move: the camera slowly travels from the front of the desk around to behind the man's right shoulder and pushes in toward the phone he lifts and tilts toward the camera. Ends on an over-the-shoulder close-up of the phone, its screen a plain white glow. Steady, cinematic, no shake, shallow depth of field, photorealistic. Same man, same blazer, same keffiyeh.
```

إذا ما ظبطت الحركة مع إطار النهاية، جرّب أبسط: ابدأ من `keyframe-phone.png` لحالها:
```
Slow push-in toward the phone in the man's hands, over-the-shoulder view, the phone screen stays a plain flat white glow, steady camera, shallow depth of field, photorealistic.
```

## اللقطة 4: الموقع على التليفون (0:28 – 0:55)

ما في توليد هون. **جاهزة: `phone-on-screen.mp4`** (1920×1080، 21 ثانية). التسجيل الحقيقي ملصوق على شاشة التليفون بـ `keyframe-phone.png`، والكاميرا بتقرّب لحد ما الشاشة تعبّي الكادر. أول ثانية ونص الشاشة بيضا، فبتكمل من آخر اللقطة 3 بدون قطع.

إذا بدك تعملها بإيدك بدالها، استعمل `phone-doubtful-id.mp4` (التسجيل لحاله). في طريقتين:
- **أسهل:** قص لصورة سودة أو بلون الخلفية `#f5f7f7`، والتسجيل بالنص بطوله.
- **أحلى:** حط التسجيل فوق شاشة التليفون بـ `keyframe-phone.png`. صغّره ودوّره شوي ليطابق الشاشة البيضا. الشاشة مستقيمة، فما بدها تتبّع.

الجمل فوق التسجيل:
- **«الحكي هون عن وحدة رفعت هويتها، وتاريخ الانتهاء مش زي السجل.»**
- **«كل وكيل بيحكي رأيه، وبيقلّك من أي مادة بالقانون.»**
- **«والقرار الحساس، زي رفض طلبك، ما بقرره لحالي: بوقّف وبحوّله لموظف.»**

## اللقطة 5: الوعد (0:55 – 1:07)

إطار البداية: `keyframe-desk.png`

الجملة: **«كل كلمة إلها مصدر. واللي ما إله مصدر، بيطلع قدامك أحمر.»**

بدون حكي:
```
Medium shot, static camera. The man puts the phone down on the desk, leans slightly forward, looks into the camera with a sincere, reassuring smile and talks calmly, then ends with a small confident nod. Natural office light, photorealistic. Same face, same blazer, same keffiyeh.
```

مع حكي:
```
Medium shot, static camera. The man puts the phone down on the desk, leans slightly forward and says calmly in a Jordanian Arabic accent, with a reassuring smile: "كل كلمة إلها مصدر. واللي ما إله مصدر، بيطلع قدامك أحمر." Ends with a small nod. Quiet office ambience, no music. Photorealistic.
```

## اللقطة 6: النهاية (1:07 – 1:15)

`endcard.png` لمدة 8 ثواني، موسيقى بس.

---

## السكربت كامل (للتسجيل بصوتك)

اقرأه بهدوء وبابتسامة، كأنك بتحكي مع جارك. الأرقام بين القوسين وقت تقريبي.

> **(0:00)** مرحبا! أنا ميسّر.
>
> **(0:07)** بدك تجدد هويتك؟ تطلّع بطاقة إعاقة لابنك؟
> بتلف على عشر صفحات، وآخر إشي ما بتعرف أي قانون بيحكي عنك.
>
> **(0:20)** تعال أوريك.
>
> **(0:28)** الحكي هون عن وحدة رفعت هويتها، وتاريخ الانتهاء مش زي السجل.
> كل وكيل بيحكي رأيه، وبيقلّك من أي مادة بالقانون.
> والقرار الحساس، زي رفض طلبك، ما بقرره لحالي: بوقّف وبحوّله لموظف.
>
> **(0:55)** كل كلمة إلها مصدر. واللي ما إله مصدر، بيطلع قدامك أحمر.
>
> **(1:07)** (موسيقى) ميسّر، نشمي بجيبك.

## المونتاج (CapCut أو DaVinci Resolve)

1. رتّب اللقطات: 1، 2أ، 2ب، 3. خلّي آخر إطار من 3 ثابت نص ثانية.
2. اللقطة 4 بالتسجيل، والصوت فوقها.
3. اللقطة 5، بعدين `endcard.png`.
4. ترجمة عربية لكل جملة، بخط واضح أبيض على شريط غامق.
5. الشاشة اللي ورا ميسّر باللقطات 1 و2 و5 فاضية: إذا بدك حط عليها اللوجو `web/brand/logo-keffiyeh.png`.
6. موسيقى هادية واطية تحت الحكي، وأعلى شوي بشاشة النهاية.

**قبل العرض، تأكد من شغلتين:**
- إنه وجه الشخصية والكوفية ما تغيّروا بين اللقطات.
- إنه جملة «نموذج تجريبي… الشخصية مولّدة بالذكاء الاصطناعي» مبيّنة بالآخر.
