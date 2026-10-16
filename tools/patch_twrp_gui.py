#!/usr/bin/env python3
"""ASEM Recovery: TWRP gui patches (applied by build.sh after the theme).

  patch_twrp_gui.py <twrp_root>

1. Smooth sliders (swipe to flash / wipe / unlock) without touching anything else.
   TWRP redraws the WHOLE screen in software for every slider move (~16 fps at
   1080x2436 on the X6855, measured R2/#14). Now: on a normal full redraw the slider
   saves the pixels under its own strip; while it is dragged, Update() puts those back,
   redraws only the slider and returns 1 (= flip only, no full Render). Every other
   screen and object keeps TWRP's normal full redraw. Falls back to a full redraw if the
   draw buffer is rotated/unavailable or nothing was saved yet.
2. PRINT_RENDER_TIME: log "Render(): x ms, flip(): y ms" for full frames and
   "flip-only: y ms" for slider frames, to measure on the phone (test builds).
Idempotent: each change carries a marker and is skipped if already present.
"""
import os, sys

MARK = "// ASEM: partial slider redraw"


def patch_slider(p):
    s = open(p, encoding="utf-8").read()
    if MARK in s:
        return "slider.cpp: already patched"
    helpers = MARK + '''
#include <map>
#include <vector>
#include <string.h>
extern GRSurface* gr_draw;
extern unsigned int gr_rotation;
namespace {
struct AsemSliderBg { int x = 0, y = 0, w = 0, h = 0; std::vector<unsigned char> px; bool valid = false; };
std::map<const void*, AsemSliderBg> asem_bg;
bool asem_partial = false;
bool asem_region(int rx, int ry, int rw, int rh, int th, AsemSliderBg& b) {
	if (!gr_draw || !gr_draw->data || gr_rotation != 0 || gr_draw->pixel_bytes < 1 || rw <= 0 || rh <= 0)
		return false;
	int y0 = ry, y1 = ry + rh;
	int ty = ry + ((rh - th) / 2);
	if (th > 0 && ty < y0) y0 = ty;
	if (th > 0 && ty + th > y1) y1 = ty + th;
	int x0 = rx < 0 ? 0 : rx, x1 = rx + rw > gr_draw->width ? gr_draw->width : rx + rw;
	if (y0 < 0) y0 = 0;
	if (y1 > gr_draw->height) y1 = gr_draw->height;
	b.x = x0; b.y = y0; b.w = x1 - x0; b.h = y1 - y0;
	return b.w > 0 && b.h > 0;
}
void asem_copy(AsemSliderBg& b, bool save) {
	const size_t pb = gr_draw->pixel_bytes, rb = gr_draw->row_bytes, n = (size_t)b.w * pb;
	for (int r = 0; r < b.h; ++r) {
		unsigned char* fb = gr_draw->data + (size_t)(b.y + r) * rb + (size_t)b.x * pb;
		unsigned char* sv = b.px.data() + (size_t)r * n;
		if (save) memcpy(sv, fb, n); else memcpy(fb, sv, n);
	}
}
}  // namespace

GUISlider::GUISlider(xml_node<>* node) : GUIObject(node)'''
    a = "GUISlider::GUISlider(xml_node<>* node) : GUIObject(node)"
    assert s.count(a) == 1, "constructor anchor"
    s = s.replace(a, helpers, 1)

    a = "GUISlider::~GUISlider()\n{\n"
    assert s.count(a) == 1, "destructor anchor"
    s = s.replace(a, a + "\tasem_bg.erase(this);\n", 1)

    a = """	if (!sSlider || !sSlider->GetResource())
		return -1;

	// Draw the slider"""
    assert s.count(a) == 1, "render anchor"
    s = s.replace(a, """	if (!sSlider || !sSlider->GetResource())
		return -1;

	if (!asem_partial) {  // full redraw: remember what is under the slider
		AsemSliderBg& b = asem_bg[this];
		b.valid = asem_region(mRenderX, mRenderY, mRenderW, mRenderH,
				(sTouch && sTouch->GetResource()) ? sTouchH : 0, b);
		if (b.valid) {
			b.px.resize((size_t)b.w * b.h * gr_draw->pixel_bytes);
			asem_copy(b, true);
		}
	}

	// Draw the slider""", 1)

    a = """	if (sUpdate)
		return 2;
	return 0;
}"""
    assert s.count(a) == 1, "update anchor"
    s = s.replace(a, """	if (sUpdate) {
		std::map<const void*, AsemSliderBg>::iterator it = asem_bg.find(this);
		if (it != asem_bg.end() && it->second.valid && gr_draw && gr_draw->data && gr_rotation == 0) {
			asem_copy(it->second, false);  // background back, then only the slider on top
			asem_partial = true;
			int ret = Render();
			asem_partial = false;
			if (ret >= 0)
				return 1;  // flip only - no full-screen Render
		}
		return 2;
	}
	return 0;
}""", 1)
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    return "slider.cpp: patched"


def patch_gui(p):
    s = open(p, encoding="utf-8").read()
    if "// ASEM: render timing" in s:
        return "gui.cpp: already patched"
    a = "#ifndef PRINT_RENDER_TIME"
    assert s.count(a) == 1, "render-time anchor"
    s = s.replace(a, "#define PRINT_RENDER_TIME  // ASEM: render timing (test builds)\n" + a, 1)
    a = """			else if (ret > 0)
				flip();
#endif"""
    assert s.count(a) == 1, "flip-only anchor"
    s = s.replace(a, """			else if (ret > 0)
			{
				timespec fs, fe;
				clock_gettime(CLOCK_MONOTONIC, &fs);
				flip();
				clock_gettime(CLOCK_MONOTONIC, &fe);
				LOGINFO("flip-only: %u ms\\n", (unsigned)TWFunc::timespec_diff_ms(fs, fe));
			}
#endif""", 1)
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    return "gui.cpp: patched"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    gui = os.path.join(sys.argv[1], "bootable", "recovery", "gui")
    print(patch_slider(os.path.join(gui, "slider.cpp")))
    print(patch_gui(os.path.join(gui, "gui.cpp")))
