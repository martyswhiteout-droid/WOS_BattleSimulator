# Real-game sample images (S1/S2 upload guides)

Cropped + downscaled from the owner's own fixture captures in
`shell/tests/fixtures/panel_ocr/images/` (owner request 2026-08-15: samples
must be real game screenshots, not drawn mock-ups). Served by the
`/shell/ocr/client` static mount; `screens/pick_upload.mjs::renderSample`
references them, and `renderSampleFallback` (the hand-drawn mini-panels)
takes over automatically via the img-error listener in `ocr_flow.js` when
these files are absent — which is the EXPECTED state in a promoted bundle
(game-UI screenshots are Century Games IP; PRODUCTION_CRITERIA F1 /
promote.py's raster strip. If promote's strip list doesn't yet cover this
folder, add it there rather than shipping these).

Regeneration (Pillow; fractions are normalized x0,y0,x1,y1 of the source):

| file | source | crop box | width |
|---|---|---|---|
| sample_battle_heroes.jpg | C_battle_1.png | 0.02, 0.365, 0.98, 0.915 | 560 |
| sample_battle_panel.jpg | C_battle_3.png | 0.00, 0.395, 1.00, 0.615 | 560 |
| sample_battle_popup.jpg | C_battle_4.png | 0.02, 0.20, 0.98, 0.46 | 640 |
| sample_scout.jpg | C_scout.png | 0.03, 0.525, 0.97, 0.92 | 560 |
| sample_citystats.jpg | C_citystats_1.png | 0.00, 0.00, 1.00, 1.00 | 560 |

JPEG quality 84, optimize=True; target = "Stat Bonuses" title + ~3 rows
(the shape users recognize), 15-25KB each.

Owner feedback 2026-08-25: scout + citystats samples are LONG-FORM (the
full panel, not a 3-row teaser); the heroes sample is the report's Hero
Comparison + Expert Comparison sections ('Heroes + Experts' row).
sample_troop_power.jpg = the owner's own capture of the Troop Power
Comparison screen (2026-09-06; 527x389, whole screen, JPEG q86, ~41KB) -
served as the Troops row sample; the drawn mini-panel is its img-error
fallback for promoted bundles.
