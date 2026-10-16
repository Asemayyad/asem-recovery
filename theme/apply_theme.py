#!/usr/bin/env python3
"""Apply the ASEM Recovery theme to a TWRP android-14.1 source tree.

    apply_theme.py <twrp_source_root>            apply (used by build.sh)
    apply_theme.py --check <twrp_source_root>    apply, then validate everything

What it does (all inside <root>/bootable/recovery):
  * gui/theme/portrait_hdpi : ui.xml (dark) + ui_light.xml, splash.xml, images
  * gui/theme/common        : portrait.xml gets the ASEM pages (Home = main2,
                              "Reboot to..." = reboot, settings, slots, transfer,
                              help sheets); languages = English + Arabic only;
                              Tajawal fonts
  * gui/pages.cpp, gui/gui.cpp : load ui_light.xml when asem_light = 1
Device-independent: nothing here is specific to one phone.
Layout units: TWRP portrait_hdpi theme units (1080 x 1920).
"""
import os
import re
import shutil
import sys
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from arabic import visual  # noqa: E402

# tw_language holds the language NAME ("en", "ar"); TWRP adds ".xml" itself
# (PageManager::LoadLanguage -> languages/<name>.xml). R1 used "ar.xml" -> it looked for
# ar.xml.xml, stayed English, while these conditions still mirrored the layout.
RTL = '<condition var1="tw_language" var2="ar"/>'
LTR = '<condition var1="tw_language" op="!=" var2="ar"/>'

PALETTES = {
    "d": dict(bg="#0E1116", surface="#171B22", text="#E8ECF2", muted="#8A94A6",
              accent="#00C2A8", ink="#04211D", warn="#FFB020", danger="#FF5A5F",
              info="#5AA2FF", green_ink="#06230F", dim="#000000A8", semi="#00000099",
              highlight="#FFFFFF22"),
    "l": dict(bg="#F3F5F8", surface="#FFFFFF", text="#121722", muted="#5F6B7D",
              accent="#00A892", ink="#FFFFFF", warn="#B86E00", danger="#D93A40",
              info="#2F74D0", green_ink="#FFFFFF", dim="#00000080", semi="#00000066",
              highlight="#00000018"),
}

FONTS = [  # name, file, size  (attribute order matters: TWRP's build parses font_m)
    ("font_l", "Tajawal-Medium.ttf", 54), ("font_m", "Tajawal-Medium.ttf", 42),
    ("font_s", "Tajawal-Regular.ttf", 36), ("fixed", "DroidSansMono.ttf", 30),
    ("keylabel", "Tajawal-Medium.ttf", 64), ("keylabel-small", "Tajawal-Medium.ttf", 46),
    ("keylabel-longpress", "Tajawal-Medium.ttf", 32),
    ("asem_f_status", "Tajawal-Medium.ttf", 32), ("asem_f_brand", "Tajawal-Bold.ttf", 52),
    ("asem_f_cap", "Tajawal-Medium.ttf", 26), ("asem_f_clock", "Tajawal-Light.ttf", 128),
    ("asem_f_h1", "Tajawal-Bold.ttf", 52), ("asem_f_h2", "Tajawal-Bold.ttf", 46),
    ("asem_f_body", "Tajawal-Medium.ttf", 32), ("asem_f_lead", "Tajawal-Regular.ttf", 30),
    ("asem_f_tile", "Tajawal-Bold.ttf", 38), ("asem_f_hint", "Tajawal-Regular.ttf", 26),
    ("asem_f_chip", "Tajawal-Medium.ttf", 28), ("asem_f_btn", "Tajawal-Bold.ttf", 40),
    ("asem_f_row_t", "Tajawal-Bold.ttf", 40), ("asem_f_row_s", "Tajawal-Regular.ttf", 28),
    ("asem_f_seg", "Tajawal-Medium.ttf", 30), ("asem_f_step", "Tajawal-Bold.ttf", 28),
]

# stock TWRP image resources we replace (resource name == file name, plus _d/_l)
THEMED_STOCK = ["main_button", "main_button_half_height", "main_button_half_height_full_width",
                "fab_selectfolder", "tab_3", "tab_4", "file", "folder", "unlock_icon", "home",
                "back", "console", "kb_hide", "kb_show", "checkbox_false", "checkbox_true",
                "radio_false", "radio_true", "sort_asc", "sort_desc", "sort_empty",
                "progress_empty", "progress_fill", "slider", "slider_used", "slider_touch",
                "handle", "tab_general", "tab_timezone", "tab_display", "tab_vibration",
                "tab_language"]
STRETCH = set(["asem_tile", "asem_tile_hl", "asem_hero", "asem_card", "asem_card_warn", "asem_card_tall",
               "asem_btn_primary", "asem_btn_half", "asem_btn_half_primary", "asem_btn_power",
               "asem_row_green", "asem_row_normal", "asem_row_dashed", "asem_row_danger",
               "asem_setrow", "asem_seg_bg", "asem_seg_on", "asem_sheet",
               "asem_chip_slot", "asem_chip_enc", "asem_chip_dec", "asem_chip_unenc", "asem_chip_mtp"])
THEMED_ASEM = sorted(STRETCH | set(
    ["asem_btn_sun", "asem_btn_moon", "asem_btn_gear", "asem_btn_help", "asem_btn_back", "asem_step",
     "asem_nav_back", "asem_nav_home", "asem_nav_home_on", "asem_nav_log",
     "asem_rowic_reboot_green", "asem_rowic_bootl", "asem_rowic_bolt", "asem_rowic_lock",
     "asem_rowic_power_danger"]
    + ["asem_ic_" + n for n in ("install", "wipe", "backup", "restore", "mount", "files", "bolt",
                                "usb", "transfer", "AB", "term", "adv")]
    + ["asem_set_" + n for n in ("globe", "clock", "palette", "bright", "vib", "timer", "info", "help")]
    + ["asem_g_%s_%s" % g for g in (("chev", "muted"), ("chev", "danger"), ("chev", "green_ink"),
                                     ("chevrtl", "muted"), ("chevrtl", "danger"), ("chevrtl", "green_ink"),
                                     ("reboot", "ink"), ("chevup", "ink"), ("power", "danger"),
                                     ("check", "ink"))]))
SHARED_IMAGES = ["logo", "asem_logo_120", "asem_logo_splash"]

AR = {}       # string id -> Arabic (logical order)
EN = {}       # string id -> English


# --------------------------------------------------------------------------- XML helpers
def s(sid, en, ar=None):
    """Translatable string; returns TWRP's {@id=default} reference."""
    sid = "asem_" + sid
    if sid in EN and EN[sid] != en:
        raise ValueError("string id reused with other text: " + sid)
    EN[sid] = en
    if ar:
        AR[sid] = ar
    return "{@%s=%s}" % (sid, en)


def conds(*cs):
    cs = [c for c in cs if c]
    if not cs:
        return ""
    if len(cs) == 1:
        return cs[0]
    return "<conditions>" + "".join(cs) + "</conditions>"


def cond(var, val, op=None):
    o = ' op="%s"' % escape(op, {'"': "&quot;"}) if op else ""
    return '<condition var1="%s"%s var2="%s"/>' % (var, o, val)


def text(x, y, txt, font, color, align=0, c=""):
    return ('<text color="%s">%s<font resource="%s"/><placement x="%d" y="%d" placement="%d"/>'
            '<text>%s</text></text>' % (color, c, font, x, y, align, escape(txt)))


def image(x, y, res, align=0, c=""):
    return '<image>%s<image resource="%s"/><placement x="%d" y="%d" placement="%d"/></image>' % (
        c, res, x, y, align)


def actions(*acts):
    out = []
    for a in acts:
        if isinstance(a, tuple):
            fn, arg = a
            out.append('<action function="%s">%s</action>' % (fn, escape(arg)))
        else:
            out.append('<action function="%s"/>' % a)
    return "<actions>" + "".join(out) + "</actions>"


def button(x, y, acts, res=None, w=None, h=None, c=""):
    pl = '<placement x="%d" y="%d"%s/>' % (x, y, ' w="%d" h="%d"' % (w, h) if w else "")
    img = '<image resource="%s"/>' % res if res else '<fill color="%transparent%"/>'
    return "<button>%s%s%s%s</button>" % (c, pl, img, actions(*acts))


def fill(x, y, w, h, color, c=""):
    return '<fill color="%s">%s<placement x="%d" y="%d" w="%d" h="%d"/></fill>' % (color, c, x, y, w, h)


def page_action(c, *acts):
    return "<action>%s%s</action>" % (c, actions(*acts))


def key_action(key, *acts):
    return '<action><touch key="%s"/>%s</action>' % (key, actions(*acts))


def bidi_text(x_ltr, x_rtl, y, txt, font, color, c=""):
    """Same text placed left-aligned (LTR) or right-aligned (RTL)."""
    return (text(x_ltr, y, txt, font, color, 0, conds(LTR, c)) +
            text(x_rtl, y, txt, font, color, 1, conds(RTL, c)))


def page(name, body, template="asem_page"):
    # The navbar Back/Home buttons only send a key; each page must say what it does.
    # R1 had none on the ASEM pages: Back/Home did nothing (e.g. stuck in ASEM Transfer).
    keys = "" if name == "main2" else (key_action("home", ("page", "main2")) +
                                        key_action("back", ("page", "main2")))
    return '<page name="%s"><template name="%s"/>%s%s</page>' % (name, template, keys, body)


# --------------------------------------------------------------------------- shared parts
def header(title, help_page=None, back_to=None):
    back = actions(("page", back_to)) if back_to else actions(("key", "back"))
    out = '<button><placement x="40" y="92"/><image resource="asem_btn_back"/>%s</button>' % back
    out += bidi_text(172, 916, 108, title, "asem_f_h1", "%asem_text%")
    if help_page:
        out += button(936, 92, [("overlay", help_page)], "asem_btn_help")
    return out


def lead(y, line):
    return bidi_text(44, 1036, y, line, "asem_f_lead", "%asem_muted%")


# --------------------------------------------------------------------------- Home (main2)
TILES = [  # icon, page/actions, label, hint, (ar label, ar hint)
    ("install", [("queueclear", ""), ("set", "tw_selectimage=0"), ("page", "install")],
     s("t_install", "Install", "تثبيت"), s("h_install", "Flash ROM zip or image", "تفليش روم أو صورة")),
    ("wipe", [("page", "wipe")], s("t_wipe", "Wipe", "مسح"), s("h_wipe", "Clean before a new ROM", "تنظيف قبل روم جديد")),
    ("backup", [("page", "backup")], s("t_backup", "Backup", "نسخ احتياطي"), s("h_backup", "Save partitions to a file", "حفظ الأقسام في ملف")),
    ("restore", [("page", "restore")], s("t_restore", "Restore", "استعادة"), s("h_restore", "Bring a backup back", "إرجاع نسخة محفوظة")),
    ("mount", [("page", "mount")], s("t_mount", "Mount", "تركيب"), s("h_mount", "Open or close partitions", "فتح وإغلاق الأقسام")),
    ("files", [("set", "tw_file_location1=/sdcard"), ("page", "filemanagerlist")],
     s("t_files", "Files", "الملفات"), s("h_files", "Browse, copy, delete", "تصفح ونسخ وحذف")),
    ("bolt", [("page", "fastboot")], s("t_fastboot", "Fastboot", "فاستبوت"), s("h_fastboot", "Flash from your PC", "التفليش من الكمبيوتر")),
    ("usb", [("page", "sideload")], s("t_sideload", "ADB Sideload", "سايدلود ADB"), s("h_sideload", "Send a zip from your PC", "إرسال ملف من الكمبيوتر")),
    ("transfer", [("page", "asem_transfer")], s("t_transfer", "ASEM Transfer", "نقل ASEM"), s("h_transfer", "Copy files from your PC", "نسخ ملفات من الكمبيوتر")),
    ("AB", [("cmd", "sh /system/bin/asem_slot.sh status fresh"), ("page", "asem_slots")],
     s("t_slots", "Slots", "الخانات"), s("h_slots", "Switch between A and B", "التبديل بين A و B")),
    ("term", [("page", "terminalcommand")], s("t_terminal", "Terminal", "الطرفية"), s("h_terminal", "Type shell commands", "كتابة أوامر")),
    ("adv", [("page", "advanced")], s("t_advanced", "Advanced", "متقدم"), s("h_advanced", "Logs, fix tools, extras", "سجلات وأدوات إصلاح")),
]


def home_page():
    b = []
    # theme: reload when the saved choice differs from the loaded file
    b.append(page_action(conds(cond("asem_light", "1"), cond("asem_is_light", "0")), ("reload", "")))
    b.append(page_action(conds(cond("asem_light", "0"), cond("asem_is_light", "1")), ("reload", "")))
    # back on Home: the next "Decrypt Data" starts at the lock-type chooser again
    b.append(page_action("", ("set", "asem_dec_chosen=0")))
    # top bar
    b.append(image(44, 92, "asem_logo_120"))
    b.append(text(184, 98, "ASEM", "asem_f_brand", "%asem_text%"))
    b.append(text(186, 162, "RECOVERY", "asem_f_cap", "%asem_muted%"))
    # (no theme button on Home: switching from here misbehaved in R1; use Settings > Theme)
    b.append(button(932, 98, [("page", "asem_settings")], "asem_btn_gear"))
    # hero
    b.append(image(40, 236, "asem_hero"))
    b.append(text(84, 255, "%tw_time%", "asem_f_clock", "%asem_text%", 0, LTR))
    b.append(text(996, 255, "%tw_time%", "asem_f_clock", "%asem_text%", 1, RTL))
    b.append(bidi_text(88, 994, 380, s("hero_sub", "TWRP %tw_version%", "TWRP %tw_version%"), "asem_f_lead", "%asem_muted%"))
    chips_ltr = [(84, 210), (306, 380), (698, 300)]
    chips_rtl = [(786, 210), (394, 380), (82, 300)]
    chip_defs = [
        (0, "asem_chip_slot", s("chip_slot", "Slot %tw_active_slot%", "الخانة %tw_active_slot%"), "%asem_accent%",
         cond("tw_has_boot_slots", "1")),
        (1, "asem_chip_enc", s("chip_enc", "Data encrypted", "البيانات مشفرة"), "%asem_warn%",
         conds(cond("tw_is_encrypted", "1"), cond("tw_is_decrypted", "0"))),
        (1, "asem_chip_dec", s("chip_dec", "Data decrypted", "البيانات مفكوكة"), "%asem_accent%",
         cond("tw_is_decrypted", "1")),
        (1, "asem_chip_unenc", s("chip_unenc", "Data not encrypted", "البيانات غير مشفرة"), "%asem_info%",
         cond("tw_is_encrypted", "0")),
        (2, "asem_chip_mtp", s("chip_mtp", "USB: MTP + ADB", "USB: MTP + ADB"), "%asem_info%",
         cond("tw_mtp_enabled", "1")),
    ]
    for slot, res, txt, col, cc in chip_defs:
        for dirc, pos in ((LTR, chips_ltr), (RTL, chips_rtl)):
            x, w = pos[slot]
            c = conds(dirc, cc) if cc.startswith("<condition ") else conds(dirc, *re.findall(r"<condition [^>]*/>", cc))
            b.append(image(x, 452, res, 0, c))
            b.append(text(x + w // 2 + 8, 481, txt, "asem_f_chip", col, 4, c))
    # tiles 3 x 4
    for i, (icon, acts, label, hint) in enumerate(TILES):
        r, col = divmod(i, 3)
        y = 560 + r * 252
        for dirc, cidx in ((LTR, col), (RTL, 2 - col)):
            x = 40 + cidx * 340
            b.append(button(x, y, acts, "asem_tile", c=dirc))
            b.append(image(x + 160, y + 62, "asem_ic_" + icon, 4, dirc))
            b.append(text(x + 160, y + 136, label, "asem_f_tile", "%asem_text%", 4, dirc))
            b.append(text(x + 160, y + 188, hint, "asem_f_hint", "%asem_muted%", 4, dirc))
    # bottom buttons
    reboot_lbl = s("reboot_to", "Reboot to...", "إعادة التشغيل إلى...")
    for dirc, x_btn, x_pow in ((LTR, 40, 904), (RTL, 204, 40)):
        b.append(button(x_btn, 1580, [("page", "reboot")], "asem_btn_primary", c=dirc))
        b.append(image(x_btn + 60, 1644, "asem_g_reboot_ink", 4, dirc))
        b.append(image(x_btn + 776, 1644, "asem_g_chevup_ink", 4, dirc))
        b.append(text(x_btn + 418, 1644, reboot_lbl, "asem_f_btn", "%asem_ink%", 4, dirc))
        b.append(button(x_pow, 1580, poweroff_actions("main2"), "asem_btn_power", c=dirc))
        b.append(image(x_pow + 68, 1644, "asem_g_power_danger", 4, dirc))
    return page("main2", "".join(b), "asem_home")


def poweroff_actions(back):
    return [("set", "tw_back=" + back), ("set", "tw_action=reboot"), ("set", "tw_action_param=poweroff"),
            ("set", "tw_reboot_param=poweroff"), ("set", "tw_has_action2=0"),
            ("set", "tw_text1={@no_os1=No OS Installed! Are you}"),
            ("set", "tw_text2={@no_ospo=sure you wish to power off?}"),
            ("set", "tw_action_text1={@turning_off=Turning Off...}"),
            ("set", "tw_complete_text1={@turning_off=Turning Off...}"),
            ("set", "tw_slider_text={@swipe_power_off=Swipe to Power Off}"),
            ("page", "rebootcheck")]


# --------------------------------------------------------------------------- Reboot to...
def reboot_page():
    b = [header(s("rb_title", "Reboot to...", "إعادة التشغيل إلى..."), "asem_help_reboot")]
    b.append(lead(236, s("rb_lead", "Choose where the phone goes next. Active slot: %tw_active_slot%",
                         "اختر إلى أين يذهب الهاتف. الخانة النشطة: %tw_active_slot%")))
    bootloader = [("set", "tw_back=reboot"), ("set", "tw_action=reboot"), ("set", "tw_action_param=bootloader"),
                  ("set", "tw_reboot_param=bootloader"), ("set", "tw_has_action2=0"),
                  ("set", "tw_text1={@no_os1=No OS Installed! Are you}"),
                  ("set", "tw_text2={@no_osrb=sure you wish to reboot?}"),
                  ("set", "tw_action_text1={@rebooting=Rebooting...}"),
                  ("set", "tw_complete_text1={@rebooting=Rebooting...}"),
                  ("set", "tw_slider_text={@swipe_reboot=Swipe to Reboot}"), ("page", "rebootcheck")]
    rows = [  # bg, icon, chevron, colour, title, sub, actions, condition
        ("asem_row_green", "asem_rowic_reboot_green", "green_ink", "%asem_green_ink%",
         s("rb_system", "System", "النظام"), s("rb_system_s", "Start Android normally", "تشغيل أندرويد بشكل طبيعي"),
         [("set", "tw_back=reboot"), ("page", "reboot_system_routine")], cond("tw_reboot_system", "1")),
        ("asem_row_normal", "asem_rowic_bootl", "muted", "%asem_text%",
         s("rb_bootloader", "Bootloader (fastboot)", "البوتلودر (فاستبوت)"),
         s("rb_bootloader_s", "PC rescue mode - works even if Android is broken", "وضع الإنقاذ عبر الكمبيوتر - يعمل حتى لو تعطل أندرويد"),
         bootloader, cond("tw_reboot_bootloader", "1")),
        ("asem_row_normal", "asem_rowic_bolt", "muted", "%asem_text%",
         s("rb_fastbootd", "Fastbootd", "فاستبوت دي"),
         s("rb_fastbootd_s", "Flash a whole ROM from the PC - no reboot", "تفليش روم كامل من الكمبيوتر - بدون إعادة تشغيل"),
         [("page", "fastboot")], ""),
        ("asem_row_dashed", "asem_rowic_lock", None, "%asem_muted%",
         s("rb_recovery", "Recovery - by hand for now", "الريكفري - يدويا حاليا"),
         s("rb_recovery_s", "Power off, then hold Power + Volume Up", "أطفئ الهاتف ثم اضغط التشغيل + رفع الصوت"), None, ""),
        ("asem_row_dashed", "asem_rowic_lock", None, "%asem_muted%",
         s("rb_edl", "BROM / EDL mode", "وضع BROM / EDL"),
         s("rb_edl_s", "MediaTek: power off, hold Vol Up + Vol Down, plug in USB",
           "ميدياتك: أطفئ الهاتف، اضغط رفع + خفض الصوت، ثم وصل USB"), None, ""),
        ("asem_row_danger", "asem_rowic_power_danger", "danger", "%asem_danger%",
         s("rb_poweroff", "Power off", "إيقاف التشغيل"), s("rb_poweroff_s", "Turn the phone off completely", "إطفاء الهاتف بالكامل"),
         poweroff_actions("reboot"), cond("tw_reboot_poweroff", "1")),
    ]
    for i, (bg, ic, chev, col, title, sub, acts, cc) in enumerate(rows):
        y = 330 + i * 196
        for dirc, rtl in ((LTR, False), (RTL, True)):
            c = conds(dirc, cc)
            if acts:
                b.append(button(40, y, acts, bg, c=c))
            else:
                b.append(image(40, y, bg, 0, c))
            b.append(image(1040 - 88 if rtl else 128, y + 84, ic, 4, c))
            tx, al = (890, 1) if rtl else (190, 0)
            b.append(text(tx, y + 38, title, "asem_f_row_t", col, al, c))
            b.append(text(tx, y + 100, sub, "asem_f_row_s", col if col != "%asem_text%" else "%asem_muted%", al, c))
            if chev:
                b.append(image(90 if rtl else 990, y + 84, ("asem_g_chevrtl_" if rtl else "asem_g_chev_") + chev, 4, c))
    return page("reboot", "".join(b))


# --------------------------------------------------------------------------- Settings
def settings_page():
    b = [header(s("set_title", "Settings", "الإعدادات"), "asem_help_settings")]
    b.append(lead(236, s("set_lead", "Saved automatically and kept after a reboot (when data is readable).",
                         "تحفظ تلقائيا وتبقى بعد إعادة التشغيل (عندما تكون البيانات مقروءة).")))
    segs = [
        ("globe", s("set_lang", "Language", "اللغة"), s("set_lang_s", "Menus and help", "القوائم والمساعدة"),
         [(s("lang_en", "English", "English"), [("set", "tw_language=en"), ("setlanguage", "")], cond("tw_language", "en", "!=")),
          (s("lang_ar", "العربية", "العربية"), [("set", "tw_language=ar"), ("setlanguage", "")], cond("tw_language", "ar", "!="))],
         [cond("tw_language", "ar", "!="), cond("tw_language", "ar")]),
        ("clock", s("set_clock", "Clock", "الساعة"), s("set_clock_s", "Now %tw_time%", "الآن %tw_time%"),
         [(s("clock_12", "12-hour", "12 ساعة"), [("set", "tw_military_time=0")], ""),
          (s("clock_24", "24-hour", "24 ساعة"), [("set", "tw_military_time=1")], "")],
         [cond("tw_military_time", "0"), cond("tw_military_time", "1")]),
        ("palette", s("set_theme", "Theme", "المظهر"), s("set_theme_s", "Dark or light", "داكن أو فاتح"),
         [(s("theme_dark", "Dark", "داكن"), [("set", "asem_light=0"), ("reload", "")], ""),
          (s("theme_light", "Light", "فاتح"), [("set", "asem_light=1"), ("reload", "")], "")],
         [cond("asem_is_light", "0"), cond("asem_is_light", "1")]),
    ]
    links = [
        ("bright", s("set_display", "Display", "الشاشة"), s("set_display_s", "Brightness and screen timeout", "السطوع ومهلة الشاشة"), "settings_screen"),
        ("vib", s("set_vib", "Vibration", "الاهتزاز"), s("set_vib_s", "Buzz on touch and when done", "اهتزاز عند اللمس والانتهاء"), "settings_vibration"),
        ("timer", s("set_tz", "Time zone", "المنطقة الزمنية"), s("set_tz_s", "Makes the clock show your time", "لضبط الساعة على وقتك"), "settings_timezone"),
        ("info", s("set_more", "More settings", "إعدادات أخرى"), s("set_more_s", "All TWRP options", "كل خيارات TWRP"), "settings"),
    ]
    y = 300
    for icon, title, sub, options, on_conds in segs:
        for dirc, rtl in ((LTR, False), (RTL, True)):
            b.append(image(40, y, "asem_setrow", 0, dirc))
            b.append(image(970 if rtl else 110, y + 94, "asem_set_" + icon, 4, dirc))
            tx, al = (900, 1) if rtl else (180, 0)
            b.append(text(tx, y + 44, title, "asem_f_row_t", "%asem_text%", al, dirc))
            b.append(text(tx, y + 104, sub, "asem_f_row_s", "%asem_muted%", al, dirc))
            sx = 60 if rtl else 460
            b.append(image(sx, y + 52, "asem_seg_bg", 0, dirc))
            for k, (label, acts, _) in enumerate(options):
                ox = sx + 6 + k * 276
                b.append(image(ox, y + 60, "asem_seg_on", 0, conds(dirc, on_conds[k])))
                b.append(button(ox, y + 52, acts, w=274, h=84, c=dirc))
                b.append(text(ox + 136, y + 94, label, "asem_f_seg", "%asem_text%", 4, dirc))
        y += 196
    for icon, title, sub, target in links:
        for dirc, rtl in ((LTR, False), (RTL, True)):
            b.append(button(40, y, [("page", target)], "asem_setrow", c=dirc))
            b.append(image(970 if rtl else 110, y + 94, "asem_set_" + icon, 4, dirc))
            tx, al = (900, 1) if rtl else (180, 0)
            b.append(text(tx, y + 44, title, "asem_f_row_t", "%asem_text%", al, dirc))
            b.append(text(tx, y + 104, sub, "asem_f_row_s", "%asem_muted%", al, dirc))
            b.append(image(90 if rtl else 990, y + 94, "asem_g_chevrtl_muted" if rtl else "asem_g_chev_muted", 4, dirc))
        y += 196
    b.append(text(540, 1708, s("about", "ASEM Recovery - based on TWRP %tw_version%",
                                "ASEM Recovery - مبني على TWRP %tw_version%"), "asem_f_row_s", "%asem_muted%", 4))
    return page("asem_settings", "".join(b))


# --------------------------------------------------------------------------- Slots
def slots_page():
    # Real slot status + switching through asem_slot.sh (bootctl / AIDL boot HAL). TWRP's own
    # "setbootslot" only speaks HIDL, failed on this phone and still showed success (R2).
    # The script writes /tmp/asem_slot/* ; TWRP re-checks "fileexists" conditions whenever a
    # page opens, so every button runs the script and then reopens this page.
    F = "/tmp/asem_slot/"
    fe = lambda f: cond("fileexists", F + f)
    b = [header(s("slots_title", "Slots", "الخانات"), "asem_help_slots")]
    b.append(lead(236, s("slots_lead1", "Your phone keeps two copies of the system: A and B.", "هاتفك يحتفظ بنسختين من النظام: A و B.")))
    b.append(lead(282, s("slots_lead2", "The active one starts at power on.", "النسخة النشطة هي التي تعمل عند التشغيل.")))
    yes = cond("tw_has_boot_slots", "1")
    b.append(image(40, 350, "asem_card", 0, yes))
    b.append(text(540, 410, s("slots_running", "Running now: slot %tw_active_slot%", "يعمل الآن: الخانة %tw_active_slot%"),
                  "asem_f_h2", "%asem_text%", 4, yes))
    for L in "AB":
        b.append(text(540, 480, s("slots_next_" + L.lower(), "Next boot: slot " + L, "التشغيل القادم: الخانة " + L),
                      "asem_f_h1", "%asem_accent%", 4, conds(yes, fe("next_" + L))))
    b.append(text(540, 480, s("slots_nohal", "Slot service not available - switching is off",
                              "خدمة الخانات غير متاحة - التبديل متوقف"), "asem_f_body", "%asem_danger%", 4, conds(yes, fe("nohal"))))
    for k, L in enumerate("AB"):
        x = 40 + k * 510
        acts = [("cmd", "sh /system/bin/asem_slot.sh set " + L), ("page", "asem_slots_wait")]
        b.append(button(x, 620, acts, "asem_btn_half", c=yes))
        b.append(text(x + 245, 684, s("slots_make_" + L.lower(), "Make slot %s active" % L, "تفعيل الخانة %s" % L),
                      "asem_f_btn", "%asem_text%", 4, yes))
        b.append(text(x + 245, 784, s("slots_ok_" + L.lower(), "Has a working system", "فيها نظام يعمل"),
                      "asem_f_lead", "%asem_accent%", 4, conds(yes, fe("bootable_" + L))))
        b.append(text(x + 245, 784, s("slots_bad_" + L.lower(), "No working system", "لا يوجد نظام يعمل"),
                      "asem_f_lead", "%asem_danger%", 4, conds(yes, cond("fileexists", F + "nohal", "!="),
                                                                 cond("fileexists", F + "bootable_" + L, "!="))))
    msgs = [("msg_done_A", s("slots_done_a", "Done: slot A starts at the next reboot.", "تم: الخانة A تعمل عند إعادة التشغيل القادمة."), "%asem_accent%"),
            ("msg_done_B", s("slots_done_b", "Done: slot B starts at the next reboot.", "تم: الخانة B تعمل عند إعادة التشغيل القادمة."), "%asem_accent%"),
            ("msg_already_A", s("slots_already_a", "Slot A is already the next-boot slot.", "الخانة A هي بالفعل خانة التشغيل القادم."), "%asem_muted%"),
            ("msg_already_B", s("slots_already_b", "Slot B is already the next-boot slot.", "الخانة B هي بالفعل خانة التشغيل القادم."), "%asem_muted%"),
            ("msg_refused_A", s("slots_refused_a", "Not switched: slot A has no working system.", "لم يتم التبديل: الخانة A لا تحتوي نظاما يعمل."), "%asem_danger%"),
            ("msg_refused_B", s("slots_refused_b", "Not switched: slot B has no working system.", "لم يتم التبديل: الخانة B لا تحتوي نظاما يعمل."), "%asem_danger%"),
            ("msg_fail", s("slots_fail", "Switch failed - nothing was changed.", "فشل التبديل - لم يتغير شيء."), "%asem_danger%"),
            ("msg_nohal", s("slots_msg_nohal", "Slot service not available - nothing was changed.", "خدمة الخانات غير متاحة - لم يتغير شيء."), "%asem_danger%")]
    for f, txt, col in msgs:
        b.append(text(540, 850, txt, "asem_f_body", col, 4, conds(yes, fe(f))))
    b.append(image(40, 910, "asem_card_warn", 0, yes))
    b.append(bidi_text(80, 1000, 942, s("slots_warn1", "Only switch to a slot that has a working system.",
                                         "بدل فقط إلى خانة فيها نظام يعمل."), "asem_f_body", "%asem_warn%", yes))
    b.append(bidi_text(80, 1000, 994, s("slots_warn2", "If it does not boot, come back here and switch back.",
                                         "إذا لم يعمل، ارجع هنا وبدل مرة أخرى."), "asem_f_lead", "%asem_warn%", yes))
    b.append(bidi_text(80, 1000, 1040, s("slots_warn3", "Your data is shared by both slots.",
                                          "بياناتك مشتركة بين الخانتين."), "asem_f_lead", "%asem_warn%", yes))
    b.append(button(122, 1200, [("page", "reboot")], "asem_btn_primary", c=yes))
    b.append(text(540, 1264, s("reboot_to", "Reboot to...", "إعادة التشغيل إلى..."), "asem_f_btn", "%asem_ink%", 4, yes))
    b.append(text(540, 430, s("slots_none", "This phone has no A/B slots", "هذا الهاتف لا يحتوي على خانات A/B"),
                  "asem_f_h2", "%asem_muted%", 4, cond("tw_has_boot_slots", "0")))
    return page("asem_slots", "".join(b))


def slots_wait_page():
    # reopening asem_slots from here makes TWRP re-check its "fileexists" conditions
    return page("asem_slots_wait", page_action("", ("page", "asem_slots")))


# --------------------------------------------------------------------------- ASEM Transfer
def transfer_page():
    b = [header(s("tr_title", "ASEM Transfer", "نقل ASEM"), "asem_help_transfer")]
    b.append(lead(236, s("tr_lead", "Copy files between your PC and the phone with a USB cable.",
                         "انسخ الملفات بين الكمبيوتر والهاتف بكابل USB.")))
    on, off = cond("tw_mtp_enabled", "1"), cond("tw_mtp_enabled", "0")
    b.append(image(40, 330, "asem_card_tall"))
    b.append(text(540, 400, s("tr_on", "File transfer is ON", "نقل الملفات يعمل"), "asem_f_h2", "%asem_accent%", 4, on))
    b.append(text(540, 400, s("tr_off", "File transfer is OFF", "نقل الملفات متوقف"), "asem_f_h2", "%asem_muted%", 4, off))
    b.append(text(540, 480, s("tr_l1", "On the PC open \"Infinix X6855\" in File Explorer.",
                              "على الكمبيوتر افتح \"Infinix X6855\" في مستكشف الملفات."), "asem_f_body", "%asem_text%", 4))
    b.append(text(540, 532, s("tr_l2", "Drop the ROM into Internal Storage.", "ضع ملف الروم في الذاكرة الداخلية."),
                  "asem_f_lead", "%asem_muted%", 4))
    b.append(text(540, 582, s("tr_l3", "Then use Install to flash it.", "ثم استخدم تثبيت لتفليشه."),
                  "asem_f_lead", "%asem_muted%", 4))
    b.append(button(40, 780, [("startmtp", "")], "asem_btn_half_primary", c=off))
    b.append(text(285, 844, s("tr_turn_on", "Turn on", "تشغيل"), "asem_f_btn", "%asem_ink%", 4, off))
    b.append(button(40, 780, [("stopmtp", "")], "asem_btn_half", c=on))
    b.append(text(285, 844, s("tr_turn_off", "Turn off", "إيقاف"), "asem_f_btn", "%asem_text%", 4, on))
    b.append(button(550, 780, [("page", "sideload")], "asem_btn_half"))
    b.append(text(795, 844, s("t_sideload", "ADB Sideload"), "asem_f_btn", "%asem_text%", 4))
    b.append(image(40, 960, "asem_card_warn"))
    b.append(bidi_text(80, 1000, 992, s("tr_w1", "Data encrypted? The PC sees scrambled names.",
                                        "البيانات مشفرة؟ سيظهر للكمبيوتر أسماء غير مفهومة."), "asem_f_body", "%asem_warn%"))
    b.append(bidi_text(80, 1000, 1044, s("tr_w2", "Use ADB Sideload or a USB stick (OTG) instead.",
                                         "استخدم سايدلود ADB أو فلاشة USB بدلا من ذلك."), "asem_f_lead", "%asem_warn%"))
    b.append(bidi_text(80, 1000, 1090, s("tr_w3", "RAM transfer for encrypted phones: next version.",
                                         "النقل عبر الذاكرة للهواتف المشفرة: في الإصدار القادم."), "asem_f_lead", "%asem_warn%"))
    return page("asem_transfer", "".join(b))


# --------------------------------------------------------------------------- Unlock your data (decrypt)
# Asem's design: ask which screen lock the phone uses (Pattern / PIN / Password / No lock),
# then open the matching TWRP input. TWRP's own "decrypt" page routes here first while
# asem_dec_chosen=0; a wrong entry (tw_password_fail=1) comes back here with a message.
# TWRP lock types (tw_crypto_pwtype): 0 none, 1 password, 2 pattern, 3 PIN.
# tw_crypto_pwtype_0 = the type TWRP detected for user 0 -> highlighted button.
# "No lock" = TWRP's default password "!" (what TWRP itself tries at start-up).
DECRYPT_CHOICES = [  # pwtype, x, y, label
    ("2", 40, 820, s("dc_pattern", "Pattern", "نمط")),
    ("3", 550, 820, s("dc_pin", "PIN (numbers)", "رمز PIN (أرقام)")),
    ("1", 40, 970, s("dc_password", "Password", "كلمة مرور")),
    ("0", 550, 970, s("dc_nolock", "No lock", "بدون قفل")),
]


def decrypt_page():
    b = [header(s("dc_title", "Unlock your data", "فتح بياناتك"))]
    b.append(lead(236, s("dc_lead", "Your data is encrypted. Choose the screen lock you use on this phone.",
                         "بياناتك مشفرة. اختر قفل الشاشة الذي تستخدمه في هذا الهاتف.")))
    b.append(image(40, 300, "asem_card_warn"))
    b.append(bidi_text(80, 1000, 340, s("dc_w1", "Use the EXACT PIN, pattern or password of this phone.",
                                        "استخدم نفس رمز PIN أو النمط أو كلمة المرور تماما."), "asem_f_body", "%asem_warn%"))
    b.append(bidi_text(80, 1000, 386, s("dc_w2", "A wrong entry shows Wrong input. Nothing changes - try again.",
                                        "الإدخال الخاطئ يظهر إدخال خاطئ. لا يتغير شيء - حاول مرة أخرى."), "asem_f_lead", "%asem_warn%"))
    b.append(bidi_text(80, 1000, 432, s("dc_w3", "Choose No lock only if the phone has no screen lock.",
                                        "اختر بدون قفل فقط إذا لم يكن للهاتف قفل شاشة."), "asem_f_lead", "%asem_warn%"))
    fail = cond("tw_password_fail", "1")
    b.append(bidi_text(44, 1036, 560, s("dc_wrong", "Wrong input - that did not unlock the data.",
                                        "إدخال خاطئ - لم يفتح ذلك البيانات."), "asem_f_h2", "%asem_danger%", fail))
    b.append(bidi_text(44, 1036, 614, s("dc_wrong2", "Check your lock type and try again.",
                                        "تأكد من نوع القفل وحاول مرة أخرى."), "asem_f_lead", "%asem_danger%", fail))
    for val, lab in (("1", s("dc_det_password", "Detected on this phone: Password", "المكتشف في هذا الهاتف: كلمة مرور")),
                     ("2", s("dc_det_pattern", "Detected on this phone: Pattern", "المكتشف في هذا الهاتف: نمط")),
                     ("3", s("dc_det_pin", "Detected on this phone: PIN", "المكتشف في هذا الهاتف: رمز PIN"))):
        b.append(bidi_text(44, 1036, 700, lab, "asem_f_body", "%asem_accent%", cond("tw_crypto_pwtype_0", val)))
    for pw, x, y, lab in DECRYPT_CHOICES:
        if pw == "0":
            acts = [("set", "tw_crypto_user_id=0"), ("set", "tw_crypto_password=!"), ("set", "tw_password_fail=0"),
                    ("set", "asem_dec_chosen=1"), ("page", "trydecrypt")]
        else:
            acts = [("set", "tw_crypto_user_id=0"), ("set", "tw_crypto_password="), ("set", "tw_password_fail=0"),
                    ("set", "tw_crypto_pwtype=" + pw), ("set", "asem_dec_chosen=1"), ("page", "decrypt")]
        for side, bx in ((LTR, x), (RTL, 590 - x)):  # Arabic: grid mirrored like the Home tiles
            det = conds(side, cond("tw_crypto_pwtype_0", pw))
            other = conds(side, cond("tw_crypto_pwtype_0", pw, "!="))
            b.append(button(bx, y, acts, "asem_btn_half_primary", c=det))
            b.append(button(bx, y, acts, "asem_btn_half", c=other))
            b.append(text(bx + 245, y + 64, lab, "asem_f_btn", "%asem_ink%", 4, det))
            b.append(text(bx + 245, y + 64, lab, "asem_f_btn", "%asem_text%", 4, other))
    return page("asem_decrypt", "".join(b))


# --------------------------------------------------------------------------- help sheets
HELP = {
    "install": (s("hp_install", "How to install a ROM", "كيف تثبت روم"), [
        (s("hp_install_1", "Back up first: Home > Backup", "انسخ احتياطيا أولا: الرئيسية > نسخ احتياطي"),
         s("hp_install_1b", "Boot, Vendor Boot and NVRAM are enough.", "Boot و Vendor Boot و NVRAM تكفي.")),
        (s("hp_install_2", "Wipe > Factory reset when changing ROM", "مسح > ضبط المصنع عند تغيير الروم"), None),
        (s("hp_install_3", "Tap the ROM zip, then swipe to flash", "اضغط على ملف الروم ثم اسحب للتفليش"), None),
        (s("hp_install_4", "Do not unplug or power off until Done", "لا تفصل أو تطفئ حتى تظهر كلمة تم"), None),
        (s("hp_install_5", "Add GApps, then Magisk last", "أضف GApps ثم Magisk في الأخير"),
         s("hp_install_5b", "Use Add more zips to queue them.", "استخدم إضافة ملفات لوضعها في الطابور.")),
    ], s("hp_install_tip", "No file on the phone? Use ASEM Transfer or Fastboot.",
         "لا يوجد ملف على الهاتف؟ استخدم نقل ASEM أو فاستبوت.")),
    "wipe": (s("hp_wipe", "Which wipe do I need?", "أي مسح أحتاج؟"), [
        (s("hp_wipe_1", "New ROM: Factory reset", "روم جديد: ضبط المصنع"),
         s("hp_wipe_1b", "Removes apps and settings, keeps your files.", "يحذف التطبيقات والإعدادات ويحتفظ بملفاتك.")),
        (s("hp_wipe_2", "Problems with encryption: Format Data", "مشاكل في التشفير: فرمتة البيانات"),
         s("hp_wipe_2b", "Erases EVERYTHING, including photos.", "يمسح كل شيء بما فيه الصور.")),
        (s("hp_wipe_3", "Slow or crashing apps: Dalvik / ART cache", "تطبيقات بطيئة أو تتوقف: كاش Dalvik / ART"), None),
    ], s("hp_wipe_tip", "Never wipe System or Vendor unless you flash a full ROM.",
         "لا تمسح System أو Vendor إلا إذا كنت ستفلش روم كامل.")),
    "backup": (s("hp_backup", "How backup works", "كيف يعمل النسخ الاحتياطي"), [
        (s("hp_backup_1", "Tick what to save", "اختر ما تريد حفظه"),
         s("hp_backup_1b", "Boot + Vendor Boot + NVRAM = safe minimum.", "Boot + Vendor Boot + NVRAM = الحد الآمن.")),
        (s("hp_backup_2", "Choose where: Internal storage or USB OTG", "اختر المكان: الذاكرة الداخلية أو USB OTG"), None),
        (s("hp_backup_3", "Swipe and wait until it says Done", "اسحب وانتظر حتى تظهر كلمة تم"), None),
        (s("hp_backup_4", "Copy the backup to your PC too", "انسخ النسخة إلى الكمبيوتر أيضا"),
         s("hp_backup_4b", "A wipe can delete backups on the phone.", "المسح قد يحذف النسخ الموجودة على الهاتف.")),
    ], s("hp_backup_tip", "NVRAM holds your IMEI. Keep that backup safe.", "NVRAM يحتوي على IMEI. احتفظ بهذه النسخة بأمان.")),
    "restore": (s("hp_restore", "How restore works", "كيف تعمل الاستعادة"), [
        (s("hp_restore_1", "Pick a backup folder from the list", "اختر مجلد النسخة من القائمة"), None),
        (s("hp_restore_2", "Tick only the parts you want back", "اختر فقط الأجزاء التي تريد إرجاعها"), None),
        (s("hp_restore_3", "Swipe to restore, then reboot to System", "اسحب للاستعادة ثم أعد التشغيل إلى النظام"), None),
    ], s("hp_restore_tip", "Restore backups made on this same phone only.", "استعد فقط النسخ المأخوذة من نفس الهاتف.")),
    "mount": (s("hp_mount", "What mount means", "ما معنى التركيب"), [
        (s("hp_mount_1", "Ticked = open: its files can be read", "محدد = مفتوح: يمكن قراءة ملفاته"), None),
        (s("hp_mount_2", "Untick before you unplug a USB stick", "ألغِ التحديد قبل فصل فلاشة USB"), None),
        (s("hp_mount_3", "Enable MTP to see the phone on your PC", "فعّل MTP لترى الهاتف على الكمبيوتر"), None),
    ], s("hp_mount_tip", "System and Vendor are read-only on this phone.", "System و Vendor للقراءة فقط على هذا الهاتف.")),
    "sideload": (s("hp_sideload", "ADB Sideload", "سايدلود ADB"), [
        (s("hp_sideload_1", "Swipe to start sideload here", "اسحب لبدء السايدلود هنا"), None),
        (s("hp_sideload_2", "On the PC run: adb sideload rom.zip", "على الكمبيوتر نفذ: adb sideload rom.zip"), None),
        (s("hp_sideload_3", "Wait for Done, then reboot", "انتظر حتى تظهر تم ثم أعد التشغيل"), None),
    ], s("hp_sideload_tip", "Works even when the phone storage is encrypted.", "يعمل حتى لو كانت ذاكرة الهاتف مشفرة.")),
    "fastboot": (s("hp_fastboot", "Fastboot from the PC", "فاستبوت من الكمبيوتر"), [
        (s("hp_fastboot_1", "Tap Enable Fastboot", "اضغط تفعيل فاستبوت"), None),
        (s("hp_fastboot_2", "On the PC: fastboot devices", "على الكمبيوتر: fastboot devices"), None),
        (s("hp_fastboot_3", "Flash: fastboot flash system system.img", "تفليش: fastboot flash system system.img"), None),
        (s("hp_fastboot_4", "Tap Enable ADB when you are finished", "اضغط تفعيل ADB عند الانتهاء"), None),
    ], s("hp_fastboot_tip", "This is fastbootd: it can flash system, vendor, product.",
         "هذا فاستبوت دي: يمكنه تفليش system و vendor و product.")),
    "reboot": (s("hp_reboot", "Where can the phone go?", "إلى أين يمكن أن يذهب الهاتف؟"), [
        (s("hp_reboot_1", "System: normal Android", "النظام: أندرويد العادي"), None),
        (s("hp_reboot_2", "Bootloader: fastboot rescue for the PC", "البوتلودر: فاستبوت للإنقاذ عبر الكمبيوتر"), None),
        (s("hp_reboot_3", "Fastbootd: flash a ROM from the PC", "فاستبوت دي: تفليش روم من الكمبيوتر"), None),
        (s("hp_reboot_4", "Recovery: power off, Power + Volume Up", "الريكفري: أطفئ الهاتف، التشغيل + رفع الصوت"), None),
    ], s("hp_reboot_tip", "Recovery from software is off on purpose for this phone.",
         "التشغيل إلى الريكفري من البرنامج معطل عمدا لهذا الهاتف.")),
    "slots": (s("hp_slots", "What are slots?", "ما هي الخانات؟"), [
        (s("hp_slots_1", "A and B are two copies of the system", "A و B نسختان من النظام"), None),
        (s("hp_slots_2", "Updates install to the other slot", "التحديثات تثبت في الخانة الأخرى"), None),
        (s("hp_slots_3", "Switch only if that slot can boot", "بدل فقط إذا كانت الخانة تعمل"), None),
    ], s("hp_slots_tip", "Not sure? Leave the active slot as it is.", "غير متأكد؟ اترك الخانة النشطة كما هي.")),
    "transfer": (s("hp_transfer", "Copy files from the PC", "نسخ الملفات من الكمبيوتر"), [
        (s("hp_transfer_1", "Connect a USB cable", "وصل كابل USB"), None),
        (s("hp_transfer_2", "Turn file transfer on", "شغل نقل الملفات"), None),
        (s("hp_transfer_3", "Open \"Infinix X6855\" on the PC", "افتح \"Infinix X6855\" على الكمبيوتر"), None),
        (s("hp_transfer_4", "Copy the ROM, then go to Install", "انسخ الروم ثم اذهب إلى تثبيت"), None),
    ], s("hp_transfer_tip", "Scrambled names = data encrypted: use ADB Sideload.",
         "أسماء غير مفهومة = بيانات مشفرة: استخدم سايدلود ADB.")),
    "settings": (s("hp_settings", "Settings", "الإعدادات"), [
        (s("hp_settings_1", "Language: English or Arabic", "اللغة: الإنجليزية أو العربية"), None),
        (s("hp_settings_2", "Clock: 12-hour or 24-hour", "الساعة: 12 أو 24 ساعة"), None),
        (s("hp_settings_3", "Theme: dark or light", "المظهر: داكن أو فاتح"), None),
    ], s("hp_settings_tip", "Settings are saved on the phone storage.", "الإعدادات تحفظ في ذاكرة الهاتف.")),
}


def help_page(key):
    title, steps, tip = HELP[key]
    b = [fill(0, 0, 1080, 1920, "%asem_dim%")]
    b.append(button(0, 0, [("overlay", "")], w=1080, h=600))
    b.append(image(0, 600, "asem_sheet"))
    b.append(bidi_text(60, 1020, 650, title, "asem_f_h2", "%asem_text%"))
    y = 760
    for i, (line, sub) in enumerate(steps):
        for dirc, rtl in ((LTR, False), (RTL, True)):
            dx = 992 if rtl else 88
            b.append(image(dx, y + 22, "asem_step", 4, dirc))
            b.append(text(dx, y + 22, str(i + 1), "asem_f_step", "%asem_ink%", 4, dirc))
            tx, al = (948, 1) if rtl else (132, 0)
            b.append(text(tx, y + 2, line, "asem_f_body", "%asem_text%", al, dirc))
            if sub:
                b.append(text(tx, y + 48, sub, "asem_f_row_s", "%asem_muted%", al, dirc))
        y += 112 if sub else 80
    b.append(bidi_text(60, 1020, y + 30, tip, "asem_f_lead", "%asem_warn%"))
    b.append(button(122, 1500, [("overlay", "")], "asem_btn_primary"))
    b.append(text(540, 1564, s("got_it", "Got it", "فهمت"), "asem_f_btn", "%asem_ink%", 4))
    b.append(key_action("back", ("overlay", "")))
    b.append(key_action("home", ("overlay", ""), ("key", "home")))
    return '<page name="asem_help_%s">%s</page>' % (key, "".join(b))


# TWRP pages that get a "?" button (page -> help key)
HELP_BUTTONS = {"install": "install", "wipe": "wipe", "advancedwipe": "wipe", "backup": "backup",
                "restore": "restore", "mount": "mount", "sideload": "sideload", "fastboot": "fastboot"}

# Arabic for the most visible stock TWRP strings
TWRP_AR = {
    "system": "النظام", "vendor": "Vendor", "boot": "Boot", "data": "البيانات", "data_backup": "البيانات (بدون الذاكرة)",
    "internal": "الذاكرة الداخلية", "usbotg": "USB OTG", "dalvik": "كاش Dalvik / ART",
    "install_btn": "تثبيت", "wipe_btn": "مسح", "backup_btn": "نسخ احتياطي", "restore_btn": "استعادة",
    "mount_btn": "تركيب", "settings_btn": "الإعدادات", "advanced_btn": "متقدم", "reboot_btn": "إعادة التشغيل",
    "copy_log_btn": "نسخ السجل", "install_zip_btn": "تثبيت ملف zip", "install_image_btn": "تثبيت صورة",
    "install_select_file_hdr": "اختر ملفا", "adb_sideload_btn": "سايدلود ADB", "install_hdr": "تثبيت",
    "select_storage_hdr": "اختر الذاكرة", "select_storage_btn": "اختر الذاكرة", "zip_queue": "الطابور:",
    "failed": "فشل", "successful": "نجح", "flash_image_select": "اختر القسم لتفليش الصورة:",
    "swipe_wipe": "اسحب للمسح", "rebooting": "جار إعادة التشغيل...", "swipe_reboot": "اسحب لإعادة التشغيل",
    "swipe_flash": "اسحب لتأكيد التفليش", "cancel_btn": "إلغاء", "wipe_hdr": "مسح",
    "factory_reset_hdr": "ضبط المصنع", "factory_reset1": "يمسح البيانات والكاش و Dalvik",
    "factory_reset2": "(بدون الذاكرة الداخلية)", "advanced_wipe_btn": "مسح متقدم",
    "swipe_format_data": "اسحب لفرمتة البيانات", "wipe_complete": "اكتمل المسح", "format_data_hdr": "فرمتة البيانات",
    "format_data_btn": "فرمتة البيانات", "back_btn": "رجوع", "backup_hdr": "نسخ احتياطي", "storage": "الذاكرة:",
    "current_boot_slot": "الخانة الحالية: %tw_active_slot%", "boot_slot_a": "الخانة A", "boot_slot_b": "الخانة B",
    "changing_boot_slot": "جار تغيير الخانة", "swipe_backup": "اسحب للنسخ الاحتياطي", "partitions": "الأقسام:",
    "restore_hdr": "استعادة", "swipe_restore": "اسحب للاستعادة", "mount_hdr": "تركيب", "usb_storage_hdr": "ذاكرة USB",
    "turning_off": "جار الإطفاء...", "swipe_power_off": "اسحب للإطفاء", "settings_hdr": "الإعدادات",
    "advanced_hdr": "متقدم", "fix_context_btn": "إصلاح السياقات", "file_manager_btn": "مدير الملفات",
    "terminal_btn": "الطرفية", "swipe_to_confirm": "اسحب للتأكيد", "decrypt_data_hdr": "فك تشفير البيانات",
    "decrypt_data_enter_pass": "أدخل كلمة المرور.", "reboot_hdr": "إعادة التشغيل", "ok_btn": "موافق",
    "update_part_details": "جار تحديث معلومات الأقسام...", "done": "تم.",
}


# --------------------------------------------------------------------------- templates (ui.xml)
STATUS = (
    '<text color="%asem_text%"><font resource="asem_f_status"/><placement x="44" y="16"/><text>%tw_time%</text></text>'
    # battery: % + outline, top-right. Only tw_no_battery_percent as condition: tw_battery is
    # computed on read and never sends a change notification, so extra numeric conditions
    # were evaluated once at page load (no reading yet) and hid it for good (R1).
    '<text color="%asem_text%"><condition var1="tw_no_battery_percent" var2="0"/>'
    '<font resource="asem_f_status"/><placement x="978" y="16" placement="1"/><text>%tw_battery%</text></text>'
    + "".join('<fill color="%%asem_text%%"><condition var1="tw_no_battery_percent" var2="0"/>'
              '<placement x="%d" y="%d" w="%d" h="%d"/></fill>' % r
              for r in ((990, 24, 44, 3), (990, 45, 44, 3), (990, 24, 3, 24), (1031, 24, 3, 24), (1034, 31, 5, 10)))
    +
    '<text color="%asem_muted%"><condition var1="tw_no_cpu_temp" var2="0"/><font resource="asem_f_status"/>'
    '<placement x="840" y="16" placement="1"/><text>%tw_cpu_temp%&#xB0;C</text></text>')
NAVBAR = (
    '<fill color="%asem_surface%"><condition var1="tw_busy" var2="0"/>'
    '<placement x="0" y="%navbar_y%" w="%screen_width%" h="%navbar_height%"/></fill>'
    '<button><condition var1="tw_busy" var2="0"/><placement x="%back_button_x%" y="%navbar_btn_y%" placement="4"/>'
    '<image resource="back"/><action function="key">back</action></button>'
    '<button><condition var1="tw_busy" var2="0"/><placement x="%center_x%" y="%navbar_btn_y%" placement="4"/>'
    '<image resource="%home_res%"/><action function="key">home</action></button>'
    '<button><condition var1="tw_busy" var2="0"/><placement x="%console_button_x%" y="%navbar_btn_y%" placement="4"/>'
    '<image resource="console"/><action function="overlay">slideout</action></button>'
    '<action><touch key="power"/><action function="togglebacklight"/></action>'
    '<action><touch key="power+voldown"/><action function="screenshot"/></action>')


def templates():
    twrp_page = ('<template name="page"><background color="%background_color%"/>'
                 '<image><condition var1="tw_busy" var2="1"/><image resource="logo"/><placement x="0" y="0"/></image>'
                 '<button><condition var1="tw_busy" var2="0"/><placement x="0" y="0"/><image resource="logo"/>'
                 '<action function="key">home</action></button>' + STATUS + NAVBAR.replace("%home_res%", "home") +
                 '</template>')
    asem_page = ('<template name="asem_page"><background color="%background_color%"/>' + STATUS +
                 NAVBAR.replace("%home_res%", "home") + '</template>')
    asem_home = ('<template name="asem_home"><background color="%background_color%"/>' + STATUS +
                 NAVBAR.replace("%home_res%", "asem_nav_home_on") + '</template>')
    return twrp_page, asem_page + asem_home


# --------------------------------------------------------------------------- ui.xml generation
def make_ui(src, t):
    p = PALETTES[t]
    x = src
    x = re.sub(r"<title>.*?</title>", "<title>ASEM Recovery</title>", x)
    x = re.sub(r"<author>.*?</author>", "<author>Asemayyad (based on TeamWin)</author>", x)
    x = re.sub(r"<description>.*?</description>", "<description>ASEM Recovery %s theme</description>" %
               ("dark" if t == "d" else "light"), x)
    # fonts: replace the whole font list
    font_xml = "\n".join('\t\t<font name="%s" filename="%s" size="%d"/>' % f for f in FONTS)
    x, n = re.subn(r"[ \t]*<font name=[^\n]*\n", "", x)
    assert n >= 4, "font lines not found"
    x = x.replace("\t<resources>\n", "\t<resources>\n" + font_xml + "\n", 1)
    # stock images -> themed files
    for name in THEMED_STOCK:  # matched by file name (e.g. resource progress_full -> file progress_fill)
        x, n = re.subn(r'(<image name="[^"]+" filename=")%s(")' % name, r"\g<1>%s_%s\2" % (name, t), x)
        assert n == 1, "stock image not found: " + name
    x, n = re.subn(r'<animation name="progress" filename="indeterminate"/>',
                   '<animation name="progress" filename="asem_ind_%s"/>' % t, x)
    assert n == 1
    res = []
    for name in THEMED_ASEM:
        ra = "" if name in STRETCH else ' retainaspect="1"'
        res.append('\t\t<image name="%s" filename="%s_%s"%s/>' % (name, name, t, ra))
    theme_btn = "asem_btn_sun" if t == "d" else "asem_btn_moon"
    res.append('\t\t<image name="asem_btn_theme" filename="%s_%s" retainaspect="1"/>' % (theme_btn, t))
    for name in SHARED_IMAGES:
        if name != "logo":
            res.append('\t\t<image name="%s" filename="%s" retainaspect="1"/>' % (name, name))
    x = x.replace("\t</resources>", "\n".join(res) + "\n\t</resources>", 1)
    # colours
    cmap = {"background_color": p["bg"], "accent_color": p["accent"], "accent_color_semitransparent": p["accent"] + "30",
            "text_color": p["text"], "text_button_color": p["text"], "text_success_color": p["accent"],
            "text_fail_color": p["danger"], "highlight_color": p["highlight"], "caps_highlight_color": p["highlight"],
            "semi_transparent": p["semi"], "warning": p["warn"], "error": p["danger"], "highlight": p["accent"]}
    for k, v in cmap.items():
        x, n = re.subn(r'(<variable name="%s" value=")[^"]*(")' % k, r"\g<1>%s\2" % v, x)
        assert n == 1, "colour variable not found: " + k
    # placeholders the build only replaces in ui.xml - make them concrete in both files
    for ph, val in (("{statusicons_align}", "15"), ("{clock_12_pos}", "0"), ("{clock_24_pos}", "0"),
                    ("{cpu_pos}", "0"), ("{battery_pos}", "0")):
        x = x.replace(ph, val)
    asem_vars = {"asem_text": p["text"], "asem_muted": p["muted"], "asem_accent": p["accent"], "asem_ink": p["ink"],
                 "asem_warn": p["warn"], "asem_danger": p["danger"], "asem_info": p["info"],
                 "asem_green_ink": p["green_ink"], "asem_surface": p["surface"], "asem_dim": p["dim"],
                 "button_text_color": p["ink"], "asem_is_light": "1" if t == "l" else "0",
                 "asem_target_light": "0" if t == "l" else "1"}
    v = "\n".join('\t\t<variable name="%s" value="%s"/>' % kv for kv in asem_vars.items())
    v += '\n\t\t<variable name="asem_light" value="%s" persist="1"/>' % ("1" if t == "l" else "0")
    v += '\n\t\t<variable name="asem_dec_chosen" value="0"/>'
    x = x.replace("\t</variables>", v + "\n\t</variables>", 1)
    # templates: replace TWRP's "page" template, add ASEM ones
    twrp_page, asem_tpl = templates()
    x, n = re.subn(r'<template name="page">.*?</template>', lambda m: twrp_page, x, count=1, flags=re.S)
    assert n == 1, "page template not found"
    x = x.replace("\t</templates>", asem_tpl + "\n\t</templates>", 1)
    return x


SPLASH = """<?xml version="1.0"?>
<recovery>
	<details>
		<resolution width="1080" height="1920"/>
		<author>Asemayyad</author>
		<title>ASEM Recovery</title>
		<description>splash screen</description>
		<themeversion>{themeversion}</themeversion>
	</details>

	<resources>
		<image name="asem_logo_splash" filename="asem_logo_splash" retainaspect="1"/>
		<font name="font_m" filename="Tajawal-Medium.ttf" size="42"/>
		<font name="asem_f_cap" filename="Tajawal-Bold.ttf" size="40"/>
		<font name="asem_small" filename="Tajawal-Regular.ttf" size="28"/>
	</resources>

	<pages>
		<page name="splash">
			<background color="#0E1116"/>
			<image>
				<image resource="asem_logo_splash"/>
				<placement x="540" y="820" placement="4"/>
			</image>
			<text color="#8FE3B0">
				<font resource="asem_f_cap"/>
				<placement x="540" y="1120" placement="4"/>
				<text>R E C O V E R Y</text>
			</text>
			<text color="#6E7889">
				<font resource="asem_small"/>
				<placement x="540" y="1760" placement="4"/>
				<text>based on TWRP %tw_version%</text>
			</text>
		</page>
	</pages>
</recovery>
"""


# --------------------------------------------------------------------------- languages
def language_files(en_src):
    en = en_src.replace("RobotoCondensed-Regular.ttf", "Tajawal-Medium.ttf")
    lines = []
    for sid, txt in EN.items():
        lines.append('\t\t<string name="%s">%s</string>' % (sid, escape(visual(txt))))
    en, n = re.subn(r"(\n\t</resources>)", "\n\t\t<!-- ASEM Recovery -->\n" + "\n".join(lines) + r"\1", en, count=1)
    assert n == 1, "en.xml resources end not found"
    ar = ['<?xml version="1.0" encoding="utf-8"?>', "<language>",
          "\t<display>%s</display>" % escape(visual("العربية")), "\t<resources>"]
    for fn in ("font_l", "font_m", "font_s"):
        ar.append('\t\t<resource name="%s" type="fontoverride" filename="Tajawal-Medium.ttf" scale="100" />' % fn)
    ar.append('\t\t<resource name="fixed" type="fontoverride" filename="DroidSansMono.ttf" scale="100" />')
    for sid, txt in list(TWRP_AR.items()) + list(AR.items()):
        ar.append('\t\t<string name="%s">%s</string>' % (sid, escape(visual(txt))))
    ar += ["\t</resources>", "</language>", ""]
    return en, "\n".join(ar)


# --------------------------------------------------------------------------- portrait.xml
def patch_portrait(src):
    x = src
    for name in ("main2", "reboot"):
        x, n = re.subn(r'\t\t<page name="%s">.*?\n\t\t</page>\n' % name, "", x, count=1, flags=re.S)
        assert n == 1, "page not found: " + name
    for pg, key in HELP_BUTTONS.items():
        # TWRP page titles can be long, so "?" goes to the free right end of the navbar
        btn = ('<button><condition var1="tw_busy" var2="0"/><placement x="1010" y="%navbar_btn_y%" placement="4"/>'
               '<image resource="asem_btn_help"/><action function="overlay">asem_help_' + key + '</action></button>')
        x, n = re.subn(r'(<page name="%s">\s*<template name="page"/>)' % pg, lambda m: m.group(1) + btn, x, count=1)
        assert n == 1, "help button target not found: " + pg
    # decrypt: route to the ASEM lock-type chooser first (until a type was chosen)
    i = x.index('<page name="decrypt">'); j = x.index("</page>", i)
    d = x[i:j].replace('<template name="page"/>', '<template name="page"/>\n\t\t\t<action>'
                       '<condition var1="asem_dec_chosen" var2="0"/><action function="page">asem_decrypt</action></action>', 1)
    for t in ("2", "3"):
        old = '<condition var1="tw_crypto_pwtype" var2="%s"/>' % t
        assert d.count(old) == 1, "decrypt routing " + t
        d = d.replace(old, '<conditions>%s<condition var1="asem_dec_chosen" var2="1"/></conditions>' % old, 1)
    x = x[:i] + d + x[j:]
    # trydecrypt: on failure go back through the chooser (it shows "Wrong input")
    i = x.index('<page name="trydecrypt">'); j = x.index("</page>", i)
    old = '<action function="set">tw_password_fail=1</action>'
    assert x[i:j].count(old) == 1, "trydecrypt failure branch"
    x = x[:i] + x[i:j].replace(old, old + '\n\t\t\t\t\t<action function="set">asem_dec_chosen=0</action>', 1) + x[j:]
    pages = [home_page(), reboot_page(), settings_page(), slots_page(), transfer_page(), decrypt_page(), slots_wait_page()]
    pages += [help_page(k) for k in HELP]
    x, n = re.subn(r"(\n\t</pages>)", "\n<!-- ASEM Recovery pages -->\n" + "\n".join(pages) + r"\1", x, count=1)
    assert n == 1, "</pages> not found"
    return x


# --------------------------------------------------------------------------- C++ (light theme file)
CPP = [
    ("gui/pages.cpp", 'ReloadPackage("TWRP", TWRES "ui.xml")', 1),
    ("gui/gui.cpp", 'PageManager::LoadPackage("TWRP", TWRES "ui.xml", "main")', 1),
]
LIGHT_EXPR = '(DataManager::GetIntValue("asem_light") == 1 ? TWRES "ui_light.xml" : TWRES "ui.xml")'


def patch_cpp(rec):
    for rel, old, count in CPP:
        path = os.path.join(rec, rel)
        src = read(path)
        if "asem_light" in src:
            continue
        n = src.count(old)
        assert n == count, "%s: expected %d x %r, found %d" % (rel, count, old, n)
        write(path, src.replace(old, old.replace('TWRES "ui.xml"', LIGHT_EXPR)))


# --------------------------------------------------------------------------- io
def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, data):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)


def apply(root):
    rec = os.path.join(root, "bootable", "recovery")
    th = os.path.join(rec, "gui", "theme")
    hd, common = os.path.join(th, "portrait_hdpi"), os.path.join(th, "common")
    marker = os.path.join(hd, "ASEM_THEME")
    if os.path.exists(marker):
        sys.exit("ASEM theme already applied - reset bootable/recovery first (git checkout + clean)")
    ui_src = read(os.path.join(hd, "ui.xml"))
    write(os.path.join(hd, "ui.xml"), make_ui(ui_src, "d"))
    write(os.path.join(hd, "ui_light.xml"), make_ui(ui_src, "l"))
    write(os.path.join(hd, "splash.xml"), SPLASH)
    write(os.path.join(common, "portrait.xml"), patch_portrait(read(os.path.join(common, "portrait.xml"))))
    en, ar = language_files(read(os.path.join(common, "languages", "en.xml")))
    for f in os.listdir(os.path.join(common, "languages")):
        os.remove(os.path.join(common, "languages", f))
    write(os.path.join(common, "languages", "en.xml"), en)
    write(os.path.join(common, "languages", "ar.xml"), ar)
    for f in os.listdir(os.path.join(HERE, "fonts")):
        shutil.copy(os.path.join(HERE, "fonts", f), os.path.join(common, "fonts", f))
    os.makedirs(os.path.join(hd, "images"), exist_ok=True)
    for f in os.listdir(os.path.join(HERE, "images")):
        shutil.copy(os.path.join(HERE, "images", f), os.path.join(hd, "images", f))
    patch_cpp(rec)
    write(marker, "applied\n")
    print("ASEM theme applied: %d strings, %d Arabic" % (len(EN), len(AR) + len(TWRP_AR)))


# --------------------------------------------------------------------------- validation
# links that are already broken in stock TWRP android-14.1 (not caused by ASEM)
UPSTREAM_MISSING_PAGES = {"partsdcardaction"}


def check(root):
    import xml.etree.ElementTree as ET
    rec = os.path.join(root, "bootable", "recovery")
    hd = os.path.join(rec, "gui", "theme", "portrait_hdpi")
    common = os.path.join(rec, "gui", "theme", "common")
    errors = []
    docs = {}
    for rel in ("portrait_hdpi/ui.xml", "portrait_hdpi/ui_light.xml", "portrait_hdpi/splash.xml",
                "common/portrait.xml", "common/languages/en.xml", "common/languages/ar.xml"):
        try:
            docs[rel] = ET.parse(os.path.join(rec, "gui", "theme", rel)).getroot()
        except ET.ParseError as e:
            errors.append("XML error in %s: %s" % (rel, e))
    if errors:
        return errors
    images = set(os.path.splitext(f)[0] for f in os.listdir(os.path.join(hd, "images")))
    fonts = set(os.listdir(os.path.join(common, "fonts")))
    portrait = docs["common/portrait.xml"]
    pages = set(p.get("name") for p in portrait.iter("page"))
    for uiname in ("portrait_hdpi/ui.xml", "portrait_hdpi/ui_light.xml"):
        ui = docs[uiname]
        resources = {}
        for r in ui.find("resources"):
            if r.get("name") in resources:  # fonts and images share one namespace in TWRP
                errors.append("%s: resource name used twice: %s" % (uiname, r.get("name")))
            resources[r.get("name")] = r
            fn = r.get("filename")
            if r.tag == "font" and fn not in fonts:
                errors.append("%s: font file missing %s" % (uiname, fn))
            if r.tag == "image" and fn not in images:
                errors.append("%s: image file missing %s.png" % (uiname, fn))
            if r.tag == "animation" and fn + "001" not in images:
                errors.append("%s: animation frames missing %s001.png" % (uiname, fn))
        templates = set(t.get("name") for t in ui.find("templates"))
        styles = set(st.get("name") for st in portrait.find("styles"))
        for root_el, where in ((ui, uiname), (portrait, "portrait.xml")):
            for el in root_el.iter():
                res = el.get("resource")
                if res and not res.startswith("%") and res not in resources:
                    errors.append("%s: unknown resource '%s' (in <%s>)" % (where, res, el.tag))
                if el.tag == "template" and el.get("name") not in templates and where == "portrait.xml":
                    errors.append("portrait.xml: unknown template " + el.get("name"))
                if el.get("style") and el.get("style") not in styles:
                    errors.append("%s: unknown style %s" % (where, el.get("style")))
                if el.tag == "action" and el.get("function") in ("page", "overlay"):
                    tgt = (el.text or "").strip()
                    if tgt and "%" not in tgt and tgt not in pages and tgt not in UPSTREAM_MISSING_PAGES:
                        errors.append("%s: %s target '%s' does not exist" % (where, el.get("function"), tgt))
    # every ASEM page except Home must react to the navbar Back and Home keys
    for pg in portrait.find("pages"):
        if pg.get("name") in ("reboot", "asem_settings", "asem_slots", "asem_transfer", "asem_decrypt", "asem_slots_wait"):
            keys = set(t.get("key") for t in pg.iter("touch"))
            for k in ("back", "home"):
                if k not in keys:
                    errors.append("page %s: no '%s' key handler (navbar button would do nothing)" % (pg.get("name"), k))
    # language names: TWRP stores "en"/"ar" and adds ".xml" itself
    if re.search(r'tw_language"[^>]*var2="[a-z]+\.xml"|tw_language=[a-z]+\.xml', read(os.path.join(common, "portrait.xml")) +
                 "".join(read(os.path.join(hd, f)) for f in ("ui.xml", "ui_light.xml"))):
        errors.append("tw_language compared/set with a .xml suffix (TWRP adds .xml itself)")
    # strings: every {@asem_...} used must exist in en.xml; ar.xml must be valid
    en_ids = set(st.get("name") for st in docs["common/languages/en.xml"].iter("string"))
    used = set(re.findall(r"\{@(asem_[a-z0-9_]+)=", read(os.path.join(common, "portrait.xml"))))
    for sid in sorted(used - en_ids):
        errors.append("string %s used but not in en.xml" % sid)
    # glyph coverage
    try:
        from fontTools.ttLib import TTFont
        cmap = TTFont(os.path.join(common, "fonts", "Tajawal-Medium.ttf")).getBestCmap()
        for lang in ("en", "ar"):
            for st in docs["common/languages/%s.xml" % lang].iter("string"):
                if st.get("name", "").startswith("asem_") or lang == "ar":
                    for ch in (st.text or ""):
                        if ord(ch) > 32 and ord(ch) not in cmap:
                            errors.append("%s.xml %s: Tajawal has no glyph for U+%04X" % (lang, st.get("name"), ord(ch)))
    except ImportError:
        print("(fontTools not installed - glyph coverage not checked)")
    for rel, old, _ in CPP:
        if "asem_light" not in read(os.path.join(rec, rel)):
            errors.append("C++ patch missing in " + rel)
    return errors


if __name__ == "__main__":
    args = sys.argv[1:]
    do_check = "--check" in args
    args = [a for a in args if a != "--check"]
    if len(args) != 1:
        sys.exit(__doc__)
    apply(args[0])
    if do_check:
        errs = check(args[0])
        for e in errs:
            print("ERROR:", e)
        print("check: %s" % ("OK" if not errs else "%d problem(s)" % len(errs)))
        sys.exit(1 if errs else 0)
