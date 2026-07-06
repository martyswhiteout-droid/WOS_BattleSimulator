"""Battle report data model + ingestion (reports are the fitting dataset).

A report is extracted from 7 screenshot panels (procedure in GAME_RULES.md):
  1 Overview          - roles (sword=attacker / shield=defender), troops,
                        losses, injured, lightly injured, survivors
  2 Troop comparison  - per-class share %, FC badge, avg tier level
  3 Stat Bonuses      - scouted stats both sides (12 params each)
  4 Special Bonuses   - item / widget / pet layers incl. enemy penalties
  5 Lead skill detail - captain heroes, per-skill trigger counts + kills
  6/7 Joiners         - per-joiner flag hero, troops, kills, casualties

Friendly side is ALWAYS the left column; friendly may be attacker or
defender. Killed = Losses + Injured. Troops = Killed + Lightly Injured +
Survivors. The side reaching 0 survivors first loses.

Joiner universality: every troop in a rally/garrison enjoys the same
scouted stats, lead skills, and top-4 joiner first-skills regardless of
which heroes that joiner brought. Only troop type / quality / quantity
differ per joiner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from .models import StatType, TroopType

REPORTS_DIR = Path(__file__).resolve().parent / "data" / "reports"


class BattleRole(StrEnum):
    ATTACKER = "Attacker"   # white sword icon on avatar
    DEFENDER = "Defender"   # white shield icon on avatar


@dataclass(frozen=True)
class TroopGroup:
    """One troop class in the pre-battle comparison panel."""

    troop_type: TroopType
    share: float        # fraction of the side's total troops
    fc_badge: int       # 10 = 100% FC10; 9 = NOT all FC10, average ~FC9
    tier_level: float   # weighted average tier, e.g. 11.0

    def count(self, total_troops: int) -> float:
        return total_troops * self.share


@dataclass(frozen=True)
class SpecialBonus:
    """One row of the "Notes on Special Bonuses" panel (per side)."""

    label: str          # e.g. "Troops' Attack Bonus", "Rally Troops' Attack"
    value: float        # decimal fraction, sign as displayed
    source: str         # "item" / "widget" / "pet"
    stat: StatType
    applies_to: str     # "own" or "enemy" (Enemy Troops' X rows debuff the foe)


@dataclass(frozen=True)
class SkillTriggerRow:
    """One row of the Battle Details skill table for a lead hero."""

    skill: str          # identified skill name, or "icon:<description>" if TBD
    triggered: int
    kills: int = 0
    identified: bool = True


@dataclass(frozen=True)
class LeadHero:
    name: str
    level: int
    stars: str | None = None
    rows: tuple[SkillTriggerRow, ...] = ()


@dataclass(frozen=True)
class ParticipantRow:
    """One troop-class line in a participant's panel-6/7 block."""

    troop_type: TroopType
    kills: int              # enemy units killed by this class (pro-rata share)
    losses: int
    injured: int            # stored positive (panel displays negative)
    lightly_injured: int
    survivors: int
    fc_badge: int | None = None

    @property
    def total(self) -> int:
        return self.losses + self.injured + self.lightly_injured + self.survivors

    @property
    def incapacitated(self) -> int:
        return self.losses + self.injured + self.lightly_injured


@dataclass(frozen=True)
class Participant:
    """One rally/garrison participant block (captain = first block)."""

    player: str
    is_captain: bool
    troops: int
    kills: int
    power_loss: int
    rows: tuple[ParticipantRow, ...]
    flag_hero: str | None = None   # slot-1 hero (None = not yet identified)

    def identity_errors(self) -> list[str]:
        if not self.rows:   # collapsed block in the screenshot: totals only
            return []
        errors = []
        if sum(r.total for r in self.rows) != self.troops:
            errors.append(f"{self.player}: rows sum {sum(r.total for r in self.rows):,}"
                          f" != troops {self.troops:,}")
        if sum(r.kills for r in self.rows) != self.kills:
            errors.append(f"{self.player}: row kills sum != kills badge {self.kills:,}")
        return errors


@dataclass
class ReportSide:
    player: str
    state: int
    role: BattleRole
    is_friendly: bool
    power_loss: int
    troops: int
    losses: int
    injured: int
    lightly_injured: int
    survivors: int
    composition: dict[TroopType, TroopGroup] = field(default_factory=dict)
    scouted: dict[tuple[TroopType, StatType], float] = field(default_factory=dict)
    specials: list[SpecialBonus] = field(default_factory=list)
    lead_heroes: list[LeadHero] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    joiner_flags: list[str] = field(default_factory=list)  # fallback when the
    # participant panel is unavailable (older reports show only top-4 detail)
    coords: str | None = None

    @property
    def killed(self) -> int:
        return self.losses + self.injured

    @property
    def captain(self) -> Participant | None:
        """The captain: in a RALLY always the first block; in a GARRISON the
        game auto-selects the strongest player regardless of position (mark
        that block is_captain in the data). Falls back to the first block."""
        for p in self.participants:
            if p.is_captain:
                return p
        return self.participants[0] if self.participants else None

    def active_joiners(self) -> list[Participant]:
        """The first four NON-CAPTAIN blocks from the top; their flag heroes'
        Skill 1 activates. All skill levels assumed 5 (confirmed)."""
        captain = self.captain
        return [p for p in self.participants if p is not captain][:4]

    def joiner_flag_heroes(self) -> list[str]:
        """Active joiner flag heroes - from participant blocks when present,
        else from the joiner_flags fallback list."""
        names = [p.flag_hero for p in self.active_joiners() if p.flag_hero]
        return names if names else list(self.joiner_flags)

    def class_counts(self) -> dict[TroopType, float]:
        """Exact bottom-up counts from participant rows when available,
        falling back to share-derived estimates (collapsed blocks lack rows)."""
        if self.participants and all(p.rows for p in self.participants):
            counts: dict[TroopType, float] = {t: 0.0 for t in TroopType}
            for p in self.participants:
                for row in p.rows:
                    counts[row.troop_type] += row.total
            return counts
        return {t: g.count(self.troops) for t, g in self.composition.items()}

    def class_breakdown(self) -> dict[TroopType, dict[str, int]]:
        """Per-class outcome totals aggregated bottom-up (sim fit targets)."""
        agg: dict[TroopType, dict[str, int]] = {
            t: {"kills": 0, "losses": 0, "injured": 0, "lightly_injured": 0,
                "survivors": 0, "total": 0, "incapacitated": 0} for t in TroopType}
        for p in self.participants:
            for r in p.rows:
                a = agg[r.troop_type]
                a["kills"] += r.kills
                a["losses"] += r.losses
                a["injured"] += r.injured
                a["lightly_injured"] += r.lightly_injured
                a["survivors"] += r.survivors
                a["total"] += r.total
                a["incapacitated"] += r.incapacitated
        return agg

    def identity_errors(self) -> list[str]:
        errors = []
        if self.killed + self.lightly_injured + self.survivors != self.troops:
            errors.append(
                f"{self.player}: troops {self.troops:,} != killed {self.killed:,}"
                f" + lightly {self.lightly_injured:,} + survivors {self.survivors:,}")
        share_sum = sum(g.share for g in self.composition.values())
        if abs(share_sum - 1.0) > 0.001:
            errors.append(f"{self.player}: composition shares sum to {share_sum:.4f}")
        for p in self.participants:
            errors.extend(p.identity_errors())
        if self.participants:
            if sum(p.troops for p in self.participants) != self.troops:
                errors.append(f"{self.player}: participant troops sum != side troops")
            if all(p.rows for p in self.participants):  # skip with collapsed blocks
                for cat in ("losses", "injured", "lightly_injured", "survivors"):
                    total = sum(getattr(r, cat) for p in self.participants for r in p.rows)
                    if total != getattr(self, cat):
                        errors.append(f"{self.player}: participant {cat} sum {total:,}"
                                      f" != side {getattr(self, cat):,}")
        return errors

    def special_pool(self, stat: StatType, enemy: "ReportSide | None" = None,
                     net_enemy_debuffs: bool = False) -> float:
        """Sum this side's OWN special-layer buffs for one stat.

        net_enemy_debuffs is retained for callers that still want the old
        (approximate) subtractive netting; the exact rule is the divisor
        form used in standard_pool()."""
        total = sum(b.value for b in self.specials
                    if b.stat == stat and b.applies_to == "own")
        if net_enemy_debuffs and enemy is not None:
            total += sum(b.value for b in enemy.specials
                         if b.stat == stat and b.applies_to == "enemy")
        return total

    def enemy_penalty_pool(self, stat: StatType, enemy: "ReportSide") -> float:
        """Enemy debuff magnitude against us for one stat, as a POSITIVE
        number (enemy-applied entries are stored negative)."""
        return -sum(b.value for b in enemy.specials
                    if b.stat == stat and b.applies_to == "enemy")

    def standard_pool(self, enemy: "ReportSide") -> dict[tuple[TroopType, StatType], float]:
        """Back out the additive standard pool from the scouted display.

        CONFIRMED EXACT (enemy-penalty A/B panels, 2026-07-03):
          Scouted = (1 + std) x (1 + S_own) / (1 + P_enemy) - 1
        where S_own = own special buffs (items+widgets+pets+temp buffs,
        additive within the pool) and P_enemy = enemy debuff magnitudes
        acting as a DIVISOR (not a subtraction: RMS 0.03 vs 3.7 pct-points
        across the 6 A/B rows). Therefore
          std = (1 + Scouted) x (1 + P_enemy) / (1 + S_own) - 1.
        Hero expedition-skill buffs are NOT in the scout; the battle engine
        adds them into std later: battle multiplier =
        (1 + std + skill buffs) x (1 + S_own) / (1 + P_enemy).
        """
        pools: dict[tuple[TroopType, StatType], float] = {}
        for (troop, stat), scouted in self.scouted.items():
            s_own = self.special_pool(stat)
            p_enemy = self.enemy_penalty_pool(stat, enemy)
            pools[(troop, stat)] = (1 + scouted) * (1 + p_enemy) / (1 + s_own) - 1
        return pools


@dataclass
class BattleReport:
    report_id: str
    outcome_friendly: str            # "victory" / "defeat"
    friendly: ReportSide
    enemy: ReportSide
    notes: list[str] = field(default_factory=list)

    @property
    def attacker(self) -> ReportSide:
        return self.friendly if self.friendly.role == BattleRole.ATTACKER else self.enemy

    @property
    def defender(self) -> ReportSide:
        return self.friendly if self.friendly.role == BattleRole.DEFENDER else self.enemy

    def validate(self) -> list[str]:
        errors = self.friendly.identity_errors() + self.enemy.identity_errors()
        loser = self.friendly if self.outcome_friendly == "defeat" else self.enemy
        if loser.survivors != 0:
            errors.append(f"loser {loser.player} has {loser.survivors:,} survivors")
        for side, other in ((self.friendly, self.enemy), (self.enemy, self.friendly)):
            if side.participants:
                total_kills = sum(p.kills for p in side.participants)
                if total_kills != other.killed:
                    errors.append(f"{side.player}: participant kills {total_kills:,}"
                                  f" != enemy killed {other.killed:,}")
        return errors


def _side_from_dict(d: dict) -> ReportSide:
    side = ReportSide(
        player=d["player"], state=d["state"], role=BattleRole(d["role"]),
        is_friendly=d["is_friendly"], power_loss=d["power_loss"],
        troops=d["troops"], losses=d["losses"], injured=d["injured"],
        lightly_injured=d["lightly_injured"], survivors=d["survivors"],
        coords=d.get("coords"))
    for t, g in d.get("composition", {}).items():
        troop = TroopType(t)
        side.composition[troop] = TroopGroup(
            troop_type=troop, share=g["share"], fc_badge=g["fc_badge"],
            tier_level=g["tier_level"])
    for key, v in d.get("scouted", {}).items():
        troop_s, stat_s = key.split("|")
        side.scouted[(TroopType(troop_s), StatType(stat_s))] = v
    side.specials = [SpecialBonus(label=s["label"], value=s["value"],
                                  source=s["source"], stat=StatType(s["stat"]),
                                  applies_to=s["applies_to"])
                     for s in d.get("specials", [])]
    side.lead_heroes = [
        LeadHero(name=h["name"], level=h.get("level", 80),
                 stars=h.get("stars"),
                 rows=tuple(SkillTriggerRow(skill=r["skill"],
                                            triggered=r["triggered"],
                                            kills=r.get("kills", 0),
                                            identified=r.get("identified", True))
                            for r in h.get("rows", [])))
        for h in d.get("lead_heroes", [])]
    side.joiner_flags = list(d.get("joiner_flags", []))
    side.participants = [
        Participant(
            player=p["player"], is_captain=p.get("is_captain", False),
            troops=p["troops"], kills=p["kills"], power_loss=p["power_loss"],
            flag_hero=p.get("flag_hero"),
            rows=tuple(ParticipantRow(
                troop_type=TroopType(r["troop_type"]), kills=r["kills"],
                losses=r["losses"], injured=r["injured"],
                lightly_injured=r["lightly_injured"], survivors=r["survivors"],
                fc_badge=r.get("fc_badge"))
                for r in p["rows"]))
        for p in d.get("participants", [])]
    return side


def load_report(path: Path) -> BattleReport:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return BattleReport(
        report_id=d["report_id"], outcome_friendly=d["outcome_friendly"],
        friendly=_side_from_dict(d["friendly"]),
        enemy=_side_from_dict(d["enemy"]),
        notes=d.get("notes", []))


def load_all_reports(directory: Path = REPORTS_DIR) -> list[BattleReport]:
    return [load_report(p) for p in sorted(Path(directory).glob("*.json"))]
