#!/usr/bin/env python3
"""Approximate TWRP renderer for checking the generated ASEM theme on a PC.

    preview.py <twrp_root_with_theme_applied> <out_dir>

Draws pages from ui.xml / ui_light.xml + portrait.xml the way TWRP lays them out
(theme 1080x1920 scaled to the X6855 GUI area 1080x2337: y and non-retainaspect
images stretched, fonts and retainaspect images not). Supports background, fill,
image, text, button (image/fill + style text) and conditions; other TWRP objects
(lists, file selectors, sliders, consoles) are drawn as labelled boxes.
Not pixel-exact - it is for catching layout mistakes before a real build.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 2337
SY = H / 1920.0

RUNTIME = {"tw_time": "9:42 PM", "tw_battery": "87%", "tw_cpu_temp": "38", "tw_active_slot": "B",
           "tw_version": "3.7.1_12-ASEM_R1", "tw_is_encrypted": "1", "tw_is_decrypted": "0",
           "tw_mtp_enabled": "1", "tw_has_boot_slots": "1", "tw_reboot_system": "1",
           "tw_reboot_bootloader": "1", "tw_reboot_poweroff": "1", "tw_reboot_recovery": "0",
           "tw_busy": "0", "tw_no_cpu_temp": "0", "tw_no_battery_percent": "0", "tw_military_time": "0",
           "tw_samsung_navbar": "0", "tw_simulate_actions": "0", "tw_language": "en.xml",
           "asem_light": "0", "tw_has_data_media": "1"}


class Theme:
    def __init__(self, root, ui_name, lang):
        th = os.path.join(root, "bootable", "recovery", "gui", "theme")
        self.img_dir = os.path.join(th, "portrait_hdpi", "images")
        self.font_dir = os.path.join(th, "common", "fonts")
        ui = ET.parse(os.path.join(th, "portrait_hdpi", ui_name)).getroot()
        self.portrait = ET.parse(os.path.join(th, "common", "portrait.xml")).getroot()
        self.vars = dict(RUNTIME)
        self.vars["tw_language"] = lang + ".xml"
        for v in ui.find("variables"):
            self.vars[v.get("name")] = self.sub(v.get("value"))
        self.vars.update({k: RUNTIME[k] for k in ("tw_time",)})
        self.res = {r.get("name"): r for r in ui.find("resources")}
        self.templates = {t.get("name"): t for t in ui.find("templates")}
        self.styles = {s.get("name"): s for s in self.portrait.find("styles")}
        self.pages = {p.get("name"): p for p in self.portrait.iter("page")}
        self.strings = {}
        for f in ("en", lang):
            doc = ET.parse(os.path.join(th, "common", "languages", f + ".xml")).getroot()
            for s in doc.iter("string"):
                self.strings[s.get("name")] = s.text or ""
        self.missing = set()
        self._fonts, self._imgs = {}, {}

    def sub(self, s):
        if s is None:
            return ""
        s = re.sub(r"\{@([^=}]+)=?([^}]*)\}", lambda m: self.strings.get(m.group(1), m.group(2))
                   if hasattr(self, "strings") else m.group(2), s)
        return re.sub(r"%([A-Za-z0-9_]+)%", lambda m: str(self.vars.get(m.group(1), m.group(0))), s)

    def num(self, s, default=0):
        try:
            return int(float(self.sub(s))) if s is not None else default
        except ValueError:
            return default

    def color(self, s):
        s = self.sub(s).lstrip("#")
        if len(s) == 6:
            s += "FF"
        try:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
        except ValueError:
            return (255, 0, 255, 255)

    def font(self, name):
        if name not in self._fonts:
            r = self.res.get(name)
            if r is None or r.tag != "font":
                self.missing.add("font " + str(name))
                return ImageFont.truetype(os.path.join(self.font_dir, "Tajawal-Medium.ttf"), 40,
                                          layout_engine=ImageFont.Layout.BASIC)
            self._fonts[name] = ImageFont.truetype(os.path.join(self.font_dir, r.get("filename")),
                                                   int(r.get("size")), layout_engine=ImageFont.Layout.BASIC)
        return self._fonts[name]

    def image(self, name):
        if name not in self._imgs:
            r = self.res.get(name)
            if r is None:
                self.missing.add("image " + name)
                return None
            fn = r.get("filename") + ("001" if r.tag == "animation" else "")
            im = Image.open(os.path.join(self.img_dir, fn + ".png")).convert("RGBA")
            if r.get("retainaspect") is None:
                im = im.resize((im.width, max(1, round(im.height * SY))), Image.LANCZOS)
            self._imgs[name] = im
        return self._imgs[name]

    def cond_ok(self, el):
        cs = list(el.findall("condition"))
        c2 = el.find("conditions")
        if c2 is not None:
            cs += list(c2.findall("condition"))
        for c in cs:
            a = self.vars.get(c.get("var1"), "")
            b = self.sub(c.get("var2", ""))
            op = c.get("op", "=")
            try:
                fa, fb = float(re.match(r"-?[\d.]+", a).group()), float(b)  # TWRP compares like atoi
                ok = {"=": fa == fb, "!=": fa != fb, ">": fa > fb, "<": fa < fb, ">=": fa >= fb, "<=": fa <= fb}[op]
            except (ValueError, KeyError, AttributeError):
                ok = (a == b) if op == "=" else (a != b) if op == "!=" else False
            if not ok:
                return False
        return True


def anchor(x, y, w, h, placement):
    p = int(placement or 0)
    if p == 1:
        return x - w, y
    if p == 2:
        return x, y - h
    if p == 3:
        return x - w, y - h
    if p == 4:
        return x - w // 2, y - h // 2
    if p == 5:
        return x - w // 2, y
    return x, y


def render(theme, page_name, out, overlay=None):
    can = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(can)

    def place(el):
        pl = el.find("placement")
        if pl is None:
            return 0, 0, None, None, 0
        x = theme.num(pl.get("x"))
        y = round(theme.num(pl.get("y")) * SY)
        w = theme.num(pl.get("w")) if pl.get("w") else None
        h = round(theme.num(pl.get("h")) * SY) if pl.get("h") else None
        return x, y, w, h, pl.get("placement")

    def draw_text(txt, font, col, x, y, placement):
        f = theme.font(font)
        box = d.textbbox((0, 0), txt, font=f)
        tw, th = box[2], f.getmetrics()[0] + f.getmetrics()[1]
        ax, ay = anchor(x, y, tw, th, placement)
        d.text((ax, ay), txt, font=f, fill=col)

    def obj(el):
        tag = el.tag
        if tag in ("action", "condition", "conditions"):
            return
        if not theme.cond_ok(el):
            return
        if tag == "template":
            for c in theme.templates[el.get("name")]:
                obj(c)
            return
        if tag == "background":
            d.rectangle((0, 0, W, H), fill=theme.color(el.get("color")))
            return
        x, y, w, h, pmode = place(el)
        if tag == "fill":
            layer = Image.new("RGBA", (max(1, w or 1), max(1, h or 1)), theme.color(el.get("color")))
            can.alpha_composite(layer, (x, y))
        elif tag == "image":
            im = theme.image(el.find("image").get("resource"))
            if im:
                ax, ay = anchor(x, y, im.width, im.height, pmode)
                can.alpha_composite(im, (max(0, ax), max(0, ay)))
        elif tag == "text":
            st = theme.styles.get(el.get("style")) if el.get("style") else None
            f = el.find("font") if el.find("font") is not None else (st.find("font") if st is not None else None)
            col = el.get("color") or (f.get("color") if f is not None else None) or "%text_color%"
            draw_text(theme.sub(el.find("text").text), f.get("resource") if f is not None else "font_m",
                      theme.color(col), x, y, pmode)
        elif tag == "button":
            st = theme.styles.get(el.get("style")) if el.get("style") else None
            imgel = el.find("image") if el.find("image") is not None else (st.find("image") if st is not None else None)
            bw, bh = w or 0, h or 0
            if imgel is not None:
                im = theme.image(imgel.get("resource"))
                if im:
                    ax, ay = anchor(x, y, im.width, im.height, pmode)
                    can.alpha_composite(im, (max(0, ax), max(0, ay)))
                    x, y, bw, bh = ax, ay, im.width, im.height
            t = el.find("text")
            if t is not None and t.text:
                fe = el.find("font") if el.find("font") is not None else (st.find("font") if st is not None else None)
                font = fe.get("resource") if fe is not None else "font_m"
                col = theme.color(fe.get("color")) if fe is not None and fe.get("color") else (230, 230, 230, 255)
                draw_text(theme.sub(t.text), font, col, x + bw // 2, y + bh // 2, 4)
        elif tag in ("listbox", "fileselector", "partitionlist", "slider", "console", "terminal", "keyboard",
                     "input", "checkbox", "progressbar", "animation", "slidervalue", "patternpassword", "textbox"):
            if w and h:
                d.rectangle((x, y, x + w, y + h), outline=(120, 120, 120, 255), width=2)
            d.text((x + 8, y + 4), "[%s]" % tag, font=theme.font("asem_f_row_s"), fill=(150, 150, 150, 255))
            if tag == "checkbox" and el.find("text") is not None:
                draw_text(theme.sub(el.find("text").text), "font_m", theme.color("%text_color%"), x + 80, y + 10, 0)
            if tag == "slider" and el.find("text") is not None:
                draw_text(theme.sub(el.find("text").text), "font_m", theme.color("%text_color%"), x + 300, y + 60, 0)

    for el in theme.pages[page_name]:
        obj(el)
    if overlay:
        for el in theme.pages[overlay]:
            obj(el)
    can.convert("RGB").save(out)


def main(root, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    jobs = [("ui.xml", "en", "main2", None), ("ui_light.xml", "ar", "main2", None),
            ("ui.xml", "en", "reboot", None), ("ui_light.xml", "ar", "reboot", None),
            ("ui.xml", "en", "asem_settings", None), ("ui.xml", "ar", "asem_settings", None),
            ("ui.xml", "en", "asem_slots", None), ("ui_light.xml", "en", "asem_transfer", None),
            ("ui.xml", "en", "install", "asem_help_install"), ("ui.xml", "ar", "main2", "asem_help_reboot"),
            ("ui.xml", "en", "install", None), ("ui_light.xml", "en", "wipe", None)]
    missing = set()
    for ui, lang, pg, ov in jobs:
        th = Theme(root, ui, lang)
        name = "%s_%s_%s%s.png" % (pg, "dark" if ui == "ui.xml" else "light", lang, "_" + ov if ov else "")
        render(th, pg, os.path.join(out_dir, name), ov)
        missing |= th.missing
    print("rendered %d previews into %s" % (len(jobs), out_dir))
    if missing:
        print("missing:", sorted(missing))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
