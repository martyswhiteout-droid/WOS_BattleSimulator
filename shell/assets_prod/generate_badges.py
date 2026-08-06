"""shell/assets_prod/generate_badges.py — deterministic generator for the
original SVG badge/chip pack (PRODUCTION_PLAN.md §2.5, PRODUCTION_CRITERIA F1).

Everything emitted here is ORIGINAL code-drawn geometry (hex frames, numerals,
rounded chips) in the prototype design-system palette
(prototype/DESIGN_SYSTEM.md). Nothing is derived from Century Games artwork.

Run from repo root:  python shell/assets_prod/generate_badges.py
Rewrites: gen_01.svg .. gen_14.svg, chip_rarity_*.svg, chip_role_*.svg,
and manifest.json (which also indexes the hand-drawn class emblems).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

# Palette tokens (prototype/DESIGN_SYSTEM.md)
PANEL = "#0B273D"; RAISED = "#123B59"; LIT = "#164A72"
TEXT = "#EAF6FF"; MUTED = "#B9D2E5"
BLUE = "#2EA1F2"; BLUE_BRIGHT = "#55BFFF"; BLUE_DEEP = "#1682D8"; FOCUS = "#5AAEF3"
RED = "#EF5F5F"; RED_DEEP = "#C94646"
GOLD = "#D9A94F"; CREAM = "#FDEFD3"; CREAM2 = "#F7E3B9"; CREAM_BORDER = "#E7C783"
PERI = "#93A0C8"; PERI_DEEP = "#6E7CA8"

FONT = "'Chakra Petch','IBM Plex Mono',Inter,system-ui,sans-serif"
GEN_COUNT = 14  # framed numeral badges 1..14 (hero generations)

HEADER = ("<!-- ORIGINAL code-drawn badge (WoS Battle Simulator shell). "
          "Generic framed geometry; not derived from any Century Games "
          "artwork. Palette: prototype/DESIGN_SYSTEM.md. -->")


def gen_badge(n: int) -> str:
    """Hexagonal framed numeral badge for hero generation n."""
    label = str(n)
    fs = 26 if n < 10 else 22
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" role="img" aria-label="Generation {n} badge">
  {HEADER}
  <defs>
    <linearGradient id="g{n}f" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{LIT}"/><stop offset="1" stop-color="{PANEL}"/>
    </linearGradient>
  </defs>
  <path d="M24 2 L43 13 V35 L24 46 L5 35 V13 Z" fill="url(#g{n}f)"
        stroke="{GOLD}" stroke-width="2.5" stroke-linejoin="round"/>
  <path d="M24 6.4 L39.2 15.2 V32.8 L24 41.6 L8.8 32.8 V15.2 Z" fill="none"
        stroke="{MUTED}" stroke-opacity="0.3" stroke-width="1.1"/>
  <text x="24" y="{24 + fs * 0.36:.1f}" text-anchor="middle"
        font-family="{FONT}" font-weight="700" font-size="{fs}"
        fill="{TEXT}">{label}</text>
</svg>
"""


def chip(label: str, aria: str, face_top: str, face_bot: str, border: str,
         text: str, width: int = 84) -> str:
    """Rounded rarity/role chip with a text label."""
    gid = label.lower().replace(" ", "")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 26" role="img" aria-label="{aria}">
  {HEADER}
  <defs>
    <linearGradient id="c{gid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{face_top}"/><stop offset="1" stop-color="{face_bot}"/>
    </linearGradient>
  </defs>
  <rect x="1.5" y="1.5" width="{width - 3}" height="23" rx="11.5"
        fill="url(#c{gid})" stroke="{border}" stroke-width="1.6"/>
  <text x="{width / 2:.0f}" y="17.5" text-anchor="middle" font-family="{FONT}"
        font-weight="700" font-size="11.5" letter-spacing="1.2"
        fill="{text}">{label}</text>
</svg>
"""


def main() -> None:
    files: dict[str, str] = {}

    # Generation numeral badges
    for n in range(1, GEN_COUNT + 1):
        name = f"gen_{n:02d}.svg"
        (HERE / name).write_text(gen_badge(n), encoding="utf-8", newline="\n")
        files[f"gen.{n}"] = name

    # Rarity chips (palette-locked tiers: blue / periwinkle / gold)
    rarities = [
        ("RARE",   "Rare rarity chip",   BLUE_BRIGHT, BLUE_DEEP, FOCUS, TEXT),
        ("EPIC",   "Epic rarity chip",   PERI,        PERI_DEEP, PERI,  TEXT),
        ("MYTHIC", "Mythic rarity chip", CREAM,       CREAM2,    GOLD,  "#8d5b31"),
    ]
    for label, aria, top, bot, border, text in rarities:
        name = f"chip_rarity_{label.lower()}.svg"
        (HERE / name).write_text(chip(label, aria, top, bot, border, text),
                                 encoding="utf-8", newline="\n")
        files[f"rarity.{label.lower()}"] = name

    # Role chips
    roles = [
        ("RALLY",    "Rally role chip",    RED,    RED_DEEP,  RED_DEEP, TEXT, 84),
        ("GARRISON", "Garrison role chip", BLUE,   BLUE_DEEP, FOCUS,    TEXT, 100),
    ]
    for label, aria, top, bot, border, text, w in roles:
        name = f"chip_role_{label.lower()}.svg"
        (HERE / name).write_text(chip(label, aria, top, bot, border, text, w),
                                 encoding="utf-8", newline="\n")
        files[f"role.{label.lower()}"] = name

    # Class emblems (hand-drawn, kept in this directory)
    files["class.infantry"] = "class_infantry.svg"
    files["class.lancer"] = "class_lancer.svg"
    files["class.marksman"] = "class_marksman.svg"

    manifest = {
        "version": 1,
        "generated_by": "shell/assets_prod/generate_badges.py",
        "license": ("Original code-drawn SVG artwork created for the WoS "
                    "Battle Simulator production shell. Not derived from, and "
                    "not containing, any Century Games / Whiteout Survival "
                    "assets. Safe to ship (PRODUCTION_CRITERIA F1)."),
        "palette_source": "prototype/DESIGN_SYSTEM.md",
        "assets": dict(sorted(files.items())),
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"assets_prod: wrote {len(files)} assets + manifest.json")


if __name__ == "__main__":
    main()
