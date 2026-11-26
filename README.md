# THE WORLD IN PICTURES — 26 November 2026

Entry for make.fun competition **news-image-20261126**: "Sum up 26 November's
world news in one image". $100 USDC, top 50 paid.

One 1024×1024 PNG: a masthead, a lead panel (oil jumps as Gulf shipping is
hit — Brent +3.5%, WTI +2.0%), a real world map (Natural Earth 110m
coastlines) with 10 numbered pins, a 15-card story grid, and a DATE CHECK box
naming 10 look-alike stories that are NOT from 26 November.

26 distinct stories, each first reported Thu 26 Nov 2026 (WIB day).
Render: `python3 render.py --geojson ../work/ne_110m_land.geojson` (reads
`stories.json`, writes `entry.png`). The graded program is `main.ts`
(Node 22, stdlib only, no network): it writes the embedded PNG to
`MAKEFUN_OUTPUT_DIR/entry.png`.

Sources: Reuters, AP, Bank of Korea, dailysummaryof, One Turn.
