"""T12 tier-3 skill effects (E-7). Effects + per-level values CONFIRMED
from in-game tooltips (GAME_RULES 6e). All are battle-start, last 5 turns
(Starfire ramps every 5 turns instead), and the summed rally/garrison
level is CLAMPED at 24 (= 8 members x L3).

A side's OWN T12 skills produce three per-turn multipliers:
  marks_dd_mult : multiply this side's MARKSMAN output up
                  (Meridian Phalanx +1%/lvl for 5 turns
                   + Starfire +0.5%/lvl per 5-turn tick, ramping).
  inf_dt_mult   : multiply damage TAKEN by this side's INFANTRY down
                  (Meridian Phalanx -1%/lvl for 5 turns).
  enemy_out_mult: multiply the ENEMY's damage inflicted on this side down
                  (Indomitable Wall -0.6%/lvl for 5 turns).
"""


def _clamp(lvl):
    return min(max(int(lvl), 0), 24)


def side_mods(levels, turn):
    """levels: {'indomitable_wall':L,'meridian_phalanx':L,'starfire':L}
    (summed across active members; clamped to 24 here). turn is 1-indexed.
    Returns (marks_dd_mult, inf_dt_mult, enemy_out_mult)."""
    if not levels:
        return 1.0, 1.0, 1.0
    iw = _clamp(levels.get("indomitable_wall", 0))
    mp = _clamp(levels.get("meridian_phalanx", 0))
    sf = _clamp(levels.get("starfire", 0))
    in_window = turn <= 5
    ticks = (turn - 1) // 5 + 1                # Starfire: +1 stack per 5 turns
    marks_dd = (1.0 + 0.01 * mp if in_window else 1.0) * (1.0 + 0.005 * sf * ticks)
    inf_dt = (1.0 - 0.01 * mp) if in_window else 1.0
    enemy_out = (1.0 - 0.006 * iw) if in_window else 1.0
    return marks_dd, inf_dt, enemy_out
