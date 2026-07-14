"""UI style guard (visual twin of the golden-anchor guardrail).

Locks the front-end's design system so out-of-context edits can't drift:
the palette is baselined, the page must stay self-contained (no CDNs /
external fonts / Tailwind-style runtimes), fonts and the reduced-motion
kill-switch are pinned, and the !important count may not grow.

Rules live in prototype/DESIGN_SYSTEM.md. A NEW color is allowed only as a
deliberate act:

    py -m wos_sim.predictor.tests.test_ui_style_guard --update-baseline

then state why in the commit message.
"""
import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PAGE = REPO / "prototype" / "index.html"
BASELINE = REPO / "prototype" / "style_baseline.json"

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
RGB_RE = re.compile(r"rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)")
URL_RE = re.compile(r"https?://[^\"'`\s)<>]+")
FONTFACE_RE = re.compile(r"@font-face\s*\{[^}]*\}", re.S)

ALLOWED_URLS = {"http://www.w3.org/2000/svg"}          # SVG xmlns only
ALLOWED_FONT_FAMILIES = {"Chakra Petch", "IBM Plex Mono", "Inter"}
FORBIDDEN_TOKENS = [
    "cdn.tailwindcss", "tailwind", "bootstrap", "fonts.googleapis",
    "fonts.gstatic", "unpkg.com", "jsdelivr", "cdnjs", "@import",
]
MOJIBAKE = ["Â", "â€", "â—", "âš"]  # UX_BACKLOG section 0


def read_page():
    return PAGE.read_text(encoding="utf-8")


def extract_colors(text):
    """Every literal color in the file (CSS, JS chart colors, inline styles)."""
    colors = set()
    for m in HEX_RE.findall(text):
        colors.add(m.lower())
    for m in RGB_RE.findall(text):
        colors.add(re.sub(r"\s+", "", m).lower())
    return colors


def current_snapshot():
    text = read_page()
    return {
        "file": "prototype/index.html",
        "colors": sorted(extract_colors(text)),
        "important_budget": text.count("!important"),
        "note": ("Palette lock for prototype/DESIGN_SYSTEM.md. Regenerate ONLY "
                 "deliberately: py -m wos_sim.predictor.tests.test_ui_style_guard "
                 "--update-baseline (and say why in the commit)."),
    }


class TestUiStyleGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read_page()
        cls.baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    def test_palette_locked(self):
        new = sorted(extract_colors(self.text) - set(self.baseline["colors"]))
        self.assertEqual(
            new, [],
            "New color literal(s) not in prototype/style_baseline.json: "
            f"{new}. Reuse a token from prototype/DESIGN_SYSTEM.md section 3 "
            "(shades/alphas of existing hues are listed there). If the new color is a "
            "deliberate design decision, regenerate the baseline via "
            "--update-baseline and justify it in the commit message.")

    def test_no_new_color_syntaxes(self):
        # Palette lock only parses hex + rgb()/rgba(); adding other syntaxes
        # would silently bypass it, so they require touching this guard.
        for token in ("hsl(", "hsla(", "lab(", "lch(", "oklch(", "oklab("):
            self.assertNotIn(
                token, self.text,
                f"'{token}' found — the palette guard doesn't parse this color "
                "syntax. Stick to hex/rgba, or extend extract_colors() first.")

    def test_page_is_self_contained(self):
        urls = sorted(set(URL_RE.findall(self.text)) - ALLOWED_URLS)
        self.assertEqual(
            urls, [],
            f"External URL(s) in the page: {urls}. index.html must stay fully "
            "local/offline (DESIGN_SYSTEM.md section 2.2) — bundle assets under "
            "prototype/assets/ instead.")
        low = self.text.lower()
        hits = [t for t in FORBIDDEN_TOKENS if t in low]
        self.assertEqual(
            hits, [],
            f"Forbidden framework/CDN token(s) {hits} — no Tailwind/Bootstrap/"
            "@import; the page's own design system covers styling "
            "(DESIGN_SYSTEM.md section 2.2).")

    def test_fonts_locked_and_local(self):
        faces = FONTFACE_RE.findall(self.text)
        self.assertTrue(faces, "Expected @font-face declarations to exist.")
        for face in faces:
            fam = re.search(r"font-family\s*:\s*['\"]?([^'\";]+)", face)
            self.assertIsNotNone(fam, f"Unparseable @font-face: {face[:80]}")
            self.assertIn(
                fam.group(1).strip(), ALLOWED_FONT_FAMILIES,
                f"New font family '{fam.group(1).strip()}' — the type system is "
                "Chakra Petch / Inter / IBM Plex Mono only (DESIGN_SYSTEM.md section 3).")
            src = re.search(r"url\(['\"]?([^'\")]+)", face)
            self.assertIsNotNone(src, f"@font-face without src url: {face[:80]}")
            self.assertTrue(
                src.group(1).startswith("assets/fonts/"),
                f"Font src '{src.group(1)}' must live in prototype/assets/fonts/.")

    def test_reduced_motion_killswitch_present(self):
        flat = re.sub(r"\s+", "", self.text)
        self.assertIn(
            "@media(prefers-reduced-motion:reduce){*{transition:none!important;"
            "animation:none!important}}", flat,
            "The global reduced-motion kill-switch was removed/altered — it must "
            "survive every edit (DESIGN_SYSTEM.md section 2.4).")

    def test_important_budget_not_exceeded(self):
        n = self.text.count("!important")
        self.assertLessEqual(
            n, self.baseline["important_budget"],
            f"!important count grew to {n} (budget "
            f"{self.baseline['important_budget']}). Fix specificity with source "
            "order/scoping instead (append-only rounds win by being later).")

    def test_encoding_clean(self):
        raw = PAGE.read_bytes()
        raw.decode("utf-8")  # raises on corruption
        for seq in MOJIBAKE:
            self.assertNotIn(
                seq, self.text,
                "Mojibake marker found — the 2026-07-07 double-encoding incident "
                "recurred. See UX_BACKLOG.md section 0 before saving this file again.")


if __name__ == "__main__":
    if "--update-baseline" in sys.argv:
        snap = current_snapshot()
        BASELINE.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
        print(f"Baseline rewritten: {BASELINE} "
              f"({len(snap['colors'])} colors, !important budget "
              f"{snap['important_budget']}). Justify this in your commit.")
    else:
        unittest.main()
