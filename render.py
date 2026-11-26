#!/usr/bin/env python3
"""Render THE WORLD IN PICTURES v3: 26 stories of Tue 24 Nov 2026 in one
1024x1024 PNG. Reads stories.json (same dir), downloads Natural Earth 110m
land polygons (real coastlines) at build time, draws an equirectangular
world map with numbered pins, a 15-card story grid, a lead panel with a
bar chart, and a DATE CHECK box. Deterministic: same input -> same bytes.
Usage: python3 render.py [--geojson PATH] [--stories PATH] [--out PATH]
"""
import argparse
import json
import math
import os
import sys
import urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
GEOJSON_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
                "master/geojson/ne_110m_land.geojson")

W, H = 1024, 1024
PAPER = (247, 245, 239)
NAVY = (22, 38, 62)
NAVY2 = (38, 58, 86)
INK = (28, 28, 28)
GREY = (96, 96, 96)
LIGHT_GREY = (150, 150, 150)
RED = (178, 34, 34)
GREEN = (28, 110, 48)
SEA = (213, 228, 236)
LAND = (143, 173, 156)
LAND_EDGE = (120, 148, 132)
GRAT = (185, 205, 216)
CARD_BG = (255, 255, 255)
CARD_EDGE = (206, 200, 186)
TILE_BG = (255, 255, 255)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


F_TITLE = None  # set in main()


def text_w(f, s):
    return f.getlength(s)


def wrap(text, f, max_w):
    """Greedy word wrap; returns list of lines (never empty)."""
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_w(f, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(d, text, f, x, y, max_w, fill, leading=None, max_lines=None):
    lines = wrap(text, f, max_w)
    if max_lines is not None and len(lines) > max_lines:
        raise ValueError("text overflows %d lines: %r -> %r"
                         % (max_lines, text, lines))
    lh = leading if leading is not None else int(f.size * 1.22)
    for i, ln in enumerate(lines):
        d.text((x, y + i * lh), ln, font=f, fill=fill)
    return y + len(lines) * lh


# ---------------------------------------------------------------- icons
def icon_bars(d, x, y, s):
    c = (34, 120, 60)
    d.rectangle([x + 2, y + s - 8, x + 7, y + s - 2], fill=c)
    d.rectangle([x + 10, y + s - 14, x + 15, y + s - 2], fill=c)
    d.rectangle([x + 18, y + s - 20, x + 23, y + s - 2], fill=c)


def icon_alert(d, x, y, s):
    d.polygon([(x + s // 2, y + 1), (x + s - 1, y + s - 3), (x + 1, y + s - 3)],
              fill=(214, 148, 16))
    d.rectangle([x + s // 2 - 1, y + 8, x + s // 2 + 1, y + 15], fill=(255, 255, 255))
    d.rectangle([x + s // 2 - 1, y + 17, x + s // 2 + 1, y + 19], fill=(255, 255, 255))


def icon_ban(d, x, y, s):
    d.ellipse([x + 1, y + 1, x + s - 1, y + s - 1], outline=(178, 34, 34), width=3)
    d.line([x + 4, y + s - 5, x + s - 4, y + 4], fill=(178, 34, 34), width=3)


def icon_court(d, x, y, s):
    d.polygon([(x + 1, y + 9), (x + s // 2, y + 1), (x + s - 1, y + 9)],
              fill=(38, 58, 86))
    for i in range(3):
        cx = x + 4 + i * 8
        d.rectangle([cx, y + 11, cx + 3, y + 20], fill=(38, 58, 86))
    d.rectangle([x + 1, y + 21, x + s - 1, y + 23], fill=(38, 58, 86))


def icon_note(d, x, y, s):
    d.ellipse([x + 3, y + 16, x + 10, y + 22], fill=(28, 28, 28))
    d.rectangle([x + 9, y + 4, x + 11, y + 17], fill=(28, 28, 28))
    d.polygon([(x + 11, y + 4), (x + 20, y + 8), (x + 11, y + 11)], fill=(28, 28, 28))


def icon_soccer(d, x, y, s):
    d.ellipse([x + 1, y + 1, x + s - 1, y + s - 1], outline=(28, 28, 28), width=2)
    cx, cy = x + s // 2, y + s // 2
    d.polygon([(cx - 3, cy - 4), (cx + 3, cy - 4), (cx + 5, cy + 1),
               (cx, cy + 5), (cx - 5, cy + 1)], fill=(28, 28, 28))
    for px, py in [(cx - 8, cy - 6), (cx + 8, cy - 6), (cx - 9, cy + 5),
                   (cx + 9, cy + 5), (cx, cy - 9)]:
        d.ellipse([px - 1, py - 1, px + 1, py + 1], fill=(28, 28, 28))


def icon_hoop(d, x, y, s):
    d.ellipse([x + 1, y + 1, x + s - 1, y + s - 1], fill=(224, 122, 42),
              outline=(28, 28, 28), width=1)
    d.line([x + 2, y + s // 2, x + s - 2, y + s // 2], fill=(28, 28, 28), width=1)
    d.line([x + s // 2, y + 2, x + s // 2, y + s - 2], fill=(28, 28, 28), width=1)
    d.arc([x - 6, y + 2, x + 12, y + s + 6], 300, 60, fill=(28, 28, 28), width=1)


def icon_pigskin(d, x, y, s):
    d.ellipse([x + 1, y + 6, x + s - 1, y + s - 6], fill=(122, 72, 32))
    d.line([x + 7, y + s // 2, x + s - 7, y + s // 2], fill=(255, 255, 255), width=2)
    for i in range(3):
        lx = x + 9 + i * 3
        d.line([lx, y + s // 2 - 3, lx, y + s // 2 + 3], fill=(255, 255, 255), width=1)


def icon_chip(d, x, y, s):
    d.rectangle([x + 5, y + 5, x + s - 5, y + s - 5], fill=(38, 58, 86))
    d.rectangle([x + 9, y + 9, x + s - 9, y + s - 9], outline=(255, 255, 255), width=1)
    for i in range(3):
        px = x + 8 + i * 4
        d.line([px, y + 1, px, y + 5], fill=(38, 58, 86), width=2)
        d.line([px, y + s - 5, px, y + s - 1], fill=(38, 58, 86), width=2)
        d.line([x + 1, y + 8 + i * 4, x + 5, y + 8 + i * 4], fill=(38, 58, 86), width=2)
        d.line([x + s - 5, y + 8 + i * 4, x + s - 1, y + 8 + i * 4], fill=(38, 58, 86), width=2)


def icon_scales(d, x, y, s):
    d.line([x + s // 2, y + 3, x + s // 2, y + 20], fill=(90, 90, 90), width=2)
    d.line([x + 4, y + 6, x + s - 4, y + 6], fill=(90, 90, 90), width=2)
    d.polygon([(x + 2, y + 6), (x + 7, y + 6), (x + 4, y + 13)], fill=(150, 120, 60))
    d.polygon([(x + s - 7, y + 6), (x + s - 2, y + 6), (x + s - 4, y + 13)],
              fill=(150, 120, 60))
    d.rectangle([x + s // 2 - 5, y + 20, x + s // 2 + 5, y + 22], fill=(90, 90, 90))


def icon_globe(d, x, y, s):
    d.ellipse([x + 1, y + 1, x + s - 1, y + s - 1], fill=(90, 140, 190),
              outline=(28, 60, 110), width=1)
    d.ellipse([x + s // 2 - 4, y + 1, x + s // 2 + 4, y + s - 1],
              outline=(255, 255, 255), width=1)
    d.line([x + 1, y + s // 2, x + s - 1, y + s // 2], fill=(255, 255, 255), width=1)


def icon_mountain(d, x, y, s):
    d.polygon([(x + 1, y + s - 2), (x + 9, y + 4), (x + 17, y + s - 2)],
              fill=(110, 110, 110))
    d.polygon([(x + 9, y + 4), (x + 12, y + 9), (x + 6, y + 9)], fill=(255, 255, 255))
    d.polygon([(x + 12, y + s - 2), (x + 18, y + 10), (x + s - 1, y + s - 2)],
              fill=(140, 140, 140))


def icon_ship(d, x, y, s):
    d.polygon([(x + 2, y + 15), (x + s - 2, y + 15), (x + s - 6, y + 21),
               (x + 6, y + 21)], fill=(122, 72, 32))
    d.line([x + s // 2, y + 3, x + s // 2, y + 15], fill=(28, 28, 28), width=2)
    d.polygon([(x + s // 2, y + 3), (x + s - 6, y + 8), (x + s // 2, y + 8)],
              fill=(178, 34, 34))


def icon_flag(d, x, y, s):
    d.line([x + 4, y + 2, x + 4, y + s - 1], fill=(90, 90, 90), width=2)
    d.polygon([(x + 4, y + 2), (x + s - 1, y + 6), (x + 4, y + 11)], fill=(178, 34, 34))


ICONS = {"bars": icon_bars, "alert": icon_alert, "ban": icon_ban,
         "court": icon_court, "note": icon_note, "soccer": icon_soccer,
         "hoop": icon_hoop, "pigskin": icon_pigskin, "chip": icon_chip,
         "scales": icon_scales, "globe": icon_globe, "mountain": icon_mountain,
         "ship": icon_ship, "flag": icon_flag}


# ---------------------------------------------------------------- map
def split_ring(ring):
    """Split a lon/lat ring at antimeridian jumps (>180 deg) so no line is
    drawn across the map. Returns a list of runs (each >= 2 points)."""
    runs, cur = [], [ring[0]]
    for a, b in zip(ring, ring[1:]):
        if abs(b[0] - a[0]) > 180:
            runs.append(cur)
            cur = [b]
        else:
            cur.append(b)
    runs.append(cur)
    return [r for r in runs if len(r) >= 2]


def project(lon, lat, x0, y0, s):
    return (x0 + (lon + 180.0) * s, y0 + (84.0 - lat) * s)


def draw_map(img, d, geo, box):
    """Equirectangular, uniform scale, lon -180..180, lat 84..-58.
    Land is drawn on a layer the size of the box and pasted, so nothing
    (e.g. Antarctica, lat < -58) can spill outside the frame.
    Returns the (x0, y0, scale) projection actually used."""
    x0b, y0b, x1b, y1b = box
    bw, bh = x1b - x0b, y1b - y0b
    s = min(bw / 360.0, bh / 142.0)
    used_w, used_h = 360.0 * s, 142.0 * s
    x0 = x0b + (bw - used_w) / 2.0
    y0 = y0b + (bh - used_h) / 2.0
    layer = Image.new("RGB", (bw, bh), SEA)
    md = ImageDraw.Draw(layer)
    ox, oy = x0 - x0b, y0 - y0b  # projection origin in layer coords

    def P(lon, lat):
        return (ox + (lon + 180.0) * s, oy + (84.0 - lat) * s)

    # graticule every 30 degrees
    for lon in range(-180, 181, 30):
        px, _ = P(lon, 84)
        md.line([(px, oy), (px, oy + used_h)], fill=GRAT, width=1)
    for lat in range(-60, 85, 30):
        _, py = P(-180, lat)
        md.line([(ox, py), (ox + used_w, py)], fill=GRAT, width=1)
    _, eq = P(-180, 0)
    for xx in range(int(ox), int(ox + used_w), 8):
        md.line([(xx, eq), (xx + 4, eq)], fill=(150, 175, 190), width=1)
    # land: exterior rings filled, interior rings (lakes) cut in sea colour
    for feat in geo["features"]:
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" \
            else [geom["coordinates"]]
        for poly in polys:
            for ri, ring in enumerate(poly):
                fill = LAND if ri == 0 else SEA
                for run in split_ring(ring):
                    pts = [P(lon, lat) for lon, lat in run]
                    if len(pts) >= 3:
                        md.polygon(pts, fill=fill)
            # outline the exterior only
            for run in split_ring(poly[0]):
                pts = [P(lon, lat) for lon, lat in run]
                if len(pts) >= 2:
                    md.line(pts, fill=LAND_EDGE, width=1)
    img.paste(layer, (x0b, y0b))
    d.rectangle(box, outline=(120, 130, 140), width=1)
    return x0, y0, s


# ---------------------------------------------------------------- build
def build(stories_path, geojson_path, out_path):
    with open(stories_path, encoding="utf-8") as fh:
        st = json.load(fh)

    if geojson_path:
        with open(geojson_path, encoding="utf-8") as fh:
            geo = json.load(fh)
    else:
        req = urllib.request.Request(GEOJSON_URL, headers={"User-Agent": "makefun-v3"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            geo = json.loads(resp.read().decode("utf-8"))

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    f_mast = font("DejaVuSans-Bold.ttf", 38)
    f_date = font("DejaVuSans-Bold.ttf", 15)
    f_tag = font("DejaVuSans.ttf", 13)
    f_kick = font("DejaVuSans-Bold.ttf", 13)
    f_head = font("DejaVuSans-Bold.ttf", 29)
    f_sub = font("DejaVuSans.ttf", 15)
    f_stat_l = font("DejaVuSans-Bold.ttf", 11)
    f_stat_p = font("DejaVuSans-Bold.ttf", 20)
    f_stat_v = font("DejaVuSans.ttf", 13)
    f_chart_t = font("DejaVuSans-Bold.ttf", 12)
    f_chart_l = font("DejaVuSans-Bold.ttf", 15)
    f_chart_n = font("DejaVuSans-Bold.ttf", 12)
    f_chart_s = font("DejaVuSans.ttf", 10)
    f_sec = font("DejaVuSans-Bold.ttf", 16)
    f_pin_n = font("DejaVuSans-Bold.ttf", 11)
    f_key_p = font("DejaVuSans-Bold.ttf", 11)
    f_key_t = font("DejaVuSans.ttf", 11)
    f_ocean = font("DejaVuSans-Bold.ttf", 10)
    f_card_h = font("DejaVuSans-Bold.ttf", 13)
    f_card_d = font("DejaVuSans.ttf", 11)
    f_dc_t = font("DejaVuSans-Bold.ttf", 13)
    f_dc_i = font("DejaVuSans.ttf", 12)
    f_foot = font("DejaVuSans.ttf", 11)

    # ---- masthead
    d.rectangle([0, 0, W, 66], fill=NAVY)
    d.text((16, 14), st["title"], font=f_mast, fill=(255, 255, 255))
    dt = st["date_label"]
    d.text((W - 16 - text_w(f_date, dt), 12), dt, font=f_date, fill=(255, 255, 255))
    tg = st["tagline"]
    d.text((W - 16 - text_w(f_tag, tg), 36), tg, font=f_tag, fill=(190, 200, 215))

    # ---- lead
    lead = st["lead"]
    d.text((16, 76), lead["kicker"], font=f_kick, fill=RED)
    y = 96
    for ln in lead["headline"]:
        d.text((16, y), ln, font=f_head, fill=NAVY)
        y += 33
    d.text((16, y + 4), lead["subline"], font=f_sub, fill=(60, 60, 60))
    # stat tiles (stacked: label / pct / value, no overlap)
    tx, ty, tw, th, gap = 16, 183, 134, 62, 8
    for i, s in enumerate(lead["stats"]):
        x = tx + i * (tw + gap)
        d.rectangle([x, ty, x + tw, ty + th], fill=TILE_BG, outline=CARD_EDGE, width=1)
        d.rectangle([x, ty, x + tw, ty + 3], fill=RED)
        d.text((x + 8, ty + 7), s["label"], font=f_stat_l, fill=GREY)
        d.text((x + 8, ty + 22), s["pct"], font=f_stat_p, fill=GREEN)
        d.text((x + 8, ty + 45), s["value"], font=f_stat_v, fill=INK)
    # bar chart (right)
    cx0, cx1, base = 600, 1008, 228
    d.text((cx0, 76), lead["chart_title"], font=f_chart_t, fill=GREY)
    d.line([(cx0, base), (cx1, base)], fill=(120, 120, 120), width=2)
    max_pct = 3.5
    bw_bar, centres = 72, [660, 790, 920]
    for bar, cx in zip(lead["bars"], centres):
        hgt = int(bar["pct"] / max_pct * 118)
        d.rectangle([cx - bw_bar // 2, base - hgt, cx + bw_bar // 2, base],
                    fill=(38, 90, 140))
        lab = "+%.2f%%" % bar["pct"]
        d.text((cx - text_w(f_chart_l, lab) / 2, base - hgt - 20), lab,
               font=f_chart_l, fill=GREEN)
        nm = bar["label"]
        d.text((cx - text_w(f_chart_n, nm) / 2, base + 6), nm,
               font=f_chart_n, fill=INK)
    src = lead["source"]
    d.text((cx1 - text_w(f_chart_s, src), 76), src, font=f_chart_s, fill=GREY)

    # ---- map section
    d.text((16, 258), st["map"]["title"], font=f_sec, fill=NAVY)
    mx0, my0, mx1, my1 = 16, 282, 656, 534
    px0, py0, sc = draw_map(img, d, geo, (mx0, my0, mx1, my1))
    # ocean labels
    for label, lon, lat in [("PACIFIC", -150, -28), ("ATLANTIC", -28, -18),
                            ("INDIAN OCEAN", 82, -38)]:
        lx, ly = project(lon, lat, px0, py0, sc)
        d.text((lx, ly), label, font=f_ocean, fill=(110, 135, 150))
    # pins
    pins = st["map"]["pins"]
    for p in pins:
        txp, typ = project(p["lon"], p["lat"], px0, py0, sc)
        cx, cy = txp + p.get("dx", 0), typ + p.get("dy", 0)
        if p.get("dx", 0) or p.get("dy", 0):
            d.line([(txp, typ), (cx, cy)], fill=RED, width=1)
            d.ellipse([txp - 2, typ - 2, txp + 2, typ + 2], fill=RED)
        r = 8
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED,
                  outline=(255, 255, 255), width=2)
        num = str(p["n"])
        d.text((cx - text_w(f_pin_n, num) / 2, cy - 7), num,
               font=f_pin_n, fill=(255, 255, 255))
    # key panel
    kx, ky = 672, 282
    for p in pins:
        head = "%d %s — " % (p["n"], p["place"])
        head_w = text_w(f_key_p, head)
        # wrap the body text in the space left after the bold head
        body = wrap(p["text"], f_key_t, 336 - head_w)
        if len(body) > 2:
            raise ValueError("key entry too long: %r" % p["text"])
        d.text((kx, ky), head, font=f_key_p, fill=NAVY)
        d.text((kx + head_w, ky), body[0], font=f_key_t, fill=INK)
        if len(body) > 1:
            d.text((kx, ky + 13), body[1], font=f_key_t, fill=INK)
        ky += 25

    # ---- grid
    d.text((16, 546), st["grid_title"], font=f_sec, fill=NAVY)
    cw, chh, cg = 192, 92, 8
    for i, card in enumerate(st["grid"]):
        row, col = divmod(i, 5)
        x = 16 + col * (cw + cg)
        y = 572 + row * (chh + cg)
        d.rectangle([x, y, x + cw, y + chh], fill=CARD_BG, outline=CARD_EDGE, width=1)
        ICONS[card["icon"]](d, x + 8, y + 8, 24)
        draw_wrapped(d, card["headline"], f_card_h, x + 38, y + 8, 146,
                     INK, leading=15, max_lines=2)
        draw_wrapped(d, card["detail"], f_card_d, x + 8, y + 42, 176,
                     (60, 60, 60), leading=13, max_lines=3)

    # ---- date check
    d.rectangle([16, 860, 1008, 988], outline=RED, width=2)
    d.text((28, 870), st["date_check"]["title"], font=f_dc_t, fill=RED)
    items = st["date_check"]["items"]
    for i, item in enumerate(items):
        col, row = divmod(i, 5)
        x = 32 + col * 488
        y = 896 + row * 19
        d.text((x, y), "•  " + item, font=f_dc_i, fill=INK)

    # ---- footer
    ft = st["footer"]
    d.text(((W - text_w(f_foot, ft)) / 2, 998), ft, font=f_foot, fill=GREY)

    img.save(out_path, format="PNG", optimize=False)
    print("wrote %s (%dx%d)" % (out_path, W, H))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geojson", default=None)
    ap.add_argument("--stories", default=os.path.join(HERE, "stories.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "entry.png"))
    args = ap.parse_args()
    build(args.stories, args.geojson, args.out)


if __name__ == "__main__":
    main()
