import re
CLASSES = ("Infantry", "Lancer", "Marksman")
STATS = ("Attack", "Defense", "Lethality", "Health")
_SPECIALS = (
    "Defender Troops' Attack", "Defender Troops' Health",
    "Enemy Defense Penalty (Pet Skill)", "Enemy Lethality Penalty (Pet Skill)", "Enemy Health Penalty (Pet Skill)",
    "Attack Bonus (Pet Skill)", "Defense Bonus (Pet Skill)", "Lethality Bonus (Pet Skill)", "Health Bonus (Pet Skill)",
    "Territory Defender Attack", "Territory Defender Defense",
    "Defender Troops Attack When Defending Own City", "Defender Troops Defense When Defending Own City",
    "Enemy Lethality Penalty (Expert Skill)", "Enemy Attack Penalty (Pet Skill)",
    "Attack Bonus", "Defense Bonus", "Lethality Bonus", "Health Bonus",
    "Enemy Attack Reduction", "Enemy Defense Reduction",
)
_META = ("Deployment Capacity", "March Queue", "March Speed Up", "Training Capacity", "Training Speed", "Healing Speed")
_HEADERS = ("Bonus Overview", "Stat Bonuses", "Military", "Troops Total", "Lootable")

def _skeleton(s):
    s = s.lower().replace("’", "'").replace('"', "'")
    s = s.replace("0", "o").replace("1", "l")
    return re.sub(r"[^a-z]", "", s)

def _dist(a, b):
    if abs(len(a) - len(b)) > 2:
        return 3
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
        if min(prev) > 2:
            return 3
    return prev[-1]

_CANON = {}
for _c in CLASSES:
    for _s in STATS:
        _CANON[_skeleton(f"{_c} {_s}")] = f"{_c}|{_s}"
for _s in STATS:
    _CANON[_skeleton(f"Troops' {_s}")] = f"Troops|{_s}"
for _sp in _SPECIALS:
    _CANON[_skeleton(_sp)] = f"special:{_sp}"
for _m in _META:
    _CANON[_skeleton(_m)] = f"meta:{_m}"
for _h in _HEADERS:
    _CANON[_skeleton(_h)] = f"header:{_h}"

def match_label(raw):
    sk = _skeleton(raw or "")
    if len(sk) < 4:
        return None
    if sk in _CANON:
        return _CANON[sk]
    best, bestd = None, 3
    for k, v in _CANON.items():
        d = _dist(sk, k)
        if d < bestd:
            best, bestd = v, d
    return best if bestd <= 2 else None
