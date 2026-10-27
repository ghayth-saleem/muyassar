"""Arabic text handling shared by chunking, indexing and evaluation.

`clean` is for text we store and show (keeps the wording, drops tatweel and
odd spacing). `normalize` and `tokens` are for matching only: they fold
letter variants so "الإخلال" and "الاخلال", or "١٥" and "15", meet.
"""
import re

_TATWEEL = "ـ"
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_SPACES = re.compile(r"[ \t ‏‎]+")
_WORD = re.compile(r"\w+")

# Function words in MSA and in Jordanian dialect, so a question like
# "شو بصير إذا ..." is matched on its content words only.
_STOPWORDS = {
    "في", "من", "علي", "عن", "الي", "او", "ان", "اذا", "ما", "لا", "لم", "هل", "مع", "كل",
    "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "الذين", "هو", "هي", "به", "بها", "له", "لها",
    "قد", "ثم", "بعد", "قبل", "حتي", "اي", "غير", "بين", "عند", "كان", "تكون", "يكون",
    "شو", "ايش", "بدي", "بدنا", "بده", "كيف", "ليش", "وين", "مين", "يعني", "مش", "انا", "احنا",
    "بصير", "بقدر", "لازم", "عشان", "هيك", "اللي", "يلي", "منه", "فيه", "فيها", "عليه", "عليها",
}
_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_PRONOUNS = ("هم", "ها", "كم", "نا", "ي", "ك")  # بياناتي → بيانات
_SUFFIXES = ("ات", "ون", "ين")


def clean(text: str) -> str:
    text = text.replace(_TATWEEL, "").translate(_DIGITS)
    lines = (_SPACES.sub(" ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def normalize(text: str) -> str:
    text = _DIACRITICS.sub("", str(text or "").replace(_TATWEEL, ""))
    return " ".join(text.translate(_DIGITS).translate(_LETTERS).casefold().split())


def _stem(word: str) -> str:
    # Only article-bearing prefixes: a bare و/ب/ل/ف is too often part of the
    # root (بيانات، وزارة) to strip safely.
    for p in _PREFIXES:
        if word.startswith(p) and len(word) - len(p) >= 3:
            word = word[len(p):]
            break
    for s in _PRONOUNS:
        if word.endswith(s) and len(word) - len(s) >= 4:
            word = word[: -len(s)]
            break
    for s in _SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 3:
            return word[: -len(s)]
    return word


def tokens(text: str) -> list[str]:
    return [_stem(w) for w in _WORD.findall(normalize(text)) if w not in _STOPWORDS]
