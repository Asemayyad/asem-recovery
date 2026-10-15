"""Arabic text preparation for TWRP (which draws glyphs left-to-right, with no
letter joining and no right-to-left support).

visual(text) returns the string TWRP should draw:
  1. letters are replaced by their joined presentation forms (initial/medial/
     final/isolated, lam-alef ligatures); isolated forms use the base letter,
     which every Arabic font has;
  2. the line is put into visual order for a right-to-left paragraph: Arabic
     runs are reversed, while Latin words, numbers and TWRP placeholders
     (%var%, {...}) keep their own left-to-right order.
"""
import re

# base letter: (isolated, final, initial, medial) - None = form does not exist
FORMS = {
    0x0621: (0xFE80, None, None, None),
    0x0622: (0xFE81, 0xFE82, None, None),
    0x0623: (0xFE83, 0xFE84, None, None),
    0x0624: (0xFE85, 0xFE86, None, None),
    0x0625: (0xFE87, 0xFE88, None, None),
    0x0626: (0xFE89, 0xFE8A, 0xFE8B, 0xFE8C),
    0x0627: (0xFE8D, 0xFE8E, None, None),
    0x0628: (0xFE8F, 0xFE90, 0xFE91, 0xFE92),
    0x0629: (0xFE93, 0xFE94, None, None),
    0x062A: (0xFE95, 0xFE96, 0xFE97, 0xFE98),
    0x062B: (0xFE99, 0xFE9A, 0xFE9B, 0xFE9C),
    0x062C: (0xFE9D, 0xFE9E, 0xFE9F, 0xFEA0),
    0x062D: (0xFEA1, 0xFEA2, 0xFEA3, 0xFEA4),
    0x062E: (0xFEA5, 0xFEA6, 0xFEA7, 0xFEA8),
    0x062F: (0xFEA9, 0xFEAA, None, None),
    0x0630: (0xFEAB, 0xFEAC, None, None),
    0x0631: (0xFEAD, 0xFEAE, None, None),
    0x0632: (0xFEAF, 0xFEB0, None, None),
    0x0633: (0xFEB1, 0xFEB2, 0xFEB3, 0xFEB4),
    0x0634: (0xFEB5, 0xFEB6, 0xFEB7, 0xFEB8),
    0x0635: (0xFEB9, 0xFEBA, 0xFEBB, 0xFEBC),
    0x0636: (0xFEBD, 0xFEBE, 0xFEBF, 0xFEC0),
    0x0637: (0xFEC1, 0xFEC2, 0xFEC3, 0xFEC4),
    0x0638: (0xFEC5, 0xFEC6, 0xFEC7, 0xFEC8),
    0x0639: (0xFEC9, 0xFECA, 0xFECB, 0xFECC),
    0x063A: (0xFECD, 0xFECE, 0xFECF, 0xFED0),
    0x0640: (0x0640, 0x0640, 0x0640, 0x0640),
    0x0641: (0xFED1, 0xFED2, 0xFED3, 0xFED4),
    0x0642: (0xFED5, 0xFED6, 0xFED7, 0xFED8),
    0x0643: (0xFED9, 0xFEDA, 0xFEDB, 0xFEDC),
    0x0644: (0xFEDD, 0xFEDE, 0xFEDF, 0xFEE0),
    0x0645: (0xFEE1, 0xFEE2, 0xFEE3, 0xFEE4),
    0x0646: (0xFEE5, 0xFEE6, 0xFEE7, 0xFEE8),
    0x0647: (0xFEE9, 0xFEEA, 0xFEEB, 0xFEEC),
    0x0648: (0xFEED, 0xFEEE, None, None),
    0x0649: (0xFEEF, 0xFEF0, None, None),
    0x064A: (0xFEF1, 0xFEF2, 0xFEF3, 0xFEF4),
}
LAM_ALEF = {0x0622: (0xFEF5, 0xFEF6), 0x0623: (0xFEF7, 0xFEF8),
            0x0625: (0xFEF9, 0xFEFA), 0x0627: (0xFEFB, 0xFEFC)}
TRANSPARENT = set(range(0x064B, 0x0660)) | {0x0670}
MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<",
          "«": "»", "»": "«"}


def is_arabic(ch):
    o = ord(ch)
    return 0x0600 <= o <= 0x06FF or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF


def _joins_next(c):
    """Can this letter connect to the following letter (i.e. has an initial form)?"""
    f = FORMS.get(ord(c)) if c else None
    return bool(f and f[2])


def _joins_prev(c):
    """Can this letter connect to the previous letter (i.e. has a final form)?"""
    f = FORMS.get(ord(c)) if c else None
    return bool(f and f[1])


def shape(text):
    """Logical order in, logical order out, with presentation forms."""
    chars = list(text)
    out = []
    i = 0
    n = len(chars)

    def neighbour(idx, step):
        j = idx + step
        while 0 <= j < n and ord(chars[j]) in TRANSPARENT:
            j += step
        return chars[j] if 0 <= j < n else None

    while i < n:
        c = chars[i]
        o = ord(c)
        if o not in FORMS:
            out.append(c)
            i += 1
            continue
        prev = neighbour(i, -1)
        nxt = neighbour(i, 1)
        join_prev = _joins_next(prev) and _joins_prev(c)
        # lam + alef ligature
        if o == 0x0644 and nxt and ord(nxt) in LAM_ALEF:
            iso, fin = LAM_ALEF[ord(nxt)]
            out.append(chr(fin if join_prev else iso))
            j = i + 1
            while j < n and ord(chars[j]) in TRANSPARENT:
                out.append(chars[j])
                j += 1
            i = j + 1
            continue
        join_next = _joins_next(c) and _joins_prev(nxt)
        iso, fin, ini, med = FORMS[o]
        if join_prev and join_next and med:
            form = med
        elif join_prev and fin:
            form = fin
        elif join_next and ini:
            form = ini
        else:
            form = o  # isolated: the base letter (always present in fonts)
        out.append(chr(form))
        i += 1
    return "".join(out)


# A left-to-right run: placeholders, Latin/digit words, joined by spaces/simple punctuation.
_LTR_TOKEN = r"(?:%[A-Za-z0-9_]+%|\{[^}]*\}|[A-Za-z0-9][A-Za-z0-9.,:/_+\-'%&#]*)"
_LTR_RUN = re.compile(_LTR_TOKEN + r"(?:[ \-/:.+]+" + _LTR_TOKEN + r")*")


def visual(text):
    """Shaped + visually ordered string for TWRP. Non-Arabic text is returned as is."""
    if not any(is_arabic(c) for c in text):
        return text
    s = shape(text)
    runs = []
    pos = 0
    for m in _LTR_RUN.finditer(s):
        if m.start() > pos:
            runs.append(("rtl", s[pos:m.start()]))
        runs.append(("ltr", m.group()))
        pos = m.end()
    if pos < len(s):
        runs.append(("rtl", s[pos:]))
    out = []
    for kind, chunk in reversed(runs):
        if kind == "ltr":
            out.append(chunk)
        else:
            out.append("".join(MIRROR.get(c, c) for c in reversed(chunk)))
    return "".join(out)


if __name__ == "__main__":
    import sys
    for line in sys.argv[1:]:
        print(visual(line))
