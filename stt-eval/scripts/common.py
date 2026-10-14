"""Shared text normalisation and metrics for the Uzbek STT evaluation.

The SAME `normalize` is applied to references and hypotheses of every model.
Raw texts are never modified; metrics are computed on normalised copies.
"""
import re
import unicodedata

# Every apostrophe-like character used for Uzbek oʻ/gʻ and the tutuq belgisi (ʼ)
# is folded to one symbol, so typography cannot count as an error.
APOSTROPHES = "'`´‘’ʻʼʽ′‛"
_APOS_RE = re.compile("[" + re.escape(APOSTROPHES) + "]")
_CYRILLIC_RE = re.compile("[Ѐ-ӿ]")


def normalize(text: str) -> list:
    """Uzbek ASR scoring normalisation (documented in docs/STT_EVALUATION.md).

    1. Unicode NFKC.            2. lower-case.
    3. apostrophe variants -> U+02BB.
    4. hyphens/dashes -> space (compounds are split identically for ref and hyp).
    5. every other punctuation/symbol removed; whitespace collapsed.
    NOT done (on purpose): number spelling (digits stay digits), Cyrillic->Latin
    folding, spelling correction. Those differences remain errors.
    """
    t = unicodedata.normalize("NFKC", text).lower()
    t = _APOS_RE.sub("ʻ", t)
    t = re.sub(r"[-‐‑‒–—―]", " ", t)
    t = re.sub(r"[^\w\sʻ]", " ", t)
    t = t.replace("_", " ")
    # an apostrophe that is not inside a word (e.g. quotes) is punctuation
    t = re.sub(r"(?<!\w)ʻ|ʻ(?!\w)", " ", t)
    return t.split()


def align_ops(ref: list, hyp: list):
    """Levenshtein alignment -> (substitutions, deletions, insertions)."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    s = de = ins = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]):
            s += ref[i - 1] != hyp[j - 1]; i -= 1; j -= 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            de += 1; i -= 1
        else:
            ins += 1; j -= 1
    return s, de, ins


def char_edits(ref_words: list, hyp_words: list) -> int:
    """Character edit distance between normalised texts (words joined by one space)."""
    a, b = " ".join(ref_words), " ".join(hyp_words)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def repetition(raw_hyp: str, ref_words: list, hyp_words: list) -> str:
    """Flag hallucinated repetition that the reference does not contain."""
    # a 1-4 character unit repeated 6+ times in a row ("aaaaaa", "ĞaĞaĞa...", "2-2-2-2-2-2")
    if re.search(r"(\S{1,4}?)\1{5,}", raw_hyp):
        return "char-run"
    ref_s = " " + " ".join(ref_words) + " "
    for n in (1, 2, 3):
        for i in range(len(hyp_words) - 3 * n + 1):
            g = hyp_words[i:i + n]
            if hyp_words[i + n:i + 2 * n] == g and hyp_words[i + 2 * n:i + 3 * n] == g:
                if (" " + " ".join(g)) * 3 + " " not in ref_s:
                    return f"{n}-gram-x3"
    if ref_words and len(hyp_words) > 1.5 * len(ref_words) + 3:
        return "over-long"
    return ""


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text))


def has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)
