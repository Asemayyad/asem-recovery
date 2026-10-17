# ASEM Recovery banner: theme renders (design/build_preview) + logo.  python design/make_banner.py <repo> <out.png>
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
R = sys.argv[1]; OUT = sys.argv[2]
PV = os.path.join(R, "design", "build_preview"); FONTS = os.path.join(R, "theme", "fonts")
f = lambda w, s: ImageFont.truetype(os.path.join(FONTS, "Tajawal-%s.ttf" % w), s)
W, H = 3000, 1100
VER = "TWRP 3.7.1_14 \u00b7 ASEM R3"

def screen(name, fix=None):
    im = Image.open(os.path.join(PV, name)).convert("RGB")
    if fix:  # replace the old version line (x0, x1, align) on the clock card
        x0, x1, align = fix
        d = ImageDraw.Draw(im); bg = im.getpixel((x0 - 6, 470))
        d.rectangle((x0, 448, x1, 500), fill=bg)
        col = (150, 156, 168) if sum(bg) < 300 else (95, 102, 115)
        ft = f("Regular", 30); tw = d.textlength(VER, font=ft)
        d.text((x0 if align == "l" else x1 - tw, 452), VER, font=ft, fill=col)
    return im

def phone(im, h):
    w = round(im.width * h / im.height)
    scr = im.resize((w, h), Image.LANCZOS)
    b = 12; r = 54
    ph = Image.new("RGBA", (w + 2 * b, h + 2 * b), (0, 0, 0, 0))
    ImageDraw.Draw(ph).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), r + b, fill=(30, 36, 44, 255), outline=(62, 72, 84, 255), width=2)
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    ph.paste(scr, (b, b), m)
    return ph

def place(canvas, ph, cx, cy, angle):
    p = ph.rotate(angle, resample=Image.BICUBIC, expand=True)
    sh = Image.new("RGBA", (p.width + 80, p.height + 80), (0, 0, 0, 0))
    sh.paste((0, 0, 0, 150), (40, 55), p.split()[3])
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    canvas.alpha_composite(sh, (cx - sh.width // 2, cy - sh.height // 2 + 10))
    canvas.alpha_composite(p, (cx - p.width // 2, cy - p.height // 2))

# background: dark with a soft green glow in the middle
bg = Image.new("RGBA", (W, H), (11, 15, 20, 255))
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(glow)
g.ellipse((W/2 - 520, H/2 - 420, W/2 + 520, H/2 + 420), fill=(18, 160, 120, 95))
g.ellipse((W/2 - 900, H/2 - 260, W/2 + 900, H/2 + 600), fill=(10, 70, 60, 60))
bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(170)))

shots_l = [screen("asem_slots_dark_en.jpg"), screen("asem_decrypt_dark_en.jpg"), screen("main2_dark_en.jpg", (88, 620, "l"))]
shots_r = [screen("reboot_dark_en.jpg"), screen("asem_settings_dark_ar.jpg"), screen("main2_light_ar.jpg", (500, 995, "r"))]
# outer, middle, inner on each side (inner = biggest, closest to the logo)
spec = [(330, 740, 9), (620, 830, 5), (900, 920, 0)]
for (x, h, a), im in zip(spec, shots_l):
    place(bg, phone(im, h), x, H // 2 + (40 if h < 900 else 0), a)
for (x, h, a), im in zip(spec, shots_r):
    place(bg, phone(im, h), W - x, H // 2 + (40 if h < 900 else 0), -a)

# centre: logo + title
logo = Image.open(os.path.join(R, "design", "assets", "asem_logo.png")).convert("RGBA").resize((300, 300), Image.LANCZOS)
lg = Image.new("RGBA", (W, H), (0, 0, 0, 0)); lgd = ImageDraw.Draw(lg)
lgd.ellipse((W/2 - 230, 250 - 230 + 140, W/2 + 230, 250 + 230 + 140), fill=(40, 200, 140, 120))
bg.alpha_composite(lg.filter(ImageFilter.GaussianBlur(70)))
lx, ly = W // 2 - 150, 240
sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.paste((0, 0, 0, 170), (lx + 8, ly + 18), logo.split()[3])
bg.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
bg.alpha_composite(logo, (lx, ly))
d = ImageDraw.Draw(bg)
def ctext(y, t, ft, col):
    d.text((W / 2 - d.textlength(t, font=ft) / 2, y), t, font=ft, fill=col)
ctext(575, "ASEM Recovery", f("Bold", 96), (240, 246, 244))
ctext(690, "Arabic & English  \u00b7  Data decryption", f("Medium", 34), (150, 215, 195))
ctext(742, "Infinix NOTE 50 Pro 4G (X6855)", f("Regular", 30), (150, 158, 170))
chips = ["TWRP-based", "A/B slots", "MTP + ADB"]
ft = f("Medium", 27); widths = [d.textlength(c, font=ft) + 56 for c in chips]
x = W / 2 - (sum(widths) + 18 * (len(chips) - 1)) / 2
for c, w in zip(chips, widths):
    d.rounded_rectangle((x, 805, x + w, 857), 26, fill=(22, 56, 50), outline=(40, 120, 100), width=2)
    d.text((x + 28, 816), c, font=ft, fill=(170, 235, 210)); x += w + 18
bg.convert("RGB").save(OUT, quality=95)
print("saved", OUT)
