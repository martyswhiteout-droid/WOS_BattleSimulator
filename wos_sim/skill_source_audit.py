"""Audit workbook skill mechanics against Whiteout Survival wiki text.

The engine consumes the workbook and local rules.  This module gives QA a
repeatable way to check that the workbook still matches the public Expedition
skill descriptions.  Network access is optional: by default it audits the
wiki-derived display cache, and ``--live`` refreshes text from the wiki pages.
"""
from __future__ import annotations

import argparse
import html
import re
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from wos_sim.loader import load_skill_book
from wos_sim.models import SkillSource
from wos_sim.predictor import skill_display
from wos_sim.troop_catalog import TROOP_SKILL_CATALOG

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "ENGINE_REBUILD" / "SKILL_SOURCE_AUDIT.md"
WIKI_BASE = "https://www.whiteoutsurvival.wiki/heroes"
HERO_SLUG_FIXES = {
    "Hank": "hank-2",
    "Viveca": "viveca-2",
}
_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


@dataclass
class Finding:
    hero: str
    slot: str
    status: str
    detail: str


def hero_slug(hero: str) -> str:
    if hero in HERO_SLUG_FIXES:
        return HERO_SLUG_FIXES[hero]
    slug = re.sub(r"[^a-z0-9]+", "-", hero.lower()).strip("-")
    return slug


def fetch_hero_page(hero: str, timeout: int = 20) -> str:
    url = f"{WIKI_BASE}/{hero_slug(hero)}/"
    req = urllib.request.Request(url, headers={"User-Agent": "wos-skill-audit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def html_to_text(markup: str) -> str:
    parser = _TextParser()
    parser.feed(markup)
    return html.unescape(parser.text())


def _max_percent(value: str) -> str:
    nums = re.findall(r"-?\d+(?:\.\d+)?", value)
    return f"{float(nums[-1]):g}%" if nums else value


def wiki_tokens(text: str) -> set[str]:
    """Normalize the max-level mechanics we care about for QA comparison."""
    text = text.replace("+ ", "+")
    tokens: set[str] = set()
    text = re.sub(r"(\d),(\d)", r"\1.\2", text)
    for word, number in _NUMBER_WORDS.items():
        text = re.sub(rf"\b{word}\b", number, text, flags=re.I)
    for ladder in re.findall(r"-?\d+(?:\.\d+)?%?(?:\s*/\s*-?\d+(?:\.\d+)?%?)+\s*%", text):
        tokens.add(_max_percent(ladder))
    for pct in re.findall(r"(?<![\d./])-?\d+(?:\.\d+)?%", text):
        tokens.add(_max_percent(pct))
    for every in re.findall(r"every\s+(\d+(?:\.\d+)?)\s+(turns?|attacks?|strikes?)", text, re.I):
        tokens.add(f"every {float(every[0]):g} {every[1].lower()}")
    for duration in re.findall(r"for\s+(\d+(?:\.\d+)?)\s+(turns?|attacks?|strikes?)", text, re.I):
        tokens.add(f"for {float(duration[0]):g} {duration[1].lower()}")
    for chance in re.findall(r"(\d+(?:\.\d+)?)%\s+chance", text, re.I):
        tokens.add(f"{float(chance):g}% chance")
    return tokens


def workbook_tokens(rows) -> set[str]:
    tokens: set[str] = set()
    for row in rows:
        values = []
        if row.amount_per_proc is not None:
            values.append(row.amount_per_proc)
        elif row.amount is not None:
            values.append(row.amount)
        if row.probability is not None:
            if abs(row.probability - 1.0) > 1e-9:
                tokens.add(f"{row.probability * 100:g}% chance")
        for value in values:
            if abs(value) <= 5:
                tokens.add(f"{abs(value) * 100:g}%")
        if (row.frequency is not None and row.trigger_unit is not None
                and abs(row.frequency - 1.0) > 1e-9):
            unit = row.trigger_unit.value.lower()
            if row.trigger_unit.value == "Strikes":
                unit = "attacks"
            tokens.add(f"every {row.frequency:g} {unit}")
        if (row.duration is not None and row.duration_unit is not None
                and abs(row.duration - 1.0) > 1e-9):
            tokens.add(f"for {row.duration:g} {row.duration_unit.value.lower()}")
    return tokens


def _cached_skill_text(hero: str, slot: str) -> str:
    data = skill_display._hero_data().get("heroes", {}).get(hero, {})
    for skill in data.get("skills") or []:
        if skill.get("slot") == slot:
            return skill.get("effect") or ""
    return ""


def _cached_skill_rows(hero: str) -> list[dict]:
    return skill_display._hero_data().get("heroes", {}).get(hero, {}).get("skills") or []


def _find_skill_title(text: str, title: str) -> int:
    idx = text.find(title)
    if idx >= 0:
        return idx
    base = re.sub(r"\s+Lv\.\d+\s*$", "", title).strip()
    match = re.search(rf"{re.escape(base)}\s+Lv\.\d+", text)
    return match.start() if match else -1


def _live_skill_text(hero: str) -> dict[str, str]:
    text = html_to_text(fetch_hero_page(hero))
    # The wiki renders tab labels before six skill blocks: 3 Exploration, then
    # 3 Expedition.  Plain-text HTML extraction does not preserve heading tags,
    # so use the cached display titles only as slot anchors and keep the live
    # page text as the audited evidence.
    anchors = []
    for skill in _cached_skill_rows(hero):
        slot = skill.get("slot")
        title = skill.get("name") or ""
        if not slot or not title:
            continue
        idx = _find_skill_title(text, title)
        if idx >= 0:
            anchors.append((idx, slot, title))
    anchors.sort()
    out: dict[str, str] = {}
    for i, (start, slot, _title) in enumerate(anchors):
        special_idx = text.find("\nSpecial", start)
        end = anchors[i + 1][0] if i + 1 < len(anchors) else special_idx
        if end < start:
            end = len(text)
        out[slot] = text[start:end].strip()
    return out


def audit_hero(hero: str, *, live: bool = False) -> list[Finding]:
    book = load_skill_book()
    live_text = _live_skill_text(hero) if live else {}
    findings: list[Finding] = []
    for source in (SkillSource.SKILL_1, SkillSource.SKILL_2, SkillSource.SKILL_3):
        slot = source.name.lower()
        slot = slot.replace("skill_", "skill_")
        rows = tuple(e for e in book.for_hero(hero) if e.source == source)
        if not rows:
            continue
        text = live_text.get(slot) if live_text else _cached_skill_text(hero, slot)
        if not text:
            findings.append(Finding(hero, slot, "missing_source", "No wiki/display text found."))
            continue
        expected = workbook_tokens(rows)
        observed = wiki_tokens(text)
        missing = sorted(t for t in expected if t not in observed)
        if missing:
            detail = f"Workbook tokens not found in wiki text: {', '.join(missing)}"
            findings.append(Finding(hero, slot, "mismatch", detail))
        else:
            findings.append(Finding(hero, slot, "ok", "Workbook mechanics align with wiki tokens."))
    return findings


def troop_skill_rule_tokens() -> dict[str, set[str]]:
    out = {}
    for skill in TROOP_SKILL_CATALOG:
        tokens = set()
        if skill.proc_chance is not None:
            tokens.add(f"{skill.proc_chance * 100:g}% chance")
        if skill.proc_amount is not None:
            tokens.add(f"{skill.proc_amount * 100:g}%")
        if skill.flat_offset is not None:
            tokens.add(f"flat {skill.flat_offset:g}")
        if skill.special:
            tokens.add(skill.special)
        out[skill.name] = tokens
    out["indomitable_wall"] = {"5 turns", "0.6% per level"}
    out["meridian_phalanx"] = {"5 turns", "1% per level"}
    out["starfire"] = {"every 5 turns", "0.5% per level"}
    return out


def run_audit(*, live: bool = False, heroes: list[str] | None = None,
              output: Path = DEFAULT_REPORT) -> list[Finding]:
    book = load_skill_book()
    heroes = heroes or book.heroes()
    findings: list[Finding] = []
    for hero in heroes:
        findings.extend(audit_hero(hero, live=live))
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Skill Source Audit",
        "",
        f"Mode: {'live wiki fetch' if live else 'local wiki-derived display cache'}",
        "",
        "| Hero | Slot | Status | Detail |",
        "|---|---|---|---|",
    ]
    for f in findings:
        lines.append(f"| {f.hero} | {f.slot} | {f.status} | {f.detail} |")
    lines.extend([
        "",
        "## Troop Skill Rule Tokens",
        "",
        "| Skill | Tokens |",
        "|---|---|",
    ])
    for name, tokens in troop_skill_rule_tokens().items():
        lines.append(f"| {name} | {', '.join(sorted(tokens))} |")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="fetch current wiki pages")
    parser.add_argument("--hero", action="append", help="limit audit to one hero; repeatable")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args(argv)
    findings = run_audit(live=args.live, heroes=args.hero, output=Path(args.output))
    bad = [f for f in findings if f.status != "ok"]
    print(f"wrote {args.output}: {len(findings)} checks, {len(bad)} non-ok")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
