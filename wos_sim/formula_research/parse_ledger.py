"""Stage 1: parse NANOMART_EXPERIMENT_LEDGER.md into a clean dataset (JSON).
Stats in, outcomes kept SEPARATE (never inputs). Run: py parse_ledger.py"""
import json, re, os

SRC = os.path.join(os.path.dirname(__file__), "..", "data", "experiments", "NANOMART_EXPERIMENT_LEDGER.md")
OUT = os.path.join(os.path.dirname(__file__), "ledger_dataset.json")

def force(cell):
    m = re.search(r"(\d+)\s+(Infantry|Lancer|Marksman)\s+T(\d+)", cell)
    return {"count": int(m.group(1)), "cls": m.group(2), "tier": int(m.group(3))} if m else None

def stats(cell):
    m = re.findall(r"[\d.]+", cell)
    return {"A": float(m[0]), "D": float(m[1]), "L": float(m[2]), "H": float(m[3])} if len(m) >= 4 else None

def outcome(cell):
    d = {}
    for k, pat in (("power", r"P(-?\d+)"), ("loss", r"Loss(\d+)"), ("inj", r"Inj(\d+)"),
                   ("light", r"Light(\d+)"), ("surv", r"Surv(\d+)"), ("kills", r"K(\d+)")):
        m = re.search(pat, cell.replace(",", ""))
        d[k] = int(m.group(1)) if m else None
    return d

def heroes(cell):
    h = {}
    m = re.search(r"Seo-yoon Skill 1 L(\d)", cell)
    if m: h["seoyoon_s1"] = int(m.group(1))
    # Effect text between "Skill N" and "[T../K..]" may contain any punctuation
    # (":", "%", ",", "..."), so only exclude "[" — the old [\w ]*? pattern
    # silently dropped every Vulcanus tag. "TNC"/"K-"/"K?" mean not captured.
    for s in re.finditer(r"Vulcanus Skill (\d)[^\[]*\[T([^/\]]+)/K([^\]]+)\]", cell):
        h[f"vulc_s{s.group(1)}_T"] = int(s.group(2)) if s.group(2).isdigit() else None
        h[f"vulc_s{s.group(1)}_K"] = int(s.group(3)) if s.group(3).isdigit() else None
    return h

rows = []
for line in open(SRC, encoding="utf-8"):
    if not line.startswith("| NanoMart"): continue
    c = [x.strip() for x in line.split(" | ")]
    if len(c) < 20: continue
    tm = re.search(r"(\d+)-(\d+)", c[18])
    rows.append({
        "name": c[0].lstrip("| ").strip(),
        "att": {"force": force(c[4]), "stats": stats(c[6]), "heroes": heroes(c[7]), "out": outcome(c[9])},
        "def": {"force": force(c[10]), "stats": stats(c[12]), "heroes": heroes(c[13]), "out": outcome(c[15])},
        "winner": c[16],
        "turns_lo": int(tm.group(1)) if tm else None,
        "turns_hi": int(tm.group(2)) if tm else None,
    })
json.dump(rows, open(OUT, "w"), indent=1)
ok = [r for r in rows if r["att"]["force"] and r["def"]["force"] and r["att"]["stats"] and r["def"]["stats"]]
clocked = [r for r in ok if r["turns_lo"]]
print(f"parsed rows: {len(rows)}  fully-usable: {len(ok)}  with turn clock: {len(clocked)}")
print("sample:", json.dumps(rows[6], indent=1)[:600])
