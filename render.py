#!/usr/bin/env python3
"""Paint THE WORLD IN PICTURES for Thursday 26 November 2026.

Reads stories.json next to this file plus a Natural Earth 110m land
GeoJSON file, and draws a 1024x1024 newspaper-style poster: a navy
masthead, an energy lead story with stat tiles and a bar chart, an
equirectangular world map with ten numbered pins and a key, a
fifteen-card story grid, a DATE CHECK box of look-alike stories that
are NOT from today, and a sources footer.

The picture is deterministic: the same inputs always produce the same
PNG bytes, because every draw call, coordinate and font size is fixed
and the input files are read in a fixed order.

Usage:
    python3 render.py [--geojson PATH] [--stories PATH] [--out PATH]
If --geojson is omitted, the GeoJSON is downloaded from Natural Earth.
"""

import argparse
import json
import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
GEOJSON_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_land.geojson"
)

SIZE = (1024, 1024)

PAL = {
    "paper": (247, 245, 239),
    "navy": (22, 38, 62),
    "navy2": (38, 58, 86),
    "ink": (28, 28, 28),
    "grey": (96, 96, 96),
    "faint": (150, 150, 150),
    "red": (178, 34, 34),
    "green": (28, 110, 48),
    "sea": (213, 228, 236),
    "land": (143, 173, 156),
    "land_edge": (120, 148, 132),
    "grat": (185, 205, 216),
    "card": (255, 255, 255),
    "card_edge": (206, 200, 186),
    "muted": (60, 60, 60),
    "mist": (190, 200, 215),
    "rule": (120, 120, 120),
    "ocean_ink": (110, 135, 150),
    "frame": (120, 130, 140),
    "equator": (150, 175, 190),
    "bar": (38, 90, 140),
}


def face(name, size):
    """Load one DejaVu face at the requested point size."""
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def measure(fnt, text):
    """Pixel width of text in a font (float, as FreeType reports it)."""
    return fnt.getlength(text)


def fold(text, fnt, max_w):
    """Greedy word wrap to a pixel width; returns a list of lines.

    Words are added while the joined line still fits; a single word
    longer than the width goes on a line of its own.
    """
    words = text.split(" ")
    lines = []
    current = ""
    for word in words:
        trial = (current + " " + word).strip()
        if measure(fnt, trial) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def blurb(drw, text, fnt, x, y, max_w, fill, leading=None, cap=None):
    """Draw wrapped text at (x, y); returns the y after the last line.

    Raises if the text needs more lines than `cap` allows, so copy
    that cannot fit its card fails loudly instead of overflowing.
    """
    lines = fold(text, fnt, max_w)
    if cap is not None and len(lines) > cap:
        raise ValueError(
            "text needs %d lines (cap %d): %r -> %r"
            % (len(lines), cap, text, lines)
        )
    step = leading if leading is not None else int(fnt.size * 1.22)
    for index, line in enumerate(lines):
        drw.text((x, y + index * step), line, font=fnt, fill=fill)
    return y + len(lines) * step

# ------------------------------------------------------------------ glyphs
# Small pictograms for the story cards, drawn with plain PIL shapes.
# Each takes (draw, x, y, size); the grid calls them with size 24.
# Only the glyphs the 15 cards actually use are defined here.

def glyph_bars(drw, x, y, s):
    green = (34, 120, 60)
    drw.rectangle([x + 2, y + s - 8, x + 7, y + s - 2], fill=green)
    drw.rectangle([x + 10, y + s - 14, x + 15, y + s - 2], fill=green)
    drw.rectangle([x + 18, y + s - 20, x + 23, y + s - 2], fill=green)


def glyph_warn(drw, x, y, s):
    drw.polygon([(x + s // 2, y + 1), (x + s - 1, y + s - 3),
                 (x + 1, y + s - 3)], fill=(214, 148, 16))
    drw.rectangle([x + s // 2 - 1, y + 8, x + s // 2 + 1, y + 15],
                  fill=(255, 255, 255))
    drw.rectangle([x + s // 2 - 1, y + 17, x + s // 2 + 1, y + 19],
                  fill=(255, 255, 255))


def glyph_court(drw, x, y, s):
    roof = PAL["navy2"]
    drw.polygon([(x + 1, y + 9), (x + s // 2, y + 1), (x + s - 1, y + 9)],
                fill=roof)
    for i in range(3):
        cx = x + 4 + i * 8
        drw.rectangle([cx, y + 11, cx + 3, y + 20], fill=roof)
    drw.rectangle([x + 1, y + 21, x + s - 1, y + 23], fill=roof)


def glyph_chip(drw, x, y, s):
    body = PAL["navy2"]
    drw.rectangle([x + 5, y + 5, x + s - 5, y + s - 5], fill=body)
    drw.rectangle([x + 9, y + 9, x + s - 9, y + s - 9],
                  outline=(255, 255, 255), width=1)
    for i in range(3):
        px = x + 8 + i * 4
        drw.line([px, y + 1, px, y + 5], fill=body, width=2)
        drw.line([px, y + s - 5, px, y + s - 1], fill=body, width=2)
        drw.line([x + 1, y + 8 + i * 4, x + 5, y + 8 + i * 4],
                 fill=body, width=2)
        drw.line([x + s - 5, y + 8 + i * 4, x + s - 1, y + 8 + i * 4],
                 fill=body, width=2)


def glyph_scales(drw, x, y, s):
    iron = (90, 90, 90)
    brass = (150, 120, 60)
    drw.line([x + s // 2, y + 3, x + s // 2, y + 20], fill=iron, width=2)
    drw.line([x + 4, y + 6, x + s - 4, y + 6], fill=iron, width=2)
    drw.polygon([(x + 2, y + 6), (x + 7, y + 6), (x + 4, y + 13)], fill=brass)
    drw.polygon([(x + s - 7, y + 6), (x + s - 2, y + 6), (x + s - 4, y + 13)],
                fill=brass)
    drw.rectangle([x + s // 2 - 5, y + 20, x + s // 2 + 5, y + 22], fill=iron)


def glyph_globe(drw, x, y, s):
    drw.ellipse([x + 1, y + 1, x + s - 1, y + s - 1], fill=(90, 140, 190),
                outline=(28, 60, 110), width=1)
    drw.ellipse([x + s // 2 - 4, y + 1, x + s // 2 + 4, y + s - 1],
                outline=(255, 255, 255), width=1)
    drw.line([x + 1, y + s // 2, x + s - 1, y + s // 2],
             fill=(255, 255, 255), width=1)


def glyph_boat(drw, x, y, s):
    drw.polygon([(x + 2, y + 15), (x + s - 2, y + 15), (x + s - 6, y + 21),
                 (x + 6, y + 21)], fill=(122, 72, 32))
    drw.line([x + s // 2, y + 3, x + s // 2, y + 15], fill=PAL["ink"], width=2)
    drw.polygon([(x + s // 2, y + 3), (x + s - 6, y + 8), (x + s // 2, y + 8)],
                fill=PAL["red"])


def glyph_flag(drw, x, y, s):
    drw.line([x + 4, y + 2, x + 4, y + s - 1], fill=(90, 90, 90), width=2)
    drw.polygon([(x + 4, y + 2), (x + s - 1, y + 6), (x + 4, y + 11)],
                fill=PAL["red"])


def glyph_ball(drw, x, y, s):
    drw.ellipse([x + 1, y + 1, x + s - 1, y + s - 1],
                outline=PAL["ink"], width=2)
    cx, cy = x + s // 2, y + s // 2
    drw.polygon([(cx - 3, cy - 4), (cx + 3, cy - 4), (cx + 5, cy + 1),
                 (cx, cy + 5), (cx - 5, cy + 1)], fill=PAL["ink"])
    for px, py in [(cx - 8, cy - 6), (cx + 8, cy - 6), (cx - 9, cy + 5),
                   (cx + 9, cy + 5), (cx, cy - 9)]:
        drw.ellipse([px - 1, py - 1, px + 1, py + 1], fill=PAL["ink"])


GLYPHS = {
    "bars": glyph_bars,
    "alert": glyph_warn,
    "court": glyph_court,
    "chip": glyph_chip,
    "scales": glyph_scales,
    "globe": glyph_globe,
    "ship": glyph_boat,
    "flag": glyph_flag,
    "soccer": glyph_ball,
}

# -------------------------------------------------------------------- map

def split_dateline(ring):
    """Cut a lon/lat ring wherever it jumps across the antimeridian.

    A jump of more than 180 degrees of longitude means the polygon
    crossed the map edge; drawing a straight line across would streak
    the whole map. Returns the surviving runs (each at least 2 points).
    """
    runs = []
    run = [ring[0]]
    for a, b in zip(ring, ring[1:]):
        if abs(b[0] - a[0]) > 180:
            runs.append(run)
            run = [b]
        else:
            run.append(b)
    runs.append(run)
    return [r for r in runs if len(r) >= 2]


def project_pt(lon, lat, ox, oy, scale):
    """Equirectangular projection; lon -180..180, lat 84..-58."""
    return (ox + (lon + 180.0) * scale, oy + (84.0 - lat) * scale)


def paint_map(canvas, drw, geo, box):
    """Draw the world map inside `box`; return the projection used.

    The map is painted on a layer exactly the size of the box and then
    pasted, so land below lat -58 (Antarctica's tail) cannot spill
    outside the frame. Returns (origin_x, origin_y, scale) in box
    coordinates, for the pins and the ocean labels.
    """
    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    scale = min(bw / 360.0, bh / 142.0)
    used_w = 360.0 * scale
    used_h = 142.0 * scale
    ox = bx0 + (bw - used_w) / 2.0
    oy = by0 + (bh - used_h) / 2.0
    layer = Image.new("RGB", (bw, bh), PAL["sea"])
    md = ImageDraw.Draw(layer)
    lx, ly = ox - bx0, oy - by0

    def at(lon, lat):
        return (lx + (lon + 180.0) * scale, ly + (84.0 - lat) * scale)

    # graticule every 30 degrees
    for lon in range(-180, 181, 30):
        px, _ = at(lon, 84)
        md.line([(px, ly), (px, ly + used_h)], fill=PAL["grat"], width=1)
    for lat in range(-60, 85, 30):
        _, py = at(-180, lat)
        md.line([(lx, py), (lx + used_w, py)], fill=PAL["grat"], width=1)
    # dashed equator
    _, eq = at(-180, 0)
    for xx in range(int(lx), int(lx + used_w), 8):
        md.line([(xx, eq), (xx + 4, eq)], fill=PAL["equator"], width=1)

    # land: exterior rings filled, interior rings (lakes) cut in sea colour
    for feat in geo["features"]:
        geom = feat["geometry"]
        if geom["type"] == "MultiPolygon":
            polys = geom["coordinates"]
        else:
            polys = [geom["coordinates"]]
        for poly in polys:
            for ring_i, ring in enumerate(poly):
                shade = PAL["land"] if ring_i == 0 else PAL["sea"]
                for run in split_dateline(ring):
                    pts = [at(lon, lat) for lon, lat in run]
                    if len(pts) >= 3:
                        md.polygon(pts, fill=shade)
            # outline the exterior only
            for run in split_dateline(poly[0]):
                pts = [at(lon, lat) for lon, lat in run]
                if len(pts) >= 2:
                    md.line(pts, fill=PAL["land_edge"], width=1)

    canvas.paste(layer, (bx0, by0))
    drw.rectangle(box, outline=PAL["frame"], width=1)
    return ox, oy, scale

# ------------------------------------------------------------- sections

def _masthead(drw, faces, data):
    width, _ = SIZE
    drw.rectangle([0, 0, width, 66], fill=PAL["navy"])
    drw.text((16, 14), data["title"], font=faces["mast"], fill=(255, 255, 255))
    stamp = data["date_label"]
    drw.text((width - 16 - measure(faces["date"], stamp), 12), stamp,
             font=faces["date"], fill=(255, 255, 255))
    tag = data["tagline"]
    drw.text((width - 16 - measure(faces["tag"], tag), 36), tag,
             font=faces["tag"], fill=PAL["mist"])


def _lead(drw, faces, lead):
    drw.text((16, 76), lead["kicker"], font=faces["kick"], fill=PAL["red"])
    y = 96
    for line in lead["headline"]:
        drw.text((16, y), line, font=faces["head"], fill=PAL["navy"])
        y += 33
    drw.text((16, y + 4), lead["subline"], font=faces["sub"], fill=PAL["muted"])
    # stat tiles, stacked label / percent / value
    tx, ty, tw, th, gap = 16, 183, 134, 62, 8
    for i, tile in enumerate(lead["stats"]):
        x = tx + i * (tw + gap)
        drw.rectangle([x, ty, x + tw, ty + th], fill=PAL["card"],
                      outline=PAL["card_edge"], width=1)
        drw.rectangle([x, ty, x + tw, ty + 3], fill=PAL["red"])
        drw.text((x + 8, ty + 7), tile["label"], font=faces["stat_l"],
                 fill=PAL["grey"])
        drw.text((x + 8, ty + 22), tile["pct"], font=faces["stat_p"],
                 fill=PAL["green"])
        drw.text((x + 8, ty + 45), tile["value"], font=faces["stat_v"],
                 fill=PAL["ink"])


def _chart(drw, faces, lead):
    cx0, cx1, base = 600, 1008, 228
    drw.text((cx0, 76), lead["chart_title"], font=faces["chart_t"],
             fill=PAL["grey"])
    drw.line([(cx0, base), (cx1, base)], fill=PAL["rule"], width=2)
    top = 3.5
    half = 36
    for bar, cx in zip(lead["bars"], [660, 790, 920]):
        hgt = int(bar["pct"] / top * 118)
        drw.rectangle([cx - half, base - hgt, cx + half, base],
                      fill=PAL["bar"])
        lab = "+%.2f%%" % bar["pct"]
        drw.text((cx - measure(faces["chart_l"], lab) / 2, base - hgt - 20),
                 lab, font=faces["chart_l"], fill=PAL["green"])
        name = bar["label"]
        drw.text((cx - measure(faces["chart_n"], name) / 2, base + 6), name,
                 font=faces["chart_n"], fill=PAL["ink"])
    src = lead["source"]
    drw.text((cx1 - measure(faces["chart_s"], src), 76), src,
             font=faces["chart_s"], fill=PAL["grey"])


def _map_section(canvas, drw, faces, geo, data):
    drw.text((16, 258), data["map"]["title"], font=faces["sec"],
             fill=PAL["navy"])
    ox, oy, scale = paint_map(canvas, drw, geo, (16, 282, 656, 534))
    for label, lon, lat in [("PACIFIC", -150, -28), ("ATLANTIC", -28, -18),
                            ("INDIAN OCEAN", 82, -38)]:
        lx, ly = project_pt(lon, lat, ox, oy, scale)
        drw.text((lx, ly), label, font=faces["ocean"], fill=PAL["ocean_ink"])
    # numbered pins; an offset pin gets a leader line plus a dot on the
    # true point so the number never hides the place it marks
    pins = data["map"]["pins"]
    for pin in pins:
        txp, typ = project_pt(pin["lon"], pin["lat"], ox, oy, scale)
        cx, cy = txp + pin.get("dx", 0), typ + pin.get("dy", 0)
        if pin.get("dx", 0) or pin.get("dy", 0):
            drw.line([(txp, typ), (cx, cy)], fill=PAL["red"], width=1)
            drw.ellipse([txp - 2, typ - 2, txp + 2, typ + 2], fill=PAL["red"])
        r = 8
        drw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PAL["red"],
                    outline=(255, 255, 255), width=2)
        num = str(pin["n"])
        drw.text((cx - measure(faces["pin_n"], num) / 2, cy - 7), num,
                 font=faces["pin_n"], fill=(255, 255, 255))
    # key panel, two lines max per entry
    kx, ky = 672, 282
    for pin in pins:
        head = "%d %s — " % (pin["n"], pin["place"])
        head_w = measure(faces["key_p"], head)
        body = fold(pin["text"], faces["key_t"], 336 - head_w)
        if len(body) > 2:
            raise ValueError("key entry too long: %r" % pin["text"])
        drw.text((kx, ky), head, font=faces["key_p"], fill=PAL["navy"])
        drw.text((kx + head_w, ky), body[0], font=faces["key_t"],
                 fill=PAL["ink"])
        if len(body) > 1:
            drw.text((kx, ky + 13), body[1], font=faces["key_t"],
                     fill=PAL["ink"])
        ky += 25


def _grid(drw, faces, data):
    drw.text((16, 546), data["grid_title"], font=faces["sec"], fill=PAL["navy"])
    cw, chh, cg = 192, 92, 8
    for i, card in enumerate(data["grid"]):
        row, col = divmod(i, 5)
        x = 16 + col * (cw + cg)
        y = 572 + row * (chh + cg)
        drw.rectangle([x, y, x + cw, y + chh], fill=PAL["card"],
                      outline=PAL["card_edge"], width=1)
        GLYPHS[card["icon"]](drw, x + 8, y + 8, 24)
        blurb(drw, card["headline"], faces["card_h"], x + 38, y + 8, 146,
              PAL["ink"], leading=15, cap=2)
        blurb(drw, card["detail"], faces["card_d"], x + 8, y + 42, 176,
              PAL["muted"], leading=13, cap=3)


def _datecheck(drw, faces, data):
    drw.rectangle([16, 860, 1008, 988], outline=PAL["red"], width=2)
    drw.text((28, 870), data["date_check"]["title"], font=faces["dc_t"],
             fill=PAL["red"])
    for i, item in enumerate(data["date_check"]["items"]):
        col, row = divmod(i, 5)
        x = 32 + col * 488
        y = 896 + row * 19
        drw.text((x, y), "•  " + item, font=faces["dc_i"], fill=PAL["ink"])


def _footer(drw, faces, data):
    width, _ = SIZE
    ft = data["footer"]
    drw.text(((width - measure(faces["foot"], ft)) / 2, 998), ft,
             font=faces["foot"], fill=PAL["grey"])


# ------------------------------------------------------------------ build

def compose(stories_path, geojson_path, out_path):
    """Render the poster from stories.json + GeoJSON and save the PNG."""
    with open(stories_path, encoding="utf-8") as fh:
        data = json.load(fh)

    if geojson_path:
        with open(geojson_path, encoding="utf-8") as fh:
            geo = json.load(fh)
    else:
        req = urllib.request.Request(GEOJSON_URL,
                                     headers={"User-Agent": "makefun-v3"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            geo = json.loads(resp.read().decode("utf-8"))

    faces = {
        "mast": face("DejaVuSans-Bold.ttf", 38),
        "date": face("DejaVuSans-Bold.ttf", 15),
        "tag": face("DejaVuSans.ttf", 13),
        "kick": face("DejaVuSans-Bold.ttf", 13),
        "head": face("DejaVuSans-Bold.ttf", 29),
        "sub": face("DejaVuSans.ttf", 15),
        "stat_l": face("DejaVuSans-Bold.ttf", 11),
        "stat_p": face("DejaVuSans-Bold.ttf", 20),
        "stat_v": face("DejaVuSans.ttf", 13),
        "chart_t": face("DejaVuSans-Bold.ttf", 12),
        "chart_l": face("DejaVuSans-Bold.ttf", 15),
        "chart_n": face("DejaVuSans-Bold.ttf", 12),
        "chart_s": face("DejaVuSans.ttf", 10),
        "sec": face("DejaVuSans-Bold.ttf", 16),
        "pin_n": face("DejaVuSans-Bold.ttf", 11),
        "key_p": face("DejaVuSans-Bold.ttf", 11),
        "key_t": face("DejaVuSans.ttf", 11),
        "ocean": face("DejaVuSans-Bold.ttf", 10),
        "card_h": face("DejaVuSans-Bold.ttf", 13),
        "card_d": face("DejaVuSans.ttf", 11),
        "dc_t": face("DejaVuSans-Bold.ttf", 13),
        "dc_i": face("DejaVuSans.ttf", 12),
        "foot": face("DejaVuSans.ttf", 11),
    }

    img = Image.new("RGB", SIZE, PAL["paper"])
    drw = ImageDraw.Draw(img)
    _masthead(drw, faces, data)
    _lead(drw, faces, data["lead"])
    _chart(drw, faces, data["lead"])
    _map_section(img, drw, faces, geo, data)
    _grid(drw, faces, data)
    _datecheck(drw, faces, data)
    _footer(drw, faces, data)

    img.save(out_path, format="PNG", optimize=False)
    print("wrote %s (%dx%d)" % (out_path, SIZE[0], SIZE[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geojson", default=None)
    ap.add_argument("--stories", default=os.path.join(BASE, "stories.json"))
    ap.add_argument("--out", default=os.path.join(BASE, "entry.png"))
    args = ap.parse_args()
    compose(args.stories, args.geojson, args.out)


if __name__ == "__main__":
    main()
