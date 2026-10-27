"""Extract clean Arabic text from Word-generated government PDFs.

Fonts such as Simplified Arabic draw لا/لأ/لإ/لآ and را/زا as single
ligature glyphs, and the two common extractors each break a different set:

- pdftotext keeps lam-alef right but flips را→ار and زا→از, often with a
  stray space inside the word ("إج ارء" for "إجراء").
- PyMuPDF keeps را/زا right but flips every lam-alef ("ال يجوز" for "لا يجوز").

So we take pdftotext's text and repair each word that contains ار/از by
picking the spelling PyMuPDF agrees with, comparing both under a key that
ignores lam-alef order. Words PyMuPDF never saw are left as they are and
reported, so a human can check them.

    python -m muyassar.pdf_arabic in.pdf out.txt          # whole text
    python -m muyassar.pdf_arabic --law in.pdf out.txt    # one heading per article, ready for ingest
"""
import itertools
import re
import subprocess
import sys
from pathlib import Path

_BIDI = re.compile("[‪-‮‎‏\f]")
_WORD = re.compile(r"[ء-ْ]+")
# The flipped pair, with the tanween that rides on the alef: "مباش اًر" is
# "مباشراً", and "والم أرة" is "والمرأة".
_FLIPPED = re.compile("[اأ]ً?[رز]")
_MARKS = re.compile("[ـً-ْ]")


def _key(word: str) -> str:
    """Same string for a word however its lam-alef pairs came out.

    Dropping lam entirely is crude but enough here: the key only has to tell
    ار from را, and lam is never part of that pair.
    """
    return _MARKS.sub("", word).replace("ل", "")


def _unflip(word: str, spots) -> str:
    for i in sorted(spots, reverse=True):
        pair = _FLIPPED.match(word, i).group()
        word = word[:i] + pair[-1] + pair[:-1] + word[i + len(pair):]
    return word


def _variants(word: str):
    """Every way of un-flipping the ار/از pairs in word, fewest changes first."""
    spots = [m.start() for m in _FLIPPED.finditer(word)]
    for n in range(len(spots) + 1):
        for chosen in itertools.combinations(spots, n):
            yield _unflip(word, chosen)


def _repair(word: str, known: set[str]) -> str | None:
    for v in _variants(word):
        if _key(v) in known:
            return v
    return None


def _fix_order(text: str) -> str:
    """pdftotext also moves numbers out of their brackets in RTL lines."""
    text = re.sub("([\u0621-\u064a]) \u064bء", "\\1ء\u064b", text)  # "بنا ًء" → "بناءً"
    text = re.sub(r"\(\s*\)\s*%(\d+)|\)%(\d+)\(", r"(\1\2%) ", text)  # "( )%10" / ")%10(" → "(10%)"
    text = re.sub(r"\(\s*(:?)\s*\)\s*(\d+)", r"(\2)\1 ", text)  # "( :)1" → "(1):"
    text = re.sub(r"\)(\d+)", r"\1) ", text)                    # "لسنة )2017ويعمل" → "لسنة 2017) ويعمل"
    text = re.sub(r"-(\d+)(?=[ء-ي])", r"\1- ", text)   # "-1تنفيذ" → "1- تنفيذ"
    text = re.sub(r" ،(\d+)", r" \1،", text)                    # "لسنة ،2007" → "لسنة 2007،"
    text = re.sub(r"(\d)(?=[ء-ي])", r"\1 ", text)      # "2007وتؤول" → "2007 وتؤول"
    text = re.sub(r" ([،؛])(?=\S)", r"\1 ", text)               # "إنكاره ،مباشراً" → "إنكاره، مباشراً"
    return re.sub(r"[ \t]+", " ", text)


def extract(pdf: Path) -> tuple[str, list[str]]:
    import pymupdf

    raw = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, check=True
    ).stdout.decode("utf-8")
    text = re.sub(r"[ \t]+", " ", _BIDI.sub("", raw))
    mupdf = "".join(page.get_text() for page in pymupdf.open(pdf))
    known = {_key(w) for w in _WORD.findall(mupdf)}

    out, unresolved, pos = [], [], 0
    words = list(_WORD.finditer(text))
    i = 0
    while i < len(words):
        m = words[i]
        out.append(text[pos:m.start()])
        # Join the following fragments while they start with a flipped pair
        # and sit one space away: "الق ار ارت" is one word, "القرارات".
        run = [m]
        while i + len(run) < len(words):
            nxt = words[i + len(run)]
            if text[run[-1].end():nxt.start()] == " " and _FLIPPED.match(nxt.group()):
                run.append(nxt)
            else:
                break
        fixed, used = None, 1
        for n in range(len(run), 0, -1):
            candidate = "".join(w.group() for w in run[:n])
            if _FLIPPED.search(candidate) or n > 1:
                fixed = _repair(candidate, known)
                if fixed:
                    used = n
                    break
        # A lone letter counts as a fragment: "ب" and "ت" are known only as list labels.
        if fixed is None and len(run) > 1 and (len(m.group()) < 2 or _key(m.group()) not in known):
            # PyMuPDF split this word differently, but when the piece before
            # the space is no word on its own ("ب اريل"), the space came from
            # the ligature. A real word before it ("أي ارتب") keeps its space.
            joined = "".join(w.group() for w in run)
            fixed, used = _unflip(joined, [mm.start() for mm in _FLIPPED.finditer(joined)]), len(run)
            unresolved.append(f"{' '.join(w.group() for w in run)} → {fixed}")
        if fixed is None:
            fixed = m.group()
            if _FLIPPED.search(fixed) and _key(fixed) not in known:
                unresolved.append(fixed)
        out.append(fixed)
        pos = run[used - 1].end()
        i += used
    out.append(text[pos:])
    return _fix_order("".join(out)), unresolved


# An article heading starts a line, or is glued after the previous sentence
# but then always followed by a colon. In-text references ("المادة (8) من هذا
# القانون") have neither.
_HEADING = re.compile(r"^\s*المادة\s*\((\d+)\)\s*:?\s*|المادة\s*\((\d+)\)\s*:\s*", re.M)


def law_articles(text: str) -> str:
    """Put each "المادة N" heading on its own line, the shape ingest expects.

    Drops the royal preamble and the signature after the last article, and
    fails loudly if the headings are not 1, 2, 3, ... in order.
    """
    heads = list(_HEADING.finditer(text))
    numbers = [int(h.group(1) or h.group(2)) for h in heads]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"أرقام المواد مش متسلسلة: {numbers}")
    last = text.find("مكلفون بتنفيذ أحكام هذا القانون", heads[-1].start())
    end = text.find("\n", last) if last >= 0 else len(text)
    body = _HEADING.sub(lambda h: f"\nالمادة {h.group(1) or h.group(2)}\n", text[heads[0].start():end])
    return "\n".join(line.strip() for line in body.splitlines() if line.strip()) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if a != "--law"]
    src, dst = Path(args[0]), Path(args[1])
    text, unresolved = extract(src)
    if "--law" in sys.argv:
        text = law_articles(text)
    dst.write_text(text, encoding="utf-8", newline="\n")
    print(f"{dst}: {len(text)} حرف")
    if unresolved:
        print(f"{len(unresolved)} كلمة ما انحسمت، راجعها يدويًا: {sorted(set(unresolved))}")


if __name__ == "__main__":
    main()
