"""Stage 3 shared loader for the deterministic-formula family elimination.

Loads the ACCEPTED Stage 2 constraint set (`stage2_constraints.json`) and
exposes, for every turn-clocked battle, an exact-rational WINNER-rate record
(and the one-sided LOSER-rate upper bound).  Nothing here fits or minimises
anything: it only re-expresses Stage 2's intervals in a shape convenient for
family elimination.

Rate semantics (from Stage 2): `winner_rate` is the damage ONE side deals per
own attack event, expressed as a fraction of ONE target unit's hidden HP, with
the winner stack's count factor g(N_winner) already folded in.  So

    winner_rate  ==  g(N_w) * ctr_w * Damage(A_w,L_w ; D_l,H_l) / HP(D_l,H_l)

for whatever (Damage, HP, g) a candidate family proposes.  A family is tested by
asking whether a single global scale (and any structural constants) can place the
predicted rate inside [lo, hi] for EVERY row simultaneously.

All numbers are Python `fractions.Fraction` so the exactness gate is exact.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
CONSTRAINTS_PATH = os.path.join(HERE, "stage2_constraints.json")


def F(x) -> Fraction:
    """Parse a Stage 2 rational string / int into a Fraction."""
    if isinstance(x, Fraction):
        return x
    return Fraction(str(x))


@dataclass(frozen=True)
class Side:
    role: str          # 'att' or 'def'
    count: int
    cls: str
    tier: int
    A: Fraction        # effective Attack (panels + hero/Vulc factors folded)
    D: Fraction        # effective Defense
    L: Fraction        # Lethality
    H: Fraction        # Health
    ctr: Fraction      # directional counter multiplier for THIS side's attacks


@dataclass(frozen=True)
class Interval:
    lo: Fraction
    hi: Fraction
    lo_closed: bool
    hi_closed: bool

    def contains(self, x: Fraction) -> bool:
        lo_ok = x >= self.lo if self.lo_closed else x > self.lo
        hi_ok = x <= self.hi if self.hi_closed else x < self.hi
        return lo_ok and hi_ok


@dataclass(frozen=True)
class WinnerRow:
    """One clocked battle, from the WINNER's (killing) perspective."""
    name: str
    ledger_line: int
    kind: str
    shape: str
    matchup: str
    winner_role: str
    duplicate_of: Optional[str]
    winner: Side       # the side that dealt the killing damage
    loser: Side        # the target that got wiped
    N_w: int           # winner stack live-count factor argument, g(N_w)
    N_l: int           # loser count (targets to deplete)
    # projected winner-rate intervals, per S2 branch:
    rate_plain: Optional[Interval]
    rate_nextatk: Optional[Interval]
    # one-sided loser per-event upper bound (winner finished uninjured), per branch:
    loser_ub_plain: Optional[Fraction]
    loser_ub_nextatk: Optional[Fraction]
    t_set: tuple


def _side(sd: dict, role: str) -> Side:
    return Side(
        role=role,
        count=int(sd["count"]),
        cls=sd["cls"],
        tier=int(sd["tier"]),
        A=F(sd["A_eff"]),
        D=F(sd["D_eff"]),
        L=F(sd["L"]),
        H=F(sd["H"]),
        ctr=F(sd["counter_mult"]),
    )


def _interval(block: dict) -> Optional[Interval]:
    if block is None:
        return None
    return Interval(
        lo=F(block["lo"]),
        hi=F(block["hi"]),
        lo_closed=bool(block.get("lo_closed", True)),
        hi_closed=bool(block.get("hi_closed", False)),
    )


def load_constraints(path: str = CONSTRAINTS_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def winner_rows(data: dict) -> list[WinnerRow]:
    """Every exact_1v1 / exact_clean_multi / winner_exact_loser_piecewise row
    that carries a projected winner-rate interval."""
    rows: list[WinnerRow] = []
    for b in data["battles"]:
        c = b.get("constraints", {})
        if c.get("type") not in ("exact_1v1", "exact_clean_multi",
                                  "winner_exact_loser_piecewise"):
            continue
        proj = c.get("projected")
        if not proj:
            continue
        wrole = c["winner_side"]
        lrole = "def" if wrole == "att" else "att"
        winner = _side(b["sides"][wrole], wrole)
        loser = _side(b["sides"][lrole], lrole)
        wcf = c.get("winner_count_factor", "g(1)")
        N_w = int(wcf[wcf.index("(") + 1: wcf.index(")")])
        rate_plain = _interval(proj.get("s2_plain", {}).get("winner_rate"))
        rate_next = _interval(proj.get("s2_nextatk", {}).get("winner_rate"))
        lub_p = proj.get("s2_plain", {}).get("loser_rate_ub", {})
        lub_n = proj.get("s2_nextatk", {}).get("loser_rate_ub", {})
        rows.append(WinnerRow(
            name=b["name"],
            ledger_line=b["ledger_line"],
            kind=c["type"],
            shape=b["shape"],
            matchup=b["matchup"],
            winner_role=wrole,
            duplicate_of=b.get("duplicate_of"),
            winner=winner,
            loser=loser,
            N_w=N_w,
            N_l=loser.count,
            rate_plain=rate_plain,
            rate_nextatk=rate_next,
            loser_ub_plain=F(lub_p["ub"]) if lub_p and "ub" in lub_p else None,
            loser_ub_nextatk=F(lub_n["ub"]) if lub_n and "ub" in lub_n else None,
            t_set=tuple(b["turns"]["t_set"]),
        ))
    return rows


def true_1v1(rows: list[WinnerRow], include_duplicates: bool = False) -> list[WinnerRow]:
    out = []
    for r in rows:
        if r.winner.count == 1 and r.loser.count == 1:
            if not include_duplicates and r.duplicate_of:
                continue
            out.append(r)
    return out


if __name__ == "__main__":
    data = load_constraints()
    rows = winner_rows(data)
    t11 = true_1v1(rows)
    print(f"loaded {len(rows)} clocked winner-rows; {len(t11)} true 1v1 "
          f"(duplicates excluded)")
    for r in t11:
        rp = r.rate_plain
        print(f"L{r.ledger_line:>2} {r.matchup:<16} W={r.winner_role} "
              f"A_w={float(r.winner.A):.5f} L_w={float(r.winner.L):.3g} "
              f"D_l={float(r.loser.D):.4g} H_l={float(r.loser.H):.4g} "
              f"ctr={r.winner.ctr} rate=[{float(rp.lo):.7f},{float(rp.hi):.7f}]")
