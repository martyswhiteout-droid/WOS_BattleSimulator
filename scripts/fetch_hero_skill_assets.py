"""Fetch expedition skill display metadata from whiteoutsurvival.wiki.

This creates the display layer used by the predictor UI:
- hero expedition skill names
- max-level tooltip text
- local icon asset paths

The simulator's numeric skill effects still come from the workbook/model code.
"""
from __future__ import annotations

import html
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HERO_GENERATIONS = ROOT / "wos_sim" / "data" / "hero_generations.json"
DATA_DIR = ROOT / "wos_sim" / "data" / "skill_display"
ASSET_DIR = ROOT / "prototype" / "assets" / "hero_skills"
AVATAR_DIR = ROOT / "prototype" / "avatars"
AVATAR_MANIFEST = AVATAR_DIR / "manifest.json"
FRONTEND_JS = ROOT / "prototype" / "assets" / "skill_display.js"
TROOP_DISPLAY = DATA_DIR / "troop_skills.json"
BASE_URL = "https://www.whiteoutsurvival.wiki/heroes/{slug}/"
SLUG_OVERRIDES = {
    "Gwen": "gwen-2",
    "Hank": "hank-2",
    "Ling Xue": "ling-shuang",
    "Nora": "gwen",
    "Viveca": "viveca-2",
}


def slugify(name: str) -> str:
    if name in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[name]
    slug = name.lower().replace("&", "and")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def clean_text(raw: str) -> str:
    raw = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    return re.sub(r"\s+", " ", raw).strip()


def fetch_bytes(url: str, *, retries: int = 2) -> bytes:
    parts = urlsplit(url)
    url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, parts.fragment))
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=25) as resp:
                return resp.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last}")


def extract_expedition_skills(page_html: str) -> list[dict]:
    match = re.search(
        r'<div class="tab-pane fade" id="expedition-skills"[^>]*>(.*?)'
        r'<div class="tab-pane fade" id="special-skills"',
        page_html,
        flags=re.S,
    )
    if not match:
        return []
    section = match.group(1)
    skills = []
    for icon_url, name, effect in re.findall(
        r'<img\s+src="([^"]*)"[^>]*>\s*</div>\s*'
        r'<div class="col">\s*<h5[^>]*>(.*?)</h5>\s*'
        r'<p[^>]*>(.*?)</p>',
        section,
        flags=re.S,
    ):
        name_text = clean_text(name)
        if not icon_url or not name_text:
            continue
        skills.append({
            "slot": f"skill_{len(skills) + 1}",
            "name": name_text,
            "effect": clean_text(effect),
            "source_icon_url": html.unescape(icon_url),
        })
    return skills[:3]


def extract_profile_image(page_html: str) -> str | None:
    match = re.search(r'<img\s+src="([^"]*)"[^>]*alt="post_image"', page_html)
    return html.unescape(match.group(1)) if match else None


def avatar_filename(hero: str, avatar_url: str) -> str:
    suffix = Path(urlparse(avatar_url).path).suffix or ".png"
    return f"{hero}{suffix.lower()}"


def update_avatar_manifest(hero: str, generation, troop: str, filename: str,
                           source_url: str, data: bytes) -> None:
    manifest = json.loads(AVATAR_MANIFEST.read_text(encoding="utf-8")) if AVATAR_MANIFEST.exists() else []
    manifest = [row for row in manifest if row.get("hero") != hero]
    manifest.append({
        "hero": hero,
        "troop_type": troop,
        "generation": str(generation),
        "file": filename,
        "source_media": source_url,
        "sha1": hashlib.sha1(data).hexdigest(),
        "bytes": len(data),
    })
    manifest.sort(key=lambda row: (str(row.get("generation")) == "SR",
                                   -int(row.get("generation")) if str(row.get("generation")).isdigit() else 0,
                                   row.get("hero", "")))
    AVATAR_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_hero(hero: str, meta: dict) -> tuple[dict | None, str | None]:
    slug = slugify(hero)
    url = BASE_URL.format(slug=slug)
    try:
        page = fetch_bytes(url).decode("utf-8", "replace")
    except RuntimeError as exc:
        return None, str(exc)
    skills = extract_expedition_skills(page)
    if not skills:
        return None, f"found no expedition skills at {url}"

    avatar_url = extract_profile_image(page)
    if avatar_url:
        AVATAR_DIR.mkdir(parents=True, exist_ok=True)
        avatar_name = avatar_filename(hero, avatar_url)
        avatar_path = AVATAR_DIR / avatar_name
        avatar_bytes = fetch_bytes(avatar_url)
        avatar_path.write_bytes(avatar_bytes)
        update_avatar_manifest(hero, meta.get("generation"), meta.get("troop", ""),
                               avatar_name, avatar_url, avatar_bytes)

    hero_dir = ASSET_DIR / slug
    hero_dir.mkdir(parents=True, exist_ok=True)
    for skill in skills:
        icon_url = skill["source_icon_url"]
        suffix = Path(urlparse(icon_url).path).suffix or ".png"
        icon_name = f"{skill['slot']}{suffix}"
        icon_path = hero_dir / icon_name
        if not icon_path.exists():
            icon_path.write_bytes(fetch_bytes(icon_url))
        skill["icon"] = f"assets/hero_skills/{slug}/{icon_name}"

    return {
        "source_url": url,
        "avatar": f"avatars/{avatar_name}" if avatar_url else None,
        "skills": skills,
    }, None


def main() -> int:
    heroes = json.loads(HERO_GENERATIONS.read_text(encoding="utf-8"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "source": "https://www.whiteoutsurvival.wiki/heroes/",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "level_assumption": "All expedition skills are treated as level 5 / max; effect text keeps the wiki's full level ladder.",
        "heroes": {},
        "errors": {},
    }
    for hero, meta in sorted(heroes.items()):
        record, error = fetch_hero(hero, meta)
        if record:
            out["heroes"][hero] = record
            print(f"ok {hero}")
        else:
            out["errors"][hero] = error
            print(f"ERR {hero}: {error}")

    data_path = DATA_DIR / "hero_skills.json"
    data_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    troop = json.loads(TROOP_DISPLAY.read_text(encoding="utf-8")) if TROOP_DISPLAY.exists() else {}
    js = (
        "window.HERO_SKILL_DISPLAY = "
        + json.dumps(out, ensure_ascii=False, separators=(",", ":"))
        + ";\nwindow.TROOP_SKILL_DISPLAY = "
        + json.dumps(troop, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )
    FRONTEND_JS.write_text(js, encoding="utf-8")
    print(f"wrote {data_path}")
    print(f"wrote {FRONTEND_JS}")
    return 0 if not out["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
