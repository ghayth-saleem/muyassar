# «ميسّر، نشمي بجيبك» – character pitch video (draft, about 75 seconds)

A short video to open the hackathon pitch. It is separate from the 7-minute submission video (`docs/video-script.md`).

The character is **ميسّر**, a نشمي: the kind of person in Jordan who helps without being asked (نخوة). He sits at a desk with a phone and explains the idea. The camera starts wide and pushes in until we see the phone, then cuts to a real screen recording of the site.

Rules carried over from the submission video:
- What the phone shows is the real site, recorded, never a mock-up. The demo strip «نموذج تجريبي…» stays in frame.
- All personal data is fictitious.
- The character is AI-generated and is not a real person; the end card says so. The video is shown only during the hackathon pitch and is not published.

Source image (AI-generated): the man in the grey blazer with the red keffiyeh. A keffiyeh-meem logo screen and a Jordan flag are behind him.

## Shots

| # | Time | Camera | On screen | Voice (Jordanian dialect) |
|---|---|---|---|---|
| 1 | 0:00–0:07 | Wide, static. He sits at the desk, phone in hand, then looks up at the lens. | Office, logo screen behind him. | «مرحبا! أنا ميسّر.» |
| 2 | 0:07–0:20 | Medium, slow drift in. | He talks to camera, hands open. | «بدك تجدد هويتك؟ تطلّع بطاقة إعاقة لابنك؟ بتلف على عشر صفحات، وآخر إشي ما بتعرف أي قانون بيحكي عنك.» |
| 3 | 0:20–0:28 | Push-in over his shoulder to the phone; he lifts it a little toward us. | His thumb on the screen. | «تعال أوريك.» |
| 4 | 0:28–0:55 | Cut on the push (zoom-through) to a full-frame screen recording at 375 px, inside a phone frame. | (a) A question is typed and the answer appears with its article chip «المادة 9». (b) The doubtful-document scenario replay, up to the amber card «النظام وقف هون». | «بتسألني بلهجتك، وبجاوبك وبقلّك من أي مادة بالقانون. وإذا القرار حساس، زي رفض طلبك، ما بقرر لحالي: بوقّف وبحوّله لموظف.» |
| 5 | 0:55–1:07 | Back to medium; he puts the phone down. | Him, smiling. | «كل كلمة إلها مصدر. واللي ما إله مصدر، بيطلع قدامك أحمر.» |
| 6 | 1:07–1:15 | End card, no character. | Keffiyeh-meem logo, «ميسّر، نشمي بجيبك», then «نموذج تجريبي لمسابقة AI for Good، مش موقع حكومي رسمي. الشخصية مولّدة بالذكاء الاصطناعي». | (music only) |

Two parts of shot 4 need thought:
- **Shot 4a needs the API.** The ask page answers live. Record it in one session when a key is allowed, or use only 4b, which replays a logged run with no model call.
- **The article in 4a must match the answer.** Check that the chip shows the article the answer actually cites (for an ID renewal, the Civil Status Law) before recording.

## Producing it

1. **Character shots (1, 2, 3, 5).** Use an image-to-video model with the source image as the first frame, one clip per shot, 5–8 s each. Generate the voice separately (shot 5 of the script is the clearest line to test first), then lip-sync shots 1, 2 and 5. Shot 3 needs no lip-sync: he looks at the phone.
2. **Phone recording (shot 4).** Record the real site at 375×812 with the replay link `/scenarios?replay=15fb1470#doubtful_id`, at 2x scale so it stays sharp when shown full frame.
3. **Edit.** Cut from the push-in of shot 3 straight to the recording in a phone frame. This is more reliable than tracking a screen onto a generated phone, which tends to wobble. Add music low under the voice, and burn in Arabic subtitles.

Prompts for the image-to-video model (English works best):
- Shot 1: "Static wide shot, the man from the image sits at a wooden office desk holding a phone, then looks up at the camera and smiles. Natural office light, shallow depth of field, no camera movement."
- Shot 2: "Medium shot, slow dolly-in, the man talks to the camera with open hands, friendly, Jordanian office in the background, the red keffiyeh stays the same."
- Shot 3: "Slow push-in over the man's shoulder toward the phone in his hands, he tilts the screen toward the camera, the screen is a plain white glow, shallow depth of field."
- Shot 5: "Medium shot, the man places the phone on the desk and smiles at the camera, static camera."

Keep in every prompt: the same face, the same keffiyeh pattern, no text generated on screens (the model writes nonsense Arabic, as on the logo screen in the source image).
