"""Load all data models from the workbook and print them.  Run:  py -m wos_sim.demo"""

from .loader import GameData
from .models import StatType, TroopType

data = GameData()

print(f"Hero roster: {len(data.heroes)} heroes")
for troop in TroopType:
    names = ", ".join(h.name for h in data.heroes.by_troop_type(troop))
    print(f"  {troop} ({len(data.heroes.by_troop_type(troop))}): {names}")

print("\nSample hero lookups:")
for name in ("Elif", "Dominic", "Cara"):
    print(f"  {data.heroes.get(name)}")

print(f"\nHero profiles: {len(data.hero_profiles)}")
with_avatar = [p for p in data.hero_profiles.values() if p.avatar_path]
print(f"  with avatar extracted: {len(with_avatar)}")
missing_avatar = [p.name for p in data.hero_profiles.values() if not p.avatar_path]
if missing_avatar:
    print(f"  MISSING avatar: {missing_avatar}")
only_profile = sorted(set(data.hero_profiles) - set(data.heroes.names()))
only_stats = sorted(set(data.heroes.names()) - set(data.hero_profiles))
print(f"  in profile but not in Hero Stats: {only_profile}")
if only_stats:
    print(f"  in Hero Stats but not in profile: {only_stats}")
print("  sample:", data.hero_profiles["Elif"])

mismatched = [(n, p.troop_type, data.heroes.get(n).troop_type)
              for n, p in data.hero_profiles.items()
              if n in data.heroes and p.troop_type != data.heroes.get(n).troop_type]
if mismatched:
    print("\nWARNING - class mismatch between Hero Profile and Hero Stats tabs:")
    for name, prof_class, stats_class in mismatched:
        print(f"  {name}: Profile says {prof_class}, Hero Stats says {stats_class}"
              " (Hero Stats is authoritative)")

print(f"\nSkill book: {len(data.skills)} effect rows, {len(data.skills.heroes())} heroes")
skill_heroes, profile_heroes = set(data.skills.heroes()), set(data.hero_profiles)
print(f"  heroes in skills but not profiles: {sorted(skill_heroes - profile_heroes) or 'none'}")
print(f"  heroes in profiles but not skills: {sorted(profile_heroes - skill_heroes) or 'none'}")

print("\nDominic's skills (wiki: Mystic Mechanism / Spiky Assault / Mirror Maze):")
for source, effects in data.skills.skills_of("Dominic").items():
    print(f"  {source}: {len(effects)} effect rows")
    for e in effects:
        print(f"    {e}")

print(f"\nTroop stat tiers found: {list(data.troop_stats_tiers)}")
print(f"\n{data.troop_stats}")

print("\nSpot check FC10 T11 vs image:")
expected = {
    (TroopType.INFANTRY, StatType.ATTACK): 19,
    (TroopType.LANCER, StatType.ATTACK): 28,
    (TroopType.MARKSMAN, StatType.ATTACK): 30,
    (TroopType.INFANTRY, StatType.DEFENSE): 28,
    (TroopType.LANCER, StatType.DEFENSE): 21,
    (TroopType.MARKSMAN, StatType.DEFENSE): 21,
    (TroopType.INFANTRY, StatType.LETHALITY): 18,
    (TroopType.LANCER, StatType.LETHALITY): 26,
    (TroopType.MARKSMAN, StatType.LETHALITY): 27,
    (TroopType.INFANTRY, StatType.HEALTH): 27,
    (TroopType.LANCER, StatType.HEALTH): 20,
    (TroopType.MARKSMAN, StatType.HEALTH): 20,
}
mismatches = [(t, s, data.troop_stats.get(t, s), want)
              for (t, s), want in expected.items()
              if data.troop_stats.get(t, s) != want]
print("  all 12 values match" if not mismatches else f"  MISMATCHES: {mismatches}")

print(f"\n{data.my_stats}")
print(f"\n{data.enemy_stats}")
