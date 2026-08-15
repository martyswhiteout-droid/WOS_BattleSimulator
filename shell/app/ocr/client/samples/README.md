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
| sample_battle_heroes.jpg | C_battle_3.png | 0.00, 0.115, 1.00, 0.40 | 560 |
| sample_battle_panel.jpg | C_battle_3.png | 0.00, 0.395, 1.00, 0.615 | 560 |
| sample_battle_popup.jpg | C_battle_4.png | 0.02, 0.20, 0.98, 0.46 | 640 |
| sample_scout.jpg | C_scout.png | 0.00, 0.505, 1.00, 0.685 | 560 |
| sample_citystats.jpg | C_citystats_1.png | 0.00, 0.00, 1.00, 0.31 | 560 |

JPEG quality 84, optimize=True; target = "Stat Bonuses" title + ~3 rows
(the shape users recognize), 15-25KB each.
