#!/usr/bin/env python3
"""Draw every ASEM Recovery theme image (dark "_d" and light "_l") into theme/images.

Inputs : tools/icon_sheet.png (icons.html rendered white-on-transparent, 160px cells)
         ../design/assets/asem_logo.png (Asem's logo)
Output : theme/images/*.png  (committed; the build only copies them)

Coordinates are TWRP portrait_hdpi theme units (1080 x 1920). Images that replace
stock TWRP images keep the stock sizes so TWRP's own pages keep their layout.
Needs Pillow.
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
THEME = os.path.dirname(HERE)
OUT = os.path.join(THEME, "images")
SHEET = os.path.join(HERE, "icon_sheet.png")
LOGO = os.path.join(THEME, "..", "design", "assets", "asem_logo.png")

ICONS = ["install", "wipe", "backup", "restore", "mount", "files", "bolt", "usb",
         "transfer", "term", "adv", "power", "reboot", "moon", "sun", "gear",
         "globe", "clock", "palette", "bright", "vib", "timer", "info", "back",
         "home", "log", "zip", "img", "up", "check", "chev", "chevup",
         "phone", "pc", "bootl", "lock", "help", "AB"]

PAL = {
    "d": dict(bg="#0E1116", surface="#171B22", surface2="#1F242D", line="#262C36",
              text="#E8ECF2", muted="#8A94A6", accent="#00C2A8", ink="#04211D",
              warn="#FFB020", danger="#FF5A5F", info="#5AA2FF", green="#50CB71",
              green_ink="#06230F", soft=0.16),
    "l": dict(bg="#F3F5F8", surface="#FFFFFF", surface2="#EAEEF3", line="#DDE2E9",
              text="#121722", muted="#5F6B7D", accent="#00A892", ink="#FFFFFF",
              warn="#B86E00", danger="#D93A40", info="#2F74D0", green="#3FB862",
              green_ink="#FFFFFF", soft=0.13),
}
SS = 4  # supersampling for smooth edges


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def blend(fg, bg, a):
    f, b = rgb(fg), rgb(bg)
    return "#%02X%02X%02X" % tuple(round(f[i] * a + b[i] * (1 - a)) for i in range(3))


def soft(p, key):
    return blend(p[key], p["surface"], p["soft"])


_sheet = None


def glyph(name, size, color):
    """Icon from the sheet, tinted, size x size (RGBA)."""
    global _sheet
    if _sheet is None:
        _sheet = Image.open(SHEET).convert("RGBA")
    i = ICONS.index(name)
    cell = _sheet.crop(((i % 8) * 160, (i // 8) * 160, (i % 8) * 160 + 160, (i // 8) * 160 + 160))
    a = cell.getchannel("A").resize((size, size), Image.LANCZOS)
    g = Image.new("RGBA", (size, size), rgb(color) + (255,))
    g.putalpha(a)
    return g


def rrect(w, h, r, fill=None, outline=None, width=0, dashed=False):
    """Anti-aliased rounded rectangle image."""
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    box = (width * SS // 2, width * SS // 2, w * SS - 1 - width * SS // 2, h * SS - 1 - width * SS // 2)
    if fill:
        d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r * SS, fill=rgb(fill) + (255,))
    if outline and width:
        if not dashed:
            d.rounded_rectangle(box, radius=r * SS, outline=rgb(outline) + (255,), width=width * SS)
        else:
            col = rgb(outline) + (255,)
            lw, dash, gap = width * SS, 14 * SS, 10 * SS
            x0, y0, x1, y1 = box
            rr = r * SS
            for a, b, fixed, horiz in ((x0 + rr, x1 - rr, y0, True), (x0 + rr, x1 - rr, y1, True),
                                       (y0 + rr, y1 - rr, x0, False), (y0 + rr, y1 - rr, x1, False)):
                p = a
                while p < b:
                    q = min(p + dash, b)
                    d.line(((p, fixed), (q, fixed)) if horiz else ((fixed, p), (fixed, q)), fill=col, width=lw)
                    p = q + gap
            for cx, cy, start in ((x0 + rr, y0 + rr, 180), (x1 - rr, y0 + rr, 270),
                                  (x1 - rr, y1 - rr, 0), (x0 + rr, y1 - rr, 90)):
                d.arc((cx - rr, cy - rr, cx + rr, cy + rr), start, start + 90, fill=col, width=lw)
    return big.resize((w, h), Image.LANCZOS)


def canvas(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def paste_center(base, img, cx, cy):
    base.alpha_composite(img, (round(cx - img.width / 2), round(cy - img.height / 2)))
    return base


def save(img, name):
    img.save(os.path.join(OUT, name + ".png"), optimize=True)


def chip_icon(p, icon, colorkey, size=96, gsize=None):
    c = rrect(size, size, size * 30 // 100, fill=soft(p, colorkey))
    return paste_center(c, glyph(icon, gsize or size * 58 // 100, p[colorkey]), size / 2, size / 2)


TILES = [("install", "accent"), ("wipe", "danger"), ("backup", "info"), ("restore", "info"),
         ("mount", "accent"), ("files", "accent"), ("bolt", "warn"), ("usb", "accent"),
         ("transfer", "accent"), ("AB", "warn"), ("term", "accent"), ("adv", "accent")]
SETTINGS_ICONS = ["globe", "clock", "palette", "bright", "vib", "timer", "info", "help"]


def make_theme(t):
    p = PAL[t]
    s = "_" + t

    # ---- ASEM pages ----
    save(rrect(320, 236, 36, fill=p["surface"], outline=p["line"], width=2), "asem_tile" + s)
    save(rrect(320, 236, 36, fill=soft(p, "accent"), outline=p["accent"], width=2), "asem_tile_hl" + s)
    for icon, key in TILES:
        save(chip_icon(p, icon, key, 96, 76 if icon == "AB" else 56), "asem_ic_" + icon + s)
    for icon in SETTINGS_ICONS:
        save(chip_icon(p, icon, "accent", 84), "asem_set_" + icon + s)

    for g in ("sun", "moon", "gear", "help", "back"):
        b = rrect(104, 104, 32, fill=p["surface"], outline=p["line"], width=2)
        gcol = p["accent"] if g == "help" else p["text"]
        save(paste_center(b, glyph(g, 52, gcol), 52, 52), "asem_btn_" + g + s)

    save(rrect(1000, 300, 44, fill=p["surface"], outline=p["line"], width=2), "asem_hero" + s)
    save(rrect(1000, 230, 40, fill=p["surface"], outline=p["line"], width=2), "asem_card" + s)
    save(rrect(1000, 230, 40, fill=soft(p, "warn")), "asem_card_warn" + s)
    save(rrect(1000, 400, 44, fill=p["surface"], outline=p["line"], width=2), "asem_card_tall" + s)

    for kind, key, w in (("slot", "accent", 210), ("enc", "warn", 380), ("dec", "accent", 380),
                         ("unenc", "info", 380), ("mtp", "info", 300)):
        c = rrect(w, 58, 29, fill=soft(p, key))
        dot = rrect(14, 14, 7, fill=p[key])
        c.alpha_composite(dot, (24, 22))
        save(c, "asem_chip_" + kind + s)

    # Backgrounds below are stretched with the screen (no retainaspect), so they
    # carry no glyphs; glyphs are separate retain-aspect images ("asem_g_*").
    save(rrect(836, 128, 40, fill=p["accent"]), "asem_btn_primary" + s)
    save(rrect(490, 128, 40, fill=p["surface"], outline=p["line"], width=2), "asem_btn_half" + s)
    save(rrect(490, 128, 40, fill=p["accent"]), "asem_btn_half_primary" + s)
    save(rrect(136, 128, 40, fill=soft(p, "danger")), "asem_btn_power" + s)

    # reboot chooser row backgrounds
    save(rrect(1000, 168, 40, fill=p["green"]), "asem_row_green" + s)
    save(rrect(1000, 168, 40, fill=p["surface2"]), "asem_row_normal" + s)
    save(rrect(1000, 168, 40, outline=p["line"], width=3, dashed=True), "asem_row_dashed" + s)
    save(rrect(1000, 168, 40, fill=soft(p, "danger")), "asem_row_danger" + s)

    # row icon chips (96x96, retain aspect)
    for icon in ("reboot",):
        ic = rrect(96, 96, 30, fill=blend("#FFFFFF", p["green"], 0.28))
        save(paste_center(ic, glyph(icon, 54, p["green_ink"]), 48, 48), "asem_rowic_%s_green%s" % (icon, s))
    for icon in ("bootl", "bolt"):
        ic = rrect(96, 96, 30, fill=p["surface"])
        save(paste_center(ic, glyph(icon, 52, p["text"]), 48, 48), "asem_rowic_%s%s" % (icon, s))
    save(paste_center(canvas(96, 96), glyph("lock", 50, p["muted"]), 48, 48), "asem_rowic_lock" + s)
    save(paste_center(canvas(96, 96), glyph("power", 54, p["danger"]), 48, 48), "asem_rowic_power_danger" + s)

    # loose glyphs (retain aspect)
    for name, key, size in (("chev", "muted", 40), ("chev", "danger", 40), ("chev", "green_ink", 40),
                            ("reboot", "ink", 50), ("chevup", "ink", 44), ("power", "danger", 56),
                            ("check", "ink", 30)):
        g = glyph(name, size, p[key])
        save(g, "asem_g_%s_%s%s" % (name, key, s))
        if name == "chev":
            save(g.transpose(Image.FLIP_LEFT_RIGHT), "asem_g_chevrtl_%s%s" % (key, s))

    save(rrect(1000, 188, 36, fill=p["surface"], outline=p["line"], width=2), "asem_setrow" + s)
    save(rrect(560, 84, 26, fill=p["surface2"]), "asem_seg_bg" + s)
    save(rrect(272, 68, 20, fill=p["surface"] if t == "l" else p["line"]), "asem_seg_on" + s)
    save(rrect(1080, 1320, 60, fill=p["surface"]), "asem_sheet" + s)
    save(rrect(56, 56, 28, fill=p["accent"]), "asem_step" + s)
    for g in ("back", "home", "log"):
        n = canvas(265, 128)
        save(paste_center(n, glyph(g, 64, p["muted"]), 132, 64), "asem_nav_" + g + s)
    save(paste_center(canvas(265, 128), glyph("home", 64, p["accent"]), 132, 64), "asem_nav_home_on" + s)

    # ---- replacements for stock TWRP images (same sizes) ----
    save(rrect(504, 288, 40, fill=p["surface2"], outline=p["line"], width=2), "main_button" + s)
    save(rrect(504, 192, 36, fill=p["surface2"], outline=p["line"], width=2), "main_button_half_height" + s)
    save(rrect(1008, 192, 36, fill=p["surface2"], outline=p["line"], width=2), "main_button_half_height_full_width" + s)
    save(rrect(312, 128, 30, fill=p["surface2"]), "tab_3" + s)
    save(rrect(225, 128, 30, fill=p["surface2"]), "tab_4" + s)

    cb = canvas(72, 96)
    cb.alpha_composite(rrect(52, 52, 14, outline=p["muted"], width=4), (10, 22))
    save(cb, "checkbox_false" + s)
    cb = canvas(72, 96)
    box = rrect(52, 52, 14, fill=p["accent"])
    paste_center(box, glyph("check", 36, p["ink"]), 26, 26)
    cb.alpha_composite(box, (10, 22))
    save(cb, "checkbox_true" + s)
    rd = canvas(72, 96)
    rd.alpha_composite(rrect(50, 50, 25, outline=p["muted"], width=4), (11, 23))
    save(rd, "radio_false" + s)
    rd = canvas(72, 96)
    rd.alpha_composite(rrect(50, 50, 25, outline=p["accent"], width=4), (11, 23))
    rd.alpha_composite(rrect(26, 26, 13, fill=p["accent"]), (23, 35))
    save(rd, "radio_true" + s)

    save(paste_center(canvas(72, 96), glyph("zip", 60, p["accent"]), 36, 48), "file" + s)
    save(paste_center(canvas(72, 96), glyph("files", 60, p["muted"]), 36, 48), "folder" + s)
    save(paste_center(canvas(72, 108), rrect(20, 96, 10, fill=p["accent"]), 36, 54), "handle" + s)

    pe = canvas(1008, 64)
    pe.alpha_composite(rrect(1008, 20, 10, fill=p["surface2"]), (0, 22))
    save(pe, "progress_empty" + s)
    pf = canvas(1008, 64)
    pf.alpha_composite(rrect(1008, 20, 10, fill=p["accent"]), (0, 22))
    save(pf, "progress_fill" + s)
    # busy animation: TWRP loads <filename>001, <filename>002, ...
    seg = rrect(260, 20, 10, fill=p["accent"])
    for i in range(12):
        fr = canvas(1008, 64)
        x = round(-260 + i * (1268 / 12))
        part = seg.crop((max(0, -x), 0, min(260, 1008 - x), 20))
        fr.alpha_composite(part, (max(0, x), 22))
        save(fr, "asem_ind%s%03d" % (s, i + 1))

    save(rrect(936, 192, 64, fill=p["surface2"]), "slider" + s)
    save(rrect(936, 192, 64, fill=soft(p, "accent")), "slider_used" + s)
    st = canvas(288, 192)
    knob = rrect(168, 168, 52, fill=p["accent"])
    paste_center(knob, glyph("chev", 70, p["ink"]), 84, 84)
    st.alpha_composite(knob, (60, 12))
    save(st, "slider_touch" + s)

    for g, n in (("back", "back"), ("home", "home"), ("log", "console")):
        save(paste_center(canvas(265, 128), glyph(g, 64, p["muted"]), 132, 64), n + s)
    save(paste_center(canvas(265, 128), glyph("chevup", 56, p["muted"]).transpose(Image.FLIP_TOP_BOTTOM), 132, 64), "kb_hide" + s)
    save(paste_center(canvas(265, 128), glyph("chevup", 56, p["muted"]), 132, 64), "kb_show" + s)
    fab = canvas(216, 192)
    fab.alpha_composite(rrect(168, 168, 60, fill=p["accent"]), (24, 12))
    save(paste_center(fab, glyph("check", 76, p["ink"]), 108, 96), "fab_selectfolder" + s)
    save(paste_center(canvas(344, 450), glyph("lock", 300, p["accent"]), 172, 225), "unlock_icon" + s)
    for g, n in (("bright", "tab_display"), ("gear", "tab_general"), ("globe", "tab_language"),
                 ("clock", "tab_timezone"), ("vib", "tab_vibration")):
        save(paste_center(canvas(216, 96), glyph(g, 72, p["text"]), 108, 48), n + s)
    save(paste_center(canvas(312, 128), glyph("chevup", 48, p["text"]), 156, 64), "sort_asc" + s)
    save(paste_center(canvas(312, 128), glyph("chevup", 48, p["text"]).transpose(Image.FLIP_TOP_BOTTOM), 156, 64), "sort_desc" + s)
    save(canvas(312, 128), "sort_empty" + s)


def make_shared():
    logo = Image.open(LOGO).convert("RGBA")
    save(logo.resize((120, 120), Image.LANCZOS), "asem_logo_120")
    save(logo.resize((440, 440), Image.LANCZOS), "asem_logo_splash")
    hdr = canvas(184, 256)
    save(paste_center(hdr, logo.resize((124, 124), Image.LANCZOS), 92, 164), "logo")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    make_shared()
    for t in PAL:
        make_theme(t)
    n = len([f for f in os.listdir(OUT) if f.endswith(".png")])
    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print("%d images, %.1f KB" % (n, size / 1024))
    sys.exit(0)
