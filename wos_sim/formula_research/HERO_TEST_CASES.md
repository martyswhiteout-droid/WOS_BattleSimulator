# Hero Skill Test Cases — for the test agent

**What this tests:** each hero is a class in `wos_sim/formula_research/hero_roster.py`. Instantiate `ROSTER[name](level=L)`, build a `BattleView`, call `.resolve(view)`, and compare the returned list of effect-intents to the EXPECTED below. Expected outputs are exact.

**BattleView(turn, attack_no, enemy_alive, rng, attacker_class=None, strike_no=None):** `enemy_alive` is `{Cls: count}` (controls `Target.FRONTLINE`). `attack_no` = the GLOBAL owner-side attack counter (all classes); `strike_no` = the attacker's OWN-class strike counter (defaults to attack_no). `attacker_class` is the class making this attack — a skill with `on_class=X` fires only when `attacker_class==X`, and its cadence then counts `strike_no`. `rng.random()` is rolled by `ChanceProc`/`ScaledChance` (fires iff `< p`); **rng=FIRE** returns 0.0, **rng=NOFIRE** returns 0.99. Wrong-class skills are skipped BEFORE the roll (no RNG use).

**How to read a case:** `INPUT: level, view(turn, attack_no, rng[, enemy]) → EXPECTED: [intents]`. Order within the list is not significant. `FRONTLINE→X` means the dynamic target resolved to class X.

**Interpretation notes** (the fixes applied vs the old codification) are called out per skill so you can validate the expected output against the wiki text, not just regression-check.

---

## Flagship cases (the audit fixes)

- **Gatot** — S2 King's Bestowal emits a SHIELD (absorb=Attack x0.30), NOT a +30% Defense buff
  - INPUT: level 5, view(turn=1, attack_no=1, rng=NOFIRE)
  - EXPECTED: [StatMod(Friend, Infantry, Defense, +0.3), Shield(Infantry, absorb=Attackx0.3, dur=1), StatMod(Foe, All, Attack, -0.25)]
- **Vulcanus** — S2 damage proc fires on attack 6 (wiki 'every 5' -> measured 6); target-DT NOT yet
  - INPUT: level 5, view(turn=6, attack_no=6, rng=NOFIRE)
  - EXPECTED: [StatMod(Foe, All, Attack, -0.2), DamageMod(Friend, All, Damage Dealt, +1), StatMod(Foe, Infantry, Defense, -0.6, dur=3), StatMod(Foe, Lancer, Defense, -0.6, dur=3), StatMod(Friend, Marksman, Attack, +0.6, dur=1)]
- **Vulcanus** — S2 must NOT fire on attack 5
  - INPUT: level 5, view(turn=5, attack_no=5, rng=NOFIRE)
  - EXPECTED: [StatMod(Foe, All, Attack, -0.2)]
- **Vulcanus** — S2 target-DT (Cadence offset=1) fires on attack 7 — the attack AFTER the every-6 proc
  - INPUT: level 5, view(turn=7, attack_no=7, rng=NOFIRE)
  - EXPECTED: [StatMod(Foe, All, Attack, -0.2), DamageMod(Foe, Target, Damage Taken, +0.15, dur=1)]
- **Mia** — S1 curse targets the STRUCK UNIT (Target.TARGET), not the whole class; engine scales by struck count
  - INPUT: level 5, view(turn=1, attack_no=1, rng=FIRE, enemy={Lancer:100, Marksman:50})
  - EXPECTED: [DamageMod(Foe, Target, Damage Taken, +0.5, dur=1), DamageMod(Friend, All, Damage Dealt, +0.5), DamageMod(Friend, All, Damage Taken, -0.5)]
- **Hector** — S2 Rampant = DecayingDamage (Inf start +2.00, MM +1.00, x0.85 over 10), not a flat buff
  - INPUT: level 5, view(turn=1, attack_no=1, rng=NOFIRE)
  - EXPECTED: [DecayingDamage(Friend, Infantry, start=+2, decay=0.85, window=10), DecayingDamage(Friend, Marksman, start=+1, decay=0.85, window=10)]
- **Sergey** — S2 Weaken restored (was dropped): enemy Attack -0.20
  - INPUT: level 5, view(turn=1, attack_no=1, rng=NOFIRE)
  - EXPECTED: [DamageMod(Friend, All, Damage Taken, -0.2), StatMod(Foe, All, Attack, -0.2)]
- **Zinman** — S3 emits Lethality (not Damage Dealt)
  - INPUT: level 5, view(turn=1, attack_no=1, rng=NOFIRE)
  - EXPECTED: [StatMod(Friend, All, Defense, +0.1), StatMod(Friend, All, Health, +0.1), StatMod(Friend, All, Lethality, +0.25)]
- **Gordon** — S1 poison hits ONLY the struck target unit (Target.TARGET); not all-3, not the whole class
  - INPUT: level 5, view(turn=2, attack_no=2, rng=NOFIRE)
  - EXPECTED: [DamageMod(Friend, Lancer, Damage Dealt, +1), DamageMod(Foe, Target, Damage Dealt, -0.2, dur=1)]

## Class-gating & RNG-safety cases (exercise on_class + strike counter)

- **Gatot** — S2 shield FIRES when Infantry attacks
  - INPUT: level 5, view(attack_no=1, strike_no=1, attacker_class=Infantry, rng=NOFIRE)
  - EXPECTED: [StatMod(Friend, Infantry, Defense, +0.3), Shield(Infantry, absorb=Attackx0.3, dur=1), StatMod(Foe, All, Attack, -0.25)]
- **Gatot** — S2 shield ABSENT when Marksman attacks (on_class=INF)
  - INPUT: level 5, view(attack_no=1, strike_no=1, attacker_class=Marksman, rng=NOFIRE)
  - EXPECTED: [StatMod(Friend, Infantry, Defense, +0.3), StatMod(Foe, All, Attack, -0.25)]
- **Ahmose** — S1 (every 4 INF strikes) ABSENT at Infantry strike 2 (not global event 4)
  - INPUT: level 5, view(attack_no=2, strike_no=2, attacker_class=Infantry, rng=NOFIRE)
  - EXPECTED: [DamageMod(Friend, Infantry, Damage Dealt, +1), DamageMod(Friend, Infantry, Damage Dealt, +0.6), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
- **Ahmose** — S1 FIRES at Infantry strike 4
  - INPUT: level 5, view(attack_no=4, strike_no=4, attacker_class=Infantry, rng=NOFIRE)
  - EXPECTED: [DamageMod(Friend, Infantry, Damage Taken, -0.7, dur=2), DamageMod(Friend, Lancer, Damage Taken, -0.3, dur=2), DamageMod(Friend, Marksman, Damage Taken, -0.3, dur=2), DamageMod(Friend, Infantry, Damage Dealt, +1), DamageMod(Friend, Infantry, Damage Dealt, +0.6), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
- **Lynn** — S3 (every 3 MM strikes) ABSENT at MM strike 2
  - INPUT: level 5, view(attack_no=2, strike_no=2, attacker_class=Marksman, rng=NOFIRE)
  - EXPECTED: [DamageMod(Foe, All, Damage Dealt, -0.2)]
- **Lynn** — S3 FIRES at MM strike 3
  - INPUT: level 5, view(attack_no=3, strike_no=3, attacker_class=Marksman, rng=NOFIRE)
  - EXPECTED: [DamageMod(Foe, All, Damage Dealt, -0.2), StatMod(Friend, Marksman, Attack, +0.05)]
- **Lynn** — S3 ABSENT on an Infantry attack (wrong class)
  - INPUT: level 5, view(attack_no=3, strike_no=3, attacker_class=Infantry, rng=NOFIRE)
  - EXPECTED: [DamageMod(Foe, All, Damage Dealt, -0.2)]
- **Magnus** — RNG-safety: S2 is an Infantry-gated ChanceProc. On a MARKSMAN attack with rng=FIRE it must emit no Infantry-Defense proc AND must NOT consume a random value (the RNG stream must be byte-identical to a run in which Magnus is absent).
  - INPUT: level 5, view(attack_no=1, attacker_class=Marksman, rng=FIRE)
  - EXPECTED: [StatMod(Friend, All, Attack, +0.25), DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1)]  — and rng.random() afterwards equals the untouched stream.

---

## Per-hero cases

### Ahmose  (own class: Infantry)
- **S1 Viper Formation** — wiki: *Ahmose revives the lost art of ancient guardians. His Infantry pauses the attack once every four times, reducing damage taken by Lancers and Marksmen by 10%/15%/20%/25%/30% and Infantry by 10%/25%/40%/55%/70% for 2 turn.*
  - trigger `Cadence(every 4 attack)` [only when Infantry attacks] → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.7, dur=2)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.1, dur=2)]
  - trigger `Cadence(every 4 attack)` [only when Infantry attacks] → L5: [DamageMod(Friend, Lancer, Damage Taken, -0.3, dur=2), DamageMod(Friend, Marksman, Damage Taken, -0.3, dur=2)]
    L1: [DamageMod(Friend, Lancer, Damage Taken, -0.1, dur=2), DamageMod(Friend, Marksman, Damage Taken, -0.1, dur=2)]
  - BEHAVIOR: level 5, view(attack=4, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Taken, -0.7, dur=2), DamageMod(Friend, Lancer, Damage Taken, -0.3, dur=2), DamageMod(Friend, Marksman, Damage Taken, -0.3, dur=2), DamageMod(Friend, Infantry, Damage Dealt, +1), DamageMod(Friend, Infantry, Damage Dealt, +0.6), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=3, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Dealt, +1), DamageMod(Friend, Infantry, Damage Dealt, +0.6), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
- **S2 Prayer of Flame** — wiki: *Ahmose amplifies the combat spirit of friendly Infantry with the power of the Fire Crystal, increasing their damage dealt by 20%/40%/60%/80%/100% .*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Dealt, +1)]
    L1: [DamageMod(Friend, Infantry, Damage Dealt, +0.2)]
- **S3 Blade of Light** — wiki: *Ahmose infuses friendly Infantry's weapons with the essence of Fire Crystals, increasing his infantries' damage per attack by 12%/24%/36%/48%/60% and the target's damage taken by 5%/10%/15%/20%/25% for 1 turn.*
  - trigger `Cadence(every 1 attack)` [only when Infantry attacks] → L5: [DamageMod(Friend, Infantry, Damage Dealt, +0.6)]
    L1: [DamageMod(Friend, Infantry, Damage Dealt, +0.12)]
  - trigger `Cadence(every 1 attack)` [only when Infantry attacks] → L5: [DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=1, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Dealt, +1), DamageMod(Friend, Infantry, Damage Dealt, +0.6), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=0, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Dealt, +1)]

### Alonso  (own class: Marksman)
- **S1 Onslaught** — wiki: *Alonso attacks like the waves, granting a 40% chance of increasing all troop's Lethality by 10%/20%/30%/40%/50%*
  - trigger `ChanceProc(p=0.4)` → L5: [StatMod(Friend, All, Lethality, +0.5)]
    L1: [StatMod(Friend, All, Lethality, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Lethality, +0.5), DamageMod(Foe, All, Damage Dealt, -0.5, dur=2), DamageMod(Friend, All, Damage Dealt, +0.5)]
- **S2 Iron Strength** — wiki: *Alonso's indomitable will grants all troops' attack a 20% chance of reducing damage dealt by 10%/20%/30%/40%/50% for all enemy troops for 2 turns.*
  - trigger `ChanceProc(p=0.2)` → L5: [DamageMod(Foe, All, Damage Dealt, -0.5, dur=2)]
    L1: [DamageMod(Foe, All, Damage Dealt, -0.1, dur=2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Lethality, +0.5), DamageMod(Foe, All, Damage Dealt, -0.5, dur=2), DamageMod(Friend, All, Damage Dealt, +0.5)]
- **S3 Poison Harpoon** — wiki: *Alonso coats weapons with lethal toxins, granting all troops' attack a 50% chance of dealing + 10%/20%/30%/40%/50% more damage.*
  - trigger `ChanceProc(p=0.5)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.5)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Lethality, +0.5), DamageMod(Foe, All, Damage Dealt, -0.5, dur=2), DamageMod(Friend, All, Damage Dealt, +0.5)]

### Bahiti  (own class: Marksman)
- **S1 Sixth Sense** — wiki: *Bahiti's senses for dangers ahead, reducing damage taken by 4%/8%/12%/16%/20% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.04)]
- **S2 Fluorescence** — wiki: *Bahiti's battlefield instinct grants all troops' attack a 50% chance of increasing damage dealt by 10%/20%/30%/40%/50% .*
  - trigger `ChanceProc(p=0.5)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.5)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Taken, -0.2), DamageMod(Friend, All, Damage Dealt, +0.5)]

### Blanchette  (own class: Marksman)
- **S1 Armed to the Teeth** — wiki: *Blanchette works to ensure her forces are at least as well armed as she is, increasing all Troops' Lethality by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Lethality, +0.25)]
    L1: [StatMod(Friend, All, Lethality, +0.05)]
- **S2 Blood Hunter** — wiki: *Blanchette's Marksmen fire a crystal blade every 3 rounds, dealing 15%/30%/45%/60%/75% extra damage to the targets.*
  - trigger `Cadence(every 3 turn)` → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.75)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.15)]
  - BEHAVIOR: level 5, view(turn=3, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25), DamageMod(Friend, Marksman, Damage Dealt, +0.75)]
  - BEHAVIOR (must not fire the cadence): view(turn=2, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25)]
- **S3 Crimson Sniper** — wiki: *Thanks to Blanchette's expertise in the art of sniping and her leadership, her Marksmen deal 8%/16%/24%/32%/40% extra damage to enemy Lancers and 4%/8%/12%/16%/20% extra damage to enemy Marksmen every 2 strikes.*
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.4, vs=Lancer)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.08, vs=Lancer)]
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.2, vs=Marksman)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.04, vs=Marksman)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25), DamageMod(Friend, Marksman, Damage Dealt, +0.4, vs=Lancer), DamageMod(Friend, Marksman, Damage Dealt, +0.2, vs=Marksman)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25)]

### Bradley  (own class: Marksman)
- **S1 Veteran's Might** — wiki: *Bradley's years of combat experience enables him to destroy enemies efficiently, increasing Attack by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S2 Power Shot** — wiki: *Bradley use his expertise in suppresive artillery against the ennemy vanguard, increasing Damage Dealt to Lancer by 6%/12%/18%/24%/30% , and to infantry by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Foe, Infantry, Damage Taken, +0.25)]
    L1: [DamageMod(Foe, Infantry, Damage Taken, +0.05)]
  - trigger `Passive` → L5: [DamageMod(Foe, Lancer, Damage Taken, +0.3)]
    L1: [DamageMod(Foe, Lancer, Damage Taken, +0.06)]
- **S3 Tactical Assistance** — wiki: *Bradley will press every advantage against a beleaguered ennemy, increasing Damage Dealt by 6%/12%/18%/24%/30% for all troops for 2 turns every 4 turns.*
  - trigger `Cadence(every 4 turn)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.3, dur=2)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.06, dur=2)]
  - BEHAVIOR: level 5, view(turn=4, rng=NOFIRE) → [StatMod(Friend, All, Attack, +0.25), DamageMod(Foe, Infantry, Damage Taken, +0.25), DamageMod(Foe, Lancer, Damage Taken, +0.3), DamageMod(Friend, All, Damage Dealt, +0.3, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(turn=3, rng=NOFIRE) → [StatMod(Friend, All, Attack, +0.25), DamageMod(Foe, Infantry, Damage Taken, +0.25), DamageMod(Foe, Lancer, Damage Taken, +0.3)]

### Cara  (own class: Marksman)
- **S1 Smoky Encounter** — wiki: *Cara drops smoke grenades from the air, hindering enemy attacks and reducing their Lethality by 4%/8%/12%/16%/20%*
  - trigger `Passive` → L5: [StatMod(Foe, All, Lethality, -0.2)]
    L1: [StatMod(Foe, All, Lethality, -0.04)]
- **S2 Mech Pet** — wiki: *The Mech Pets crafted by Oestermore crafters join forces with the warriors, increasing normal attack damage by 10%/15%/20%/25%/30% for all troops*
  - interpretation: fix: was Attack stat; is normal Damage Dealt
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.3, Normal)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1, Normal)]
- **S3 Witch's Wrath** — wiki: *Thanks to Cara's flying broom, she effortlessly bypasses the enemy infantry on the frontline. Her Marksmen deal 8%/16%/24%/32%/40% extra damage to enemy Lancers and 4%/8%/12%/16%/20% extra damage to enemy Marksmen every two attacks*
  - interpretation: bypass-to-backline not yet modelled
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.4, Skills, vs=Lancer)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.08, Skills, vs=Lancer)]
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.2, Skills, vs=Marksman)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.04, Skills, vs=Marksman)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [StatMod(Foe, All, Lethality, -0.2), DamageMod(Friend, All, Damage Dealt, +0.3, Normal), DamageMod(Friend, Marksman, Damage Dealt, +0.4, Skills, vs=Lancer), DamageMod(Friend, Marksman, Damage Dealt, +0.2, Skills, vs=Marksman)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → [StatMod(Foe, All, Lethality, -0.2), DamageMod(Friend, All, Damage Dealt, +0.3, Normal)]

### Dominic  (own class: Lancer)
- **S1 Mystic Mechanism** — wiki: *Dominic equips his troops with weapons cleverly crafted from magic props, increasing damage dealt by 4%/8%/12%/16%/20% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.2, Normal)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.04, Normal)]
- **S2 Spiky Assault** — wiki: *Dominic equips his Lancers with secret deices that launch poisonous spikes, increasing their damage dealt per attack by 12%/24%/36%/48%/60% . Poisoned targets receive 5%/10%/15%/20%/25% more damage for 1 turn.*
  - trigger `Cadence(every 1 attack)` [only when Lancer attacks] → L5: [DamageMod(Friend, Lancer, Damage Dealt, +0.6, Normal)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.12, Normal)]
  - trigger `Cadence(every 1 attack)` [only when Lancer attacks] → L5: [DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=1, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.2, Normal), DamageMod(Friend, Lancer, Damage Dealt, +0.6, Normal), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1), DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15, Normal), DamageMod(Friend, Marksman, Damage Dealt, +0.15, Normal)]
  - BEHAVIOR (must not fire the cadence): view(attack=0, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.2, Normal), DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15, Normal), DamageMod(Friend, Marksman, Damage Dealt, +0.15, Normal)]
- **S3 Mirror Maze** — wiki: *Dominic disrupts enemy strategies by performing optical tricks with a mirror, reducing damage take by Infantry and Marksmen by 3%/6%/9%/12%/15% and increasing their damage dealt by 3%/6%/9%/12%/15%*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15, Normal), DamageMod(Friend, Marksman, Damage Dealt, +0.15, Normal)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.03), DamageMod(Friend, Marksman, Damage Taken, -0.03), DamageMod(Friend, Infantry, Damage Dealt, +0.03, Normal), DamageMod(Friend, Marksman, Damage Dealt, +0.03, Normal)]

### Edith  (own class: Infantry)
- **S1 Strategic Balance** — wiki: *Mr. Tin's colossal presence automatically shields friendly ranged units, reducing damage taken by 4%/8%/12%/16%/20% for Marksmen, and supresses the ennemy, increasing damage dealt by 4%/8%/12%/16%/20% for Lancers.*
  - trigger `Passive` → L5: [DamageMod(Friend, Lancer, Damage Dealt, +0.2), DamageMod(Friend, Marksman, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.04), DamageMod(Friend, Marksman, Damage Taken, -0.04)]
- **S2 Ironclad** — wiki: *Mr. Tin's metallic body functions as a fortified wall on the field, reducing damage taken by 4%/8%/12%/16%/20% for Infantry.*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.04)]
- **S3 Steel Sentinel** — wiki: *Edith's mobile defence system is reliable, increasing helth by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Health, +0.25)]
    L1: [StatMod(Friend, All, Health, +0.05)]

### Eleonora  (own class: Infantry)
- **S1 Scorching Sun** — wiki: *Eleonora inspires all troops with her royal aura and sense of honor, increasing their Health by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Health, +0.25)]
    L1: [StatMod(Friend, All, Health, +0.05)]
- **S2 Solaris Nexus** — wiki: *Eleonora deploys a balanced formation, reducing damage taken by 2%/4%/6%/8%/10% for her Infantries and increasing damage dealt by 2%/4%/6%/8%/10% for her Marksmen.*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.02), DamageMod(Friend, Marksman, Damage Dealt, +0.02)]
- **S3 Soaring Flame** — wiki: *Eleonora strikes fear into her enemies with her fierce assaults, increasing all troops' damage dealt by 5%/10%/15%/20%/25% and reducing their damage taken by 5%/10%/15%/20%/25% every 5 attacks made by Infantry for 2 turns.*
  - trigger `Cadence(every 6 attack)` [only when Infantry attacks] → L5: [DamageMod(Friend, All, Damage Dealt, +0.25, dur=2), DamageMod(Friend, All, Damage Taken, -0.25, dur=2)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05, dur=2), DamageMod(Friend, All, Damage Taken, -0.05, dur=2)]
  - BEHAVIOR: level 5, view(attack=6, rng=NOFIRE) → [StatMod(Friend, All, Health, +0.25), DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1), DamageMod(Friend, All, Damage Dealt, +0.25, dur=2), DamageMod(Friend, All, Damage Taken, -0.25, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(attack=5, rng=NOFIRE) → [StatMod(Friend, All, Health, +0.25), DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1)]

### Elif  (own class: Infantry)
- **S1 Shackling Veil** — wiki: *Elif entangles enemy weapons with her veil, reducing all enemy Troops' Attack by 5/10/15/20/25% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Attack, -0.25)]
    L1: [StatMod(Foe, All, Attack, -0.05)]
- **S2 Slash Formation** — wiki: *Elif applies an exotic formation on the tundra, increasing Troops' Attack by 3/6/9/12/15% and Troops' Defense by 2/4/6/8/10% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.15)]
    L1: [StatMod(Friend, All, Attack, +0.03)]
  - trigger `Passive` → L5: [StatMod(Friend, All, Defense, +0.1)]
    L1: [StatMod(Friend, All, Defense, +0.02)]
- **S3 Enchanting Tapestry** — wiki: *Elif weaves ribbons into a curtain when her Infantry attacks, granting them a Shield with protection equal to Attack* 6/12/18/24/30% for 1 turn.*
  - interpretation: fix: was +30% Defense; is an Attack-scaled Shield (INF attacks only)
  - trigger `Cadence(every 1 attack)` [only when Infantry attacks] → L5: [Shield(Infantry, absorb=Attackx0.3, dur=1)]
    L1: [Shield(Infantry, absorb=Attackx0.06, dur=1)]
  - BEHAVIOR: level 5, view(attack=1, rng=NOFIRE) → [StatMod(Foe, All, Attack, -0.25), StatMod(Friend, All, Attack, +0.15), StatMod(Friend, All, Defense, +0.1), Shield(Infantry, absorb=Attackx0.3, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=0, rng=NOFIRE) → [StatMod(Foe, All, Attack, -0.25), StatMod(Friend, All, Attack, +0.15), StatMod(Friend, All, Defense, +0.1)]

### Estrella  (own class: Lancer)
- **S1 Corrosive Color** — wiki: *Splatters paint made from mysterious crystals that corrode enemy armor, reducing the Defense of all enemy troops by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Defense, -0.25)]
    L1: [StatMod(Foe, All, Defense, -0.05)]
- **S2 Dawn Canvas** — wiki: *Encourages troops with an inspiring painting, increasing the Attack of all allied troops by 3%/6%/9%/12%/15% and their Defense by 2%/4%/6%/8%/10% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.15)]
    L1: [StatMod(Friend, All, Attack, +0.03)]
  - trigger `Passive` → L5: [StatMod(Friend, All, Defense, +0.1)]
    L1: [StatMod(Friend, All, Defense, +0.02)]
- **S3 Splendid Scene** — wiki: *Boosts morale with a vibrant painting, reducing the damage taken by Infantry by 5%/10%/15%/20%/25% and increasing the damage dealt by Lancers by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.25), DamageMod(Friend, Lancer, Damage Dealt, +0.25)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.05), DamageMod(Friend, Lancer, Damage Dealt, +0.05)]

### Flint  (own class: Infantry)
- **S1 Pyromaniac** — wiki: *Every flame, no matter how small, can ignite a roaring fire. Flint increases his infantry's Damage Dealt by 20%/40%/60%/80%/100%*
  - interpretation: fix: passive per wiki, not Turn-based
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Dealt, +1)]
    L1: [DamageMod(Friend, Infantry, Damage Dealt, +0.2)]
- **S2 Burning Resolve** — wiki: *Flint's fire not only dispels the cold but also ignites the passion for battle, increasing Attack by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S3 Immolation** — wiki: *Flint's flame of anger devours everything. Increasing all troops' Lethality by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Lethality, +0.25)]
    L1: [StatMod(Friend, All, Lethality, +0.05)]

### Flora  (own class: Lancer)
- **S1 Enmiring Vines** — wiki: *Flora litters the ground with sharp vines to hobble enemy soldiers, granting all troops a 50% chance of increasing enemies' Damage Taken by 10%/20%/30%/40%/50% .*
  - trigger `ChanceProc(p=0.5)` → L5: [DamageMod(Foe, All, Damage Taken, +0.5)]
    L1: [DamageMod(Foe, All, Damage Taken, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Foe, All, Damage Taken, +0.5), DamageMod(Friend, Infantry, Damage Taken, -0.25, Normal), DamageMod(Friend, Lancer, Damage Dealt, +0.25, Normal)]
- **S2 Plantage** — wiki: *Flora's defensive foliage reduces Infantry Damage Taken by 5%/10%/15%/20%/25% while better Adoria Rose coordination with Lancers gives joint attacks dealing 5%/10%/15%/20%/25% extra damage.*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.25, Normal), DamageMod(Friend, Lancer, Damage Dealt, +0.25, Normal)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.05, Normal), DamageMod(Friend, Lancer, Damage Dealt, +0.05, Normal)]
- **S3 Confusion Pollen** — wiki: *Flora's hallucinatory pollen increases enemy Infantry's Damage Taken by 6%/12%/18%/24%/30% , and decreases enemy Marksmen's Damage Dealt by 6%/12%/18%/24%/30% for 2 turns every 4 turns.*
  - trigger `Cadence(every 4 turn)` → L5: [DamageMod(Foe, Infantry, Damage Taken, +0.3, Normal, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.3, Normal, dur=2)]
    L1: [DamageMod(Foe, Infantry, Damage Taken, +0.06, Normal, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.06, Normal, dur=2)]
  - BEHAVIOR: level 5, view(turn=4, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Taken, -0.25, Normal), DamageMod(Friend, Lancer, Damage Dealt, +0.25, Normal), DamageMod(Foe, Infantry, Damage Taken, +0.3, Normal, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.3, Normal, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(turn=3, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Taken, -0.25, Normal), DamageMod(Friend, Lancer, Damage Dealt, +0.25, Normal)]

### Fred  (own class: Lancer)
- **S1 Hydraulic Suppression** — wiki: *Fred's water volleys destroy opponent momentum, reducing all enemy troops’ lethality by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Lethality, -0.2)]
    L1: [StatMod(Foe, All, Lethality, -0.04)]
- **S2 Acidification** — wiki: *Fred coats enemy Infantry shields with a special acidic blend, amplifying their damage taken by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [DamageMod(Foe, Infantry, Damage Taken, +0.2)]
    L1: [DamageMod(Foe, Infantry, Damage Taken, +0.04)]
- **S3 Floodbringer** — wiki: *A master of pressure both hydraulic and tactical, Fred's Lancers deal 40%/80%/120%/160%/200% additional damage every 4 strikes and reduce enemy troop damage dealt by 4%/8%/12%/16%/20% on the next turn.*
  - trigger `Cadence(every 4 attack)` [only when Lancer attacks] → L5: [DamageMod(Friend, Lancer, Damage Dealt, +2)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.4)]
  - trigger `Cadence(every 4 attack)` [only when Lancer attacks] → L5: [DamageMod(Foe, All, Damage Dealt, -0.2, dur=1)]
    L1: [DamageMod(Foe, All, Damage Dealt, -0.04, dur=1)]
  - BEHAVIOR: level 5, view(attack=4, rng=NOFIRE) → [StatMod(Foe, All, Lethality, -0.2), DamageMod(Foe, Infantry, Damage Taken, +0.2), DamageMod(Friend, Lancer, Damage Dealt, +2), DamageMod(Foe, All, Damage Dealt, -0.2, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=3, rng=NOFIRE) → [StatMod(Foe, All, Lethality, -0.2), DamageMod(Foe, Infantry, Damage Taken, +0.2)]

### Freya  (own class: Lancer)
- **S1 Fog of War** — wiki: *Freya lobs a smoke grenade to darken enemies' vision, reducing all enemy Troops' Attack by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Attack, -0.2)]
    L1: [StatMod(Foe, All, Attack, -0.04)]
- **S2 Blood Moon Scythe** — wiki: *Freya reaps the fear of his enemies with her crescent-shaped weapon. After launching a normal attack, she has a 50% chance of performing Reap, dealing 20%/40%/60%/80%/100% damage.*
  - interpretation: fix: Reap is an extra strike, not a DD buff
  - trigger `ChanceProc(p=0.5)` [only when Lancer attacks] → L5: [ExtraAttack(Lancer, dmg_x=1)]
    L1: [ExtraAttack(Lancer, dmg_x=0.2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Foe, All, Attack, -0.2), ExtraAttack(Lancer, dmg_x=1), DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Dealt, +0.15)]
- **S3 Night's Vengeance** — wiki: *Freya disrupts enemy attacks by launching a surprise raid and breaches enemy defense, decreasing damage taken by 3%/6%/9%/12%/15% and increasing damage dealt by 3%/6%/9%/12%/15% for her Infantries and Marksmen.*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Dealt, +0.15)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.03), DamageMod(Friend, Marksman, Damage Taken, -0.03), DamageMod(Friend, Infantry, Damage Dealt, +0.03), DamageMod(Friend, Marksman, Damage Dealt, +0.03)]

### Gatot  (own class: Infantry)
- **S1 Golden Guard** — wiki: *Gatot commands his troops with imperial guard tactics, increasing his Infantry’s Defense by 6%/12%/18%/24%/30% .*
  - trigger `Passive` → L5: [StatMod(Friend, Infantry, Defense, +0.3)]
    L1: [StatMod(Friend, Infantry, Defense, +0.06)]
- **S2 King's Bestowal** — wiki: *The great kings blesses Gatot’s Infantry, granting Infantry a Shield with protection equal to Attack* 6%/12%/18%/24%/30% each time they attack, for 1 turn.*
  - interpretation: Infantry-only shield, each time INFANTRY attacks (was +30% Def)
  - trigger `Cadence(every 1 attack)` [only when Infantry attacks] → L5: [Shield(Infantry, absorb=Attackx0.3, dur=1)]
    L1: [Shield(Infantry, absorb=Attackx0.06, dur=1)]
  - BEHAVIOR: level 5, view(attack=1, rng=NOFIRE) → [StatMod(Friend, Infantry, Defense, +0.3), Shield(Infantry, absorb=Attackx0.3, dur=1), StatMod(Foe, All, Attack, -0.25)]
  - BEHAVIOR (must not fire the cadence): view(attack=0, rng=NOFIRE) → [StatMod(Friend, Infantry, Defense, +0.3), StatMod(Foe, All, Attack, -0.25)]
- **S3 Royal Legion** — wiki: *Gatot’s formidable legion instills fear in enemies, reducing their Attack by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Attack, -0.25)]
    L1: [StatMod(Foe, All, Attack, -0.05)]

### Gisela  (own class: Infantry)
- **S1 Alloyed Defense** — wiki: *Gisela's advanced tech increases Infantry Defense by 6%/12%/18%/24%/30% .*
  - trigger `Passive` → L5: [StatMod(Friend, Infantry, Defense, +0.3)]
    L1: [StatMod(Friend, Infantry, Defense, +0.06)]
- **S2 Scavengeworks** — wiki: *Gisela is a master of defensive scavenging. Infantry under Gisela's command have a 40% chance of increasing all Troops' Defense by 10%/20%/30%/40%/50% for 1 turn.*
  - trigger `ChanceProc(p=0.4)` → L5: [StatMod(Friend, All, Defense, +0.5, dur=1)]
    L1: [StatMod(Friend, All, Defense, +0.1, dur=1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, Infantry, Defense, +0.3), StatMod(Friend, All, Defense, +0.5, dur=1), DamageMod(Friend, All, Damage Taken, -0.5)]
- **S3 Trial Shield** — wiki: *Gisela provides an experimental version of her shield to all troops, granting a 40% chance of reducing Damage Taken by 10%/20%/30%/40%/50% for all troops.*
  - trigger `ChanceProc(p=0.4)` → L5: [DamageMod(Friend, All, Damage Taken, -0.5)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, Infantry, Defense, +0.3), StatMod(Friend, All, Defense, +0.5, dur=1), DamageMod(Friend, All, Damage Taken, -0.5)]

### Gordon  (own class: Lancer)
- **S1 Venom Infusion** — wiki: *Gordon dips Lancer's weapons in venom. Every 2 attacks, Lancers deals 20%/40%/60%/80%/100% extra damage and apply poison to the target for 1 turn. Posioned ennemies deals 4%/8%/12%/16%/20% less damage.*
  - interpretation: Martin 2026-07-25: poison hits ONLY the struck target unit (1 Lancer -> 1 Infantry, not all of the class), not all-3
  - trigger `Cadence(every 2 attack)` [only when Lancer attacks] → L5: [DamageMod(Friend, Lancer, Damage Dealt, +1)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.2)]
  - trigger `Cadence(every 2 attack)` [only when Lancer attacks] → L5: [DamageMod(Foe, Target, Damage Dealt, -0.2, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Dealt, -0.04, dur=1)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [DamageMod(Friend, Lancer, Damage Dealt, +1), DamageMod(Foe, Target, Damage Dealt, -0.2, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → []  (nothing fires)
- **S2 Chemical Terror** — wiki: *Gordon's envenomed weapons terorizes the field, increasing Lancer's Damage Dealt by 30%/60%/90%/120%/150% and reducing Damage Dealt by 6%/12%/18%/24%/30% for all ennemy troops for 1 turn, every 3 turns.*
  - trigger `Cadence(every 3 turn)` → L5: [DamageMod(Friend, Lancer, Damage Dealt, +1.5, dur=1)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.3, dur=1)]
  - trigger `Cadence(every 3 turn)` → L5: [DamageMod(Foe, All, Damage Dealt, -0.3, dur=1)]
    L1: [DamageMod(Foe, All, Damage Dealt, -0.06, dur=1)]
  - BEHAVIOR: level 5, view(turn=3, rng=NOFIRE) → [DamageMod(Friend, Lancer, Damage Dealt, +1.5, dur=1), DamageMod(Foe, All, Damage Dealt, -0.3, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(turn=2, rng=NOFIRE) → []  (nothing fires)
- **S3 Toxic Release** — wiki: *Gordon generates a defensive bio-toxic fog, confusing enemy frontline Infantry, increasing their Damage Taken by 6%/12%/18%/24%/30% , while blocking enemy Marksmen's line of sigth to reduce their Damage Dealt by 6%/12%/15%/24%/30% for 2 turns every 4 turns.*
  - trigger `Cadence(every 4 turn)` → L5: [DamageMod(Foe, Infantry, Damage Taken, +0.3, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.3, dur=2)]
    L1: [DamageMod(Foe, Infantry, Damage Taken, +0.06, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.06, dur=2)]
  - BEHAVIOR: level 5, view(turn=4, rng=NOFIRE) → [DamageMod(Foe, Infantry, Damage Taken, +0.3, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.3, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(turn=3, rng=NOFIRE) → [DamageMod(Friend, Lancer, Damage Dealt, +1.5, dur=1), DamageMod(Foe, All, Damage Dealt, -0.3, dur=1)]

### Greg  (own class: Marksman)
- **S1 Sword of Justice** — wiki: *Greg transforms our troops into a relentless sword of justice, granting a 20% chance of increasing damage dealt by 8%/16%/24%/32%/40% for all troops for 3 turns.*
  - trigger `ChanceProc(p=0.2)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.4, dur=3)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.08, dur=3)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Dealt, +0.4, dur=3), DamageMod(Foe, All, Damage Dealt, -0.5, dur=2), StatMod(Friend, All, Health, +0.25)]
- **S2 Deterrence of Law** — wiki: *Greg uses the authority of the law to intimidate enemies, granting all troops' attack a 20% chance of reducing damage dealt by 10%/20%/30%/40%/50% for all enemy troops for 2 turns.*
  - trigger `ChanceProc(p=0.2)` → L5: [DamageMod(Foe, All, Damage Dealt, -0.5, dur=2)]
    L1: [DamageMod(Foe, All, Damage Dealt, -0.1, dur=2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Dealt, +0.4, dur=3), DamageMod(Foe, All, Damage Dealt, -0.5, dur=2), StatMod(Friend, All, Health, +0.25)]
- **S3 Law and Order** — wiki: *Greg's faith in law and order uplifts everyone, increasing Health by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Health, +0.25)]
    L1: [StatMod(Friend, All, Health, +0.05)]

### Gregory  (own class: Infantry)
- **S1 Legion of the Sun** — wiki: *Gregory nurtures latent talents his troops did not realize they had, increasing Attack by 3%/6%/9%/12%/15% and Defense by 2%/4%/6%/8%/10% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.15)]
    L1: [StatMod(Friend, All, Attack, +0.03)]
  - trigger `Passive` → L5: [StatMod(Friend, All, Defense, +0.1)]
    L1: [StatMod(Friend, All, Defense, +0.02)]
- **S2 Charged Assault** — wiki: *Gregory inspires everyone with his valor and enthusiasm, granting all troop's normal attacks a 5%/10%/15%/20%/25% chance of dealing critical damage.*
  - trigger `Passive` → L5: [Crit(All, rate=0.25)]
    L1: [Crit(All, rate=0.05)]
- **S3 Unbroken** — wiki: *Gregory forms unbroken defensive lines, reducing Infantry’s Damage Taken by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.04)]

### Gwen  (own class: Marksman)
- **S1 Eagle Vision** — wiki: *Gwen provides unfettered vision of ennemy weakpoint during fligths, increasing target's Damage Taken by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [DamageMod(Foe, Target, Damage Taken, +0.25)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05)]
- **S2 Air Dominance** — wiki: *Gwen dominates the skies, dealing 20%/40%/60%/80%/100% extra damage once every five attacks and grants 5%/7.5%/10%/12.5%/15% extra damage to the next attack from any source.*
  - trigger `Cadence(every 6 attack)` → L5: [DamageMod(Friend, All, Damage Dealt, +1)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.2)]
  - trigger `Cadence(every 6 attack)` → L5: [DamageMod(Foe, Target, Damage Taken, +0.15, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=6, rng=NOFIRE) → [DamageMod(Foe, Target, Damage Taken, +0.25), DamageMod(Friend, All, Damage Dealt, +1), DamageMod(Foe, Target, Damage Taken, +0.15, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=5, rng=NOFIRE) → [DamageMod(Foe, Target, Damage Taken, +0.25)]
- **S3 Blastmaster** — wiki: *Gwen equips her troops with grenades, dealing 10%/20%/30%/40%/50% extra damage to all ennemies once every 4 attacks.*
  - interpretation: fix: all troops, not Marksman-only
  - trigger `Cadence(every 4 attack)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.5)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1)]
  - BEHAVIOR: level 5, view(attack=4, rng=NOFIRE) → [DamageMod(Foe, Target, Damage Taken, +0.25), DamageMod(Friend, All, Damage Dealt, +0.5)]
  - BEHAVIOR (must not fire the cadence): view(attack=3, rng=NOFIRE) → [DamageMod(Foe, Target, Damage Taken, +0.25)]

### Hank  (own class: Infantry)
- **S1 Roaring Rage** — wiki: *Hank's rage and the roaring of his chainsaw ignite the fighting spirit of all troops, boosting all troops' Lethality by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Lethality, +0.25)]
    L1: [StatMod(Friend, All, Lethality, +0.05)]
- **S2 Flying Sparks** — wiki: *The sparks of the chainsaw ignite allied morale. For every 5 attacks Hank's Infantry perform, the damage dealt by all allied troops is increased by 5%/10%/15%/20%/25% , while their damage taken is reduced by 5%/10%/15%/20%/25% .*
  - trigger `Cadence(every 6 attack)` [only when Infantry attacks] → L5: [DamageMod(Friend, All, Damage Dealt, +0.25), DamageMod(Friend, All, Damage Taken, -0.25)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05), DamageMod(Friend, All, Damage Taken, -0.05)]
  - BEHAVIOR: level 5, view(attack=6, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25), DamageMod(Friend, All, Damage Dealt, +0.25), DamageMod(Friend, All, Damage Taken, -0.25)]
  - BEHAVIOR (must not fire the cadence): view(attack=5, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25)]
- **S3 Raging Force** — wiki: *Hank's wild attacks weaken enemy morale. Every 4 turns, the damage taken by enemy Infantry is increased by 6%/12%/18%/24%/30% , while the damage dealt by enemy Marksmen is reduced by 6%/12%/18%/24%/30% . This effect lasts for 2 turns.*
  - trigger `Cadence(every 4 turn)` → L5: [DamageMod(Foe, Infantry, Damage Taken, +0.3, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.3, dur=2)]
    L1: [DamageMod(Foe, Infantry, Damage Taken, +0.06, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.06, dur=2)]
  - BEHAVIOR: level 5, view(turn=4, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25), DamageMod(Foe, Infantry, Damage Taken, +0.3, dur=2), DamageMod(Foe, Marksman, Damage Dealt, -0.3, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(turn=3, rng=NOFIRE) → [StatMod(Friend, All, Lethality, +0.25)]

### Hector  (own class: Infantry)
- **S1 Survival Instincts** — wiki: *A seasoned warrior with an uncanny knack for reading the battlefield, Hector's presence has a 40% chance of reducing damage taken by 10%/20%/30%/40%/50% for all troops.*
  - trigger `ChanceProc(p=0.4)` → L5: [DamageMod(Friend, All, Damage Taken, -0.5)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Taken, -0.5), DecayingDamage(Friend, Infantry, start=+2, decay=0.85, window=10), DecayingDamage(Friend, Marksman, start=+1, decay=0.85, window=10), DamageMod(Friend, All, Damage Dealt, +1)]
- **S2 Rampant** — wiki: *Hector excels at raiding on fortified positions with well-coordinated Marksmen, increasing Infantry's Damage Dealt by 100%/125%/150%/175%/200% , and Marksman's Damage dealt by 20%/40%/60%/80%/100% , it is effective for 10 attacks, with each attack's damage boost being 85% of the previous one.*
  - interpretation: Infantry +100..200% over a 10-attack 0.85-decay window
  - interpretation: Marksman +20..100% (own ladder, not half the Infantry one)
  - trigger `Passive` → L5: [DecayingDamage(Friend, Infantry, start=+2, decay=0.85, window=10)]
    L1: [DecayingDamage(Friend, Infantry, start=+1, decay=0.85, window=10)]
  - trigger `Passive` → L5: [DecayingDamage(Friend, Marksman, start=+1, decay=0.85, window=10)]
    L1: [DecayingDamage(Friend, Marksman, start=+0.2, decay=0.85, window=10)]
- **S3 Blitz** — wiki: *Hector has mastered the offensive strategy, granting a 25% chance of dealing 120%/140%/160%/180%/200% damage on attack.*
  - interpretation: 'dealing 200% damage' = 2x = +100% -> max value 1.00, not 2.00
  - trigger `ChanceProc(p=0.25)` → L5: [DamageMod(Friend, All, Damage Dealt, +1)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Taken, -0.5), DecayingDamage(Friend, Infantry, start=+2, decay=0.85, window=10), DecayingDamage(Friend, Marksman, start=+1, decay=0.85, window=10), DamageMod(Friend, All, Damage Dealt, +1)]

### Hendrik  (own class: Marksman)
- **S1 Worm's Ravage** — wiki: *Captain Hendrik commands a gigantic naval shipworm gnaw at the enemies’ armor reducing all enemy troops’ Defense by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Defense, -0.25)]
    L1: [StatMod(Foe, All, Defense, -0.05)]
- **S2 Armor of Barnacles** — wiki: *Hendrik covers all friendly Troops with a layer of hard-shelled barnacles every 4 turns, increasing their Defense by 6%/12%/18%/24%/30% for 2 turns.*
  - trigger `Cadence(every 4 turn)` → L5: [StatMod(Friend, All, Defense, +0.3, dur=2)]
    L1: [StatMod(Friend, All, Defense, +0.06, dur=2)]
  - BEHAVIOR: level 5, view(turn=4, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25), StatMod(Friend, All, Defense, +0.3, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(turn=3, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25), ExtraAttack(Marksman, dmg_x=0.4)]
- **S3 Dragon's Heir** — wiki: *Every 3 turns, the ancient abyssal spirit’s descendants will work together with Hendrik’s Marksmen to launch an attack, dealing 8%/16%/24%/32%/40% damage to all enemies.*
  - trigger `Cadence(every 3 turn)` → L5: [ExtraAttack(Marksman, dmg_x=0.4)]
    L1: [ExtraAttack(Marksman, dmg_x=0.08)]
  - BEHAVIOR: level 5, view(turn=3, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25), ExtraAttack(Marksman, dmg_x=0.4)]
  - BEHAVIOR (must not fire the cadence): view(turn=2, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25)]

### Hervor  (own class: Infantry)
- **S1 Call For Blood** — wiki: *Hervor's heartfelt war cry ignites fearlessness in her soldiers, increasing all troops' Lethality by 5%/10%/15%/20%/25%*
  - trigger `Passive` → L5: [StatMod(Friend, All, Lethality, +0.25)]
    L1: [StatMod(Friend, All, Lethality, +0.05)]
- **S2 Undying** — wiki: *The enemy menace pales beside Hervor's icy homeland, her Infantry's Damage Taken from Normal Attacks is reduced by 5%/10%/15%/20%/25% and 6%/12%/18%/24%/30% from enemy skills.*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.25, Normal)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.05, Normal)]
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.3, Skills)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.06, Skills)]
- **S3 Battlethirsty** — wiki: *Hervor and her Infantry are singularly devoted to the idea of battle, reducing her Infantry's damage taken by 3%/6%/9%/12%/15% and increasing their damage dealt by 2%/4%/6%/8%/10%*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.15)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.03)]
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Dealt, +0.1, Normal)]
    L1: [DamageMod(Friend, Infantry, Damage Dealt, +0.02, Normal)]

### Jasser  (own class: Marksman)
- **S1 Tactical Genius** — wiki: *Jasser's combination of courage and wisdom enriches the army, increasing damage dealt by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.25)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05)]
- **S2 Enlightened Warfare** — wiki: *Jasser's profound knowledge increases the city's Research Speed by 3%/6%/9%/12%/15% .*
  - interpretation: research-speed skill; no combat effect
  - trigger `Passive`: NON-COMBAT — resolve emits nothing

### Jeronimo  (own class: Infantry)
- **S1 Battle Manifesto** — wiki: *Jeronimo delivers a rousing rally speech ahead of the battle, increasing damage dealt by + 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.25)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05)]
- **S2 Swordmentor** — wiki: *Jeronimo imparts the secrets of swordsmanship, increasing attack by + 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S3 Expert Swordsmanship** — wiki: *Jeronimo's sword arts empower soldiers to seize battle opportunities, increasing Damage Dealt by 6%/12%/18%/24%/30% for all troops for 2 turns every 4 turns.*
  - trigger `Cadence(every 4 turn)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.3, dur=2)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.06, dur=2)]
  - BEHAVIOR: level 5, view(turn=4, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.25), StatMod(Friend, All, Attack, +0.25), DamageMod(Friend, All, Damage Dealt, +0.3, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(turn=3, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.25), StatMod(Friend, All, Attack, +0.25)]

### Jessie  (own class: Lancer)
- **S1 Stand of Arms** — wiki: *Jessie implement advanced weaponry for our troops, increasing damage dealt by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.25)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05)]
- **S2 Bulwarks** — wiki: *With a keen engineering eye, Jessie enhances troops armor, reducing damage taken by 4%/8%/12%/16%/20% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.04)]

### Karol  (own class: Lancer)
- **S1 In the Wings** — wiki: *A great offence is a great defense in the case of Karol's cavalry diversions, reducing all troops' damage taken by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.04)]
- **S2 Shieldbreaker** — wiki: *Karol knows exactly where enemy infantry are weakest against forces like his own, increasing all troops' Damage Dealt to Lancers by 6%/12%/18%/24%/30% and 5%/10%/15%/20%/25% to Infantry.*
  - trigger `Passive` → L5: [DamageMod(Foe, Lancer, Damage Taken, +0.3)]
    L1: [DamageMod(Foe, Lancer, Damage Taken, +0.06)]
  - trigger `Passive` → L5: [DamageMod(Foe, Infantry, Damage Taken, +0.25)]
    L1: [DamageMod(Foe, Infantry, Damage Taken, +0.05)]
- **S3 Standard of Ages** — wiki: *Karol has turned the lessons of past brigades into a roadmap for victory, increasing all Troops' Attack by 3%/6%/9%/12%/15% and Defense by 2%/4%/6%/8%/10% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.15)]
    L1: [StatMod(Friend, All, Attack, +0.03)]
  - trigger `Passive` → L5: [StatMod(Friend, All, Defense, +0.1)]
    L1: [StatMod(Friend, All, Defense, +0.02)]

### Ligeia  (own class: Marksman)
- **S1 Nerf Poison** — wiki: *Ligeia unleashes a swarm of biting Mech-spiders against well-armored foes, reducing all enemy Defense by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Defense, -0.25)]
    L1: [StatMod(Foe, All, Defense, -0.05)]
- **S2 Corrosion** — wiki: *Ligeia adds Mech-spiders to Marksmen's fire, dealing 20%/40%/60%/80%/100% extra damage every 2 attacks; spider acid dissolves enemy armor, amplifying target damage received by 5%/10%/15%/20%/25% for 1 turn.*
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +1, Skills)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.2, Skills)]
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25), DamageMod(Friend, Marksman, Damage Dealt, +1, Skills), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1), DamageMod(Friend, Marksman, Damage Dealt, +1, Normal), DamageMod(Foe, Target, Damage Dealt, -0.2, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25)]
- **S3 Toxic Tip** — wiki: *Ligeia dips Marksmen arrowheads in spider toxin, increasing Marksmen's damage by 20%/40%/60%/80%/100% against the target every 2 attacks while reducing the target's damage dealt by 4%/8%/12%/16%/20% for 1 turn.*
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +1, Normal)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.2, Normal)]
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Foe, Target, Damage Dealt, -0.2, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Dealt, -0.04, dur=1)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25), DamageMod(Friend, Marksman, Damage Dealt, +1, Skills), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1), DamageMod(Friend, Marksman, Damage Dealt, +1, Normal), DamageMod(Foe, Target, Damage Dealt, -0.2, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → [StatMod(Foe, All, Defense, -0.25)]

### Ling Xue  (own class: Lancer)
- **S1 Fearsome Aura** — wiki: *Ling Xue's withering assault has disturbed enemies' formation, reducing all enemy Troops' Attack by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Attack, -0.2)]
    L1: [StatMod(Foe, All, Attack, -0.04)]
- **S2 Total Control** — wiki: *Ling Xue's hands-on, disciplined instruction increases Training Speed by 4%/8%/12%/16%/20% .*
  - interpretation: training-speed skill; no combat effect
  - trigger `Passive`: NON-COMBAT — resolve emits nothing

### Lloyd  (own class: Lancer)
- **S1 Bird Invasion** — wiki: *Lloyd summons a large number of mechanical birds to disrupt enemies, reducing their Lethality by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Lethality, -0.2)]
    L1: [StatMod(Foe, All, Lethality, -0.04)]
- **S2 Iceflare Bomb** — wiki: *Lloyd prepares special bomb for all Lancers, which detonates every 3 turns, increases their attack by 30%/60%/90%/120%/150% and releases frosty mist that reduces enemy Lethality by 6%/12%/18%/24%/30% for 1 turn.*
  - trigger `Cadence(every 3 turn)` → L5: [StatMod(Friend, Lancer, Attack, +1.5, dur=1)]
    L1: [StatMod(Friend, Lancer, Attack, +0.3, dur=1)]
  - trigger `Cadence(every 3 turn)` → L5: [StatMod(Foe, All, Lethality, -0.3, dur=1)]
    L1: [StatMod(Foe, All, Lethality, -0.06, dur=1)]
  - BEHAVIOR: level 5, view(turn=3, rng=NOFIRE) → [StatMod(Foe, All, Lethality, -0.2), StatMod(Friend, Lancer, Attack, +1.5, dur=1), StatMod(Foe, All, Lethality, -0.3, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(turn=2, rng=NOFIRE) → [StatMod(Foe, All, Lethality, -0.2)]
- **S3 Ingenious Mastery** — wiki: *Lloyd works to equips his forces with unstable by interesting creations, granting a 40% chance to increase all Troops' Lethality by 10%/20%/30%/40%/50% .*
  - interpretation: fix: real proc% (sibling EV-averaging removed)
  - trigger `ChanceProc(p=0.4)` → L5: [StatMod(Friend, All, Lethality, +0.5)]
    L1: [StatMod(Friend, All, Lethality, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Foe, All, Lethality, -0.2), StatMod(Friend, All, Lethality, +0.5)]

### Logan  (own class: Infantry)
- **S1 Lion's Might** — wiki: *Logan overwhelms his enemies with a fierce presence, reducing all enemy's Troops' Attack by 4%/8%/12%/16%/20% .*
  - interpretation: fix: passive per wiki, not a proc
  - trigger `Passive` → L5: [StatMod(Foe, All, Attack, -0.2)]
    L1: [StatMod(Foe, All, Attack, -0.04)]
- **S2 Lion Intimidation** — wiki: *Logan intimidates his opponent with the ferocity of a lion, reducing damage taken by 4%/8%/12%/16%/20% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.04)]
- **S3 Leader Inspiration** — wiki: *Logan inspires everyone with his inherent leadership qualities, increasing the Health by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Health, +0.25)]
    L1: [StatMod(Friend, All, Health, +0.05)]

### Lumak Bokan  (own class: Lancer)
- **S1 Tactical Deception** — wiki: *With Lumak Bokan's expert guerrilla tactics, all enemy troops' damage dealt is reduced by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [DamageMod(Foe, All, Damage Dealt, -0.2)]
    L1: [DamageMod(Foe, All, Damage Dealt, -0.04)]
- **S2 Emerald Warrior** — wiki: *Lumak Bokan passes his people's traditional techniques to the soldiers, increasing Hunting March Speed by 20%/40%/60%/80%/100% .*
  - interpretation: hunting-march-speed skill; no combat effect
  - trigger `Passive`: NON-COMBAT — resolve emits nothing

### Lynn  (own class: Marksman)
- **S1 Song of Lion** — wiki: *Lynn uplifts our troops with an enthusiastic rhythm, granting a 40% chance of increasing damage dealt by 10%/20%/30%/40%/50% for all troops.*
  - interpretation: fix: 40% chance -> Chance-based, not Turn-based
  - trigger `ChanceProc(p=0.4)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.5)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Dealt, +0.5), DamageMod(Foe, All, Damage Dealt, -0.2)]
- **S2 Melancholic Ballad** — wiki: *Lynn demoralizes the enemies with a somber tune, reducing damage dealt by 4%/8%/12%/16%/20% for all enemy troops.*
  - trigger `Passive` → L5: [DamageMod(Foe, All, Damage Dealt, -0.2)]
    L1: [DamageMod(Foe, All, Damage Dealt, -0.04)]
- **S3 Oonai Cadenza** — wiki: *Lynn harnesses the power of music to elevate troops morale, increasing her Marksmen's attack by 1%/2%/3%/4%/5% for every 3 attacks. Stackable and lasts until the end of the battle.*
  - interpretation: stackable-until-end-of-battle: engine must accumulate, not refresh
  - trigger `Cadence(every 3 attack)` [only when Marksman attacks] → L5: [StatMod(Friend, Marksman, Attack, +0.05)]
    L1: [StatMod(Friend, Marksman, Attack, +0.01)]
  - BEHAVIOR: level 5, view(attack=3, rng=NOFIRE) → [DamageMod(Foe, All, Damage Dealt, -0.2), StatMod(Friend, Marksman, Attack, +0.05)]
  - BEHAVIOR (must not fire the cadence): view(attack=2, rng=NOFIRE) → [DamageMod(Foe, All, Damage Dealt, -0.2)]

### Magnus  (own class: Infantry)
- **S1 Rapacious** — wiki: *Magnus rouses his troops with brutal intensity, boosting friendly Troop Attack by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S2 Iron Phalanx** — wiki: *A master of tight formations, Infantry under Magnus' command enjoy a 40% chance of gaining 10%/20%/30%/40%/50% Defense when attacking for 1 turn.*
  - interpretation: Infantry gain Defense when INFANTRY attacks
  - trigger `ChanceProc(p=0.4)` [only when Infantry attacks] → L5: [StatMod(Friend, Infantry, Defense, +0.5, dur=1)]
    L1: [StatMod(Friend, Infantry, Defense, +0.1, dur=1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Attack, +0.25), StatMod(Friend, Infantry, Defense, +0.5, dur=1), DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1)]
- **S3 Iceman** — wiki: *Magnus' intrepid adventuring skills provide a 2%/4%/6%/8%/10% reduction in damage versus friendly Infantry while boosting friendly Marksmen damage by 2%/4%/6%/8%/10% .*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.02), DamageMod(Friend, Marksman, Damage Dealt, +0.02)]

### Mia  (own class: Lancer)
- **S1 Bad Luck Streak** — wiki: *Grants all troops' attack a 50% chance of cursing the target, increasing their damage taken by 10%/20%/30%/40%/50% .*
  - trigger `ChanceProc(p=0.5)` → L5: [DamageMod(Foe, Target, Damage Taken, +0.5, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.1, dur=1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Foe, Target, Damage Taken, +0.5, dur=1), DamageMod(Friend, All, Damage Dealt, +0.5), DamageMod(Friend, All, Damage Taken, -0.5)]
- **S2 Lucky Charm** — wiki: *Mia brings good luck to our troops, granting all troops' attack a 50% chance of dealing 10%/20%/30%/40%/50% . more damage.*
  - interpretation: '50% more damage' = Damage Dealt, not the Attack stat
  - trigger `ChanceProc(p=0.5)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.5)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Foe, Target, Damage Taken, +0.5, dur=1), DamageMod(Friend, All, Damage Dealt, +0.5), DamageMod(Friend, All, Damage Taken, -0.5)]
- **S3 Ritual Deciphering** — wiki: *Mia foresees potential dangers before battle, granting a 40% chance of reducing damage taken by 10%/20%/30%/40%/50% for all troops.*
  - trigger `ChanceProc(p=0.4)` → L5: [DamageMod(Friend, All, Damage Taken, -0.5)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Foe, Target, Damage Taken, +0.5, dur=1), DamageMod(Friend, All, Damage Dealt, +0.5), DamageMod(Friend, All, Damage Taken, -0.5)]

### Molly  (own class: Lancer)
- **S1 Snow's Grace** — wiki: *Molly creates an avalanche that clouds enemy sights, granting a 40% chance of reducing all troops' Damage Taken by 10%/20%/30%/40%/50%*
  - trigger `ChanceProc(p=0.4)` → L5: [DamageMod(Friend, All, Damage Taken, -0.5)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Taken, -0.5), DamageMod(Friend, All, Damage Dealt, +0.5), DamageMod(Friend, All, Damage Dealt, +0.25)]
- **S2 Ice Dominion** — wiki: *Molly excels in snowy terrains, granting all troops' attack a 50% chance of increasing damage dealt by + 10%/20%/30%/40%/50% .*
  - trigger `ChanceProc(p=0.5)` → L5: [DamageMod(Friend, All, Damage Dealt, +0.5)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Taken, -0.5), DamageMod(Friend, All, Damage Dealt, +0.5), DamageMod(Friend, All, Damage Dealt, +0.25)]
- **S3 Youthful Rage** — wiki: *Hell hath no fury like an angry Molly. Increasing damage dealt by + 5%/10%/15%/20%/25% damage.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.25)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05)]

### Natalia  (own class: Infantry)
- **S1 Feral Protection** — wiki: *Natalia Commands the beasts to cover your troops, granting a 40% chance of reducing all troops' Damage Taken by 10%/20%/30%/40%/50%*
  - trigger `ChanceProc(p=0.4)` → L5: [DamageMod(Friend, All, Damage Taken, -0.5)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Taken, -0.5), StatMod(Friend, All, Attack, +0.25), DamageMod(Friend, All, Damage Dealt, +0.25)]
- **S2 Queen of the Wild** — wiki: *Natalia is a natural leader, increasing Attack by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S3 Call of the Wild** — wiki: *Natalia's unexplained connection with nature allows her to rally wild beast, increasing damage dealt by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.25)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05)]

### Nora  (own class: Lancer)
- **S1 Combined Arms** — wiki: *Norah is well trained in combined arms tactics, decreasing Damage Taken by 3%/6%/9%/12%/15% and boosting Damage Dealt by 3%/6%/9%/12%/15% for Infantry and Marksman.*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Dealt, +0.15)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.03), DamageMod(Friend, Marksman, Damage Taken, -0.03), DamageMod(Friend, Infantry, Damage Dealt, +0.03), DamageMod(Friend, Marksman, Damage Dealt, +0.03)]
- **S2 Sneak Strike** — wiki: *Norah has an eye for weaknesses, granting her Lancers a 20% chance of dealing 20%/40%/60%/80%/100% extra damage to all enemies on attack.*
  - trigger `ChanceProc(p=0.2)` → L5: [DamageMod(Friend, Lancer, Damage Dealt, +1)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Dealt, +0.15), DamageMod(Friend, Lancer, Damage Dealt, +1)]
- **S3 Momentum** — wiki: *Norah motivates our troops, increasing all troops' Damage Dealt by 5%/10%/15%/20%/25% and reducing their damage taken by 5%/10%/15%/20%/25% every 5 attack made by lancer for 2 turns.*
  - trigger `Cadence(every 6 attack)` [only when Lancer attacks] → L5: [DamageMod(Friend, All, Damage Dealt, +0.25, dur=2), DamageMod(Friend, All, Damage Taken, -0.25, dur=2)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05, dur=2), DamageMod(Friend, All, Damage Taken, -0.05, dur=2)]
  - BEHAVIOR: level 5, view(attack=6, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Dealt, +0.15), DamageMod(Friend, All, Damage Dealt, +0.25, dur=2), DamageMod(Friend, All, Damage Taken, -0.25, dur=2)]
  - BEHAVIOR (must not fire the cadence): view(attack=5, rng=NOFIRE) → [DamageMod(Friend, Infantry, Damage Taken, -0.15), DamageMod(Friend, Marksman, Damage Taken, -0.15), DamageMod(Friend, Infantry, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Dealt, +0.15)]

### Patrick  (own class: Lancer)
- **S1 Super Nutrients** — wiki: *Patrick's culinary masterpieces invigorate our troops, increasing Health by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Health, +0.25)]
    L1: [StatMod(Friend, All, Health, +0.05)]
- **S2 Caloric Booster** — wiki: *Patrick's gourmet meals motivate and unleash the potential of our soldiers, increasing Attack by 5%/10%/15%/20%/25% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]

### Philly  (own class: Lancer)
- **S1 Vigor Tactics** — wiki: *Philly's secret remedy strengthens the soldiers, increasing Attack by 3%/6%/9%/12%/15% and Defense by 2%/4%/6%/8%/10% for all troops.*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.15)]
    L1: [StatMod(Friend, All, Attack, +0.03)]
  - trigger `Passive` → L5: [StatMod(Friend, All, Defense, +0.1)]
    L1: [StatMod(Friend, All, Defense, +0.02)]
- **S2 Dosage Boost** — wiki: *Philly's uses her secret tonic to enhance the warriors' strength, granting all troops' attack a 25% chance of dealing + 120%/140%/160%/180%/200% damage.*
  - interpretation: fix: 200% damage = 2x = +100% max, not +200%
  - trigger `ChanceProc(p=0.25)` → L5: [DamageMod(Friend, All, Damage Dealt, +1)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Attack, +0.15), StatMod(Friend, All, Defense, +0.1), DamageMod(Friend, All, Damage Dealt, +1), DamageMod(Friend, All, Damage Taken, -0.5)]
- **S3 Energizing Shot** — wiki: *Phillys special shot improves troops focus, granting a 40% chance of reducing all troops Damage Taken by 10%/20%/30%/40%/50% .*
  - trigger `ChanceProc(p=0.4)` → L5: [DamageMod(Friend, All, Damage Taken, -0.5)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.1)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Attack, +0.15), StatMod(Friend, All, Defense, +0.1), DamageMod(Friend, All, Damage Dealt, +1), DamageMod(Friend, All, Damage Taken, -0.5)]

### Reina  (own class: Lancer)
- **S1 Assassin's Instinct** — wiki: *Reina targets enemy weak spots, increasing normal attack damage by 10%/15%/20%/25%/30% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.3, Normal)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.1, Normal)]
- **S2 Swift Jive** — wiki: *Reina's adept leadership grants all troops a 4%/8%/12%/16%/20% chance of dodging normal attacks.*
  - interpretation: probability is the per-level value; effect is level-independent
  - trigger `ScaledChance` → L5: [DamageMod(Friend, All, Damage Taken, -1, Normal)]
    L1: [DamageMod(Friend, All, Damage Taken, -1, Normal)]
- **S3 Shadow Blade** — wiki: *With Reina's clever tactics, her lancers have a 25% chance of performing an extra attack, dealing 120%/140%/160%/180%/200% damage.*
  - interpretation: fix: extra strike (not a DD buff); 200% = 2x strike
  - trigger `ChanceProc(p=0.25)` → L5: [ExtraAttack(Lancer, dmg_x=2)]
    L1: [ExtraAttack(Lancer, dmg_x=1.2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [DamageMod(Friend, All, Damage Dealt, +0.3, Normal), DamageMod(Friend, All, Damage Taken, -1, Normal), ExtraAttack(Lancer, dmg_x=2)]

### Renee  (own class: Lancer)
- **S1 Nightmare Trace** — wiki: *Renee always fights in unbelievable ways. The troops she commands can place Dream Marks on their targets every two turns, dealing extra 40%/80%/120%/160%/200% Lancer Damage once next turn. The Dream Marks last for 1 turns.*
  - interpretation: Dream-Mark targeting approximated
  - trigger `Cadence(every 2 turn)` → L5: [DamageMod(Friend, Lancer, Damage Dealt, +2, dur=1)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.4, dur=1)]
  - BEHAVIOR: level 5, view(turn=2, rng=NOFIRE) → [DamageMod(Friend, Lancer, Damage Dealt, +2, dur=1), DamageMod(Friend, Lancer, Damage Dealt, +1.5, dur=1), DamageMod(Foe, Target, Damage Taken, +0.75, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(turn=1, rng=NOFIRE) → []  (nothing fires)
- **S2 Dreamcatcher** — wiki: *Renee's Dreams Marks highilght ennemy vulnerabilities, incresing her Lancer's damage dealt to marked targets by 30%/60%/90%/120%/150% .*
  - interpretation: marked-target conditional approximated
  - trigger `Cadence(every 2 turn)` → L5: [DamageMod(Friend, Lancer, Damage Dealt, +1.5, dur=1)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.3, dur=1)]
  - BEHAVIOR: level 5, view(turn=2, rng=NOFIRE) → [DamageMod(Friend, Lancer, Damage Dealt, +2, dur=1), DamageMod(Friend, Lancer, Damage Dealt, +1.5, dur=1), DamageMod(Foe, Target, Damage Taken, +0.75, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(turn=1, rng=NOFIRE) → []  (nothing fires)
- **S3 Dreamslice** — wiki: *Renee's Dream Marks expose ennemy weaknesses, increasing damage dealt to marked targets by 15%/30%/45%/60%/75% for all troops.*
  - interpretation: fix: was Inf+MM only (Lancer missing); now the marked frontline target
  - trigger `Cadence(every 2 turn)` → L5: [DamageMod(Foe, Target, Damage Taken, +0.75, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.15, dur=1)]
  - BEHAVIOR: level 5, view(turn=2, rng=NOFIRE) → [DamageMod(Friend, Lancer, Damage Dealt, +2, dur=1), DamageMod(Friend, Lancer, Damage Dealt, +1.5, dur=1), DamageMod(Foe, Target, Damage Taken, +0.75, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(turn=1, rng=NOFIRE) → []  (nothing fires)

### Rufus  (own class: Marksman)
- **S1 Inferno Regiment** — wiki: *Rufus uses his bold leadership to transform all troops into blazing flames on the battlefield, increasing their Attack by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S2 Armor Crush** — wiki: *Rufus equips his Marksmen with armor-piercing rounds, dealing 12%/24%/36%/48%/60% extra damage for each attack and increases the target's damage taken by 5%/10%/15%/20%/25% for 1 turn.*
  - interpretation: fix: was Attack stat; is Damage Dealt
  - trigger `Cadence(every 1 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.6)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.12)]
  - trigger `Cadence(every 1 attack)` [only when Marksman attacks] → L5: [DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=1, rng=NOFIRE) → [StatMod(Friend, All, Attack, +0.25), DamageMod(Friend, Marksman, Damage Dealt, +0.6), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=0, rng=NOFIRE) → [StatMod(Friend, All, Attack, +0.25)]
- **S3 Wrathful Quake** — wiki: *Rufus' aggressive combat style grants all troops a 20% chance to intimidate enemies, reducing their Lethality by 10%/20%/30%/40%/50% for 2 turns.*
  - trigger `ChanceProc(p=0.2)` → L5: [StatMod(Foe, All, Lethality, -0.5, dur=2)]
    L1: [StatMod(Foe, All, Lethality, -0.1, dur=2)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Attack, +0.25), DamageMod(Friend, Marksman, Damage Dealt, +0.6), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1), StatMod(Foe, All, Lethality, -0.5, dur=2)]

### Seo-yoon  (own class: Marksman)
- **S1 Rallying Beat** — wiki: *Seo-yoon beats the war drum to boost morale, increasing Troops Attack by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S2 Soothing Dance** — wiki: *Seo-yoon treats wounded troops with traditional medicine, increasing Healing speed in the infirmary by 10%/20%/30%/40%/50% .*
  - interpretation: infirmary-healing-speed skill; no combat effect
  - trigger `Passive`: NON-COMBAT — resolve emits nothing

### Sergey  (own class: Infantry)
- **S1 Defenders' Edge** — wiki: *Sergey's guards our troops with his shield, reducing damage taken by 4%/8%/12%/16%/20% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Taken, -0.2)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.04)]
- **S2 Weaken** — wiki: *Sergey's intimidating presence reduces Attack by 4%/8%/12%/16%/20% for all enemy troops.*
  - trigger `Passive` → L5: [StatMod(Foe, All, Attack, -0.2)]
    L1: [StatMod(Foe, All, Attack, -0.04)]

### Sonya  (own class: Lancer)
- **S1 Treasure Hunter** — wiki: *“Everyone has a share when the legendary ocean treasure is found!” Sonya’s promise inspires everyone, increasing Damage by 4%/8%/12%/16%/20% for all troops.*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.2)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.04)]
- **S2 Bounty Temptation** — wiki: *Sonya motivates her Troops with bounty, making her Lancers deal 15%/30%/45%/60%/75% more damage every 2 attacks and increasing Attack by 5%/10%/15%/20%/25% for all troops for 1 turn.*
  - interpretation: fix: Lancer '75% more damage' is Damage Dealt, not Attack
  - trigger `Cadence(every 2 attack)` [only when Lancer attacks] → L5: [DamageMod(Friend, Lancer, Damage Dealt, +0.75)]
    L1: [DamageMod(Friend, Lancer, Damage Dealt, +0.15)]
  - trigger `Cadence(every 2 attack)` [only when Lancer attacks] → L5: [StatMod(Friend, All, Attack, +0.25, dur=1)]
    L1: [StatMod(Friend, All, Attack, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.2), DamageMod(Friend, Lancer, Damage Dealt, +0.75), StatMod(Friend, All, Attack, +0.25, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.2)]
- **S3 Torrential Impact** — wiki: *Sonya’s Lancers will seize every chance to launch a surprise raid like underwater currents. Her Lancers deal 50%/100%/150%/200%/250% damage every 5 turns and stun the target for 1 turn.*
  - interpretation: deal X% damage = an extra strike at Xx normal; stun dropped
  - trigger `Cadence(every 5 turn)` → L5: [ExtraAttack(Lancer, dmg_x=2.5)]
    L1: [ExtraAttack(Lancer, dmg_x=0.5)]
  - BEHAVIOR: level 5, view(turn=5, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.2), ExtraAttack(Lancer, dmg_x=2.5)]
  - BEHAVIOR (must not fire the cadence): view(turn=4, rng=NOFIRE) → [DamageMod(Friend, All, Damage Dealt, +0.2)]

### Viveca  (own class: Marksman)
- **S1 Nightfall Legion** — wiki: *Applies the Night Guard's tactics on the battlefield, increasing the Attack of all allied troops by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Attack, +0.25)]
    L1: [StatMod(Friend, All, Attack, +0.05)]
- **S2 Shadow World** — wiki: *Viveca's Marksmen gain tremendous insight from their battles against darkness, allowing them to pinpoint enemy weaknesses. Attacks have a 20% chance to deal 20%/40%/60%/80%/100% extra damage to all enemy troops.*
  - trigger `ChanceProc(p=0.2)` → L5: [DamageMod(Friend, Marksman, Damage Dealt, +1, Skills)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.2, Skills)]
  - BEHAVIOR: level 5, view(turn=1, attack=1, rng=FIRE) → [StatMod(Friend, All, Attack, +0.25), DamageMod(Friend, Marksman, Damage Dealt, +1, Skills), DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1)]
- **S3 Children of the Mist** — wiki: *The formations and tactics of the Night's Guard provide balanced offense and defense, reducing damage taken by allied Infantry by 2%/4%/6%/8%/10% . and increasing damage dealt by allied Marksmen by 2%/4%/6%/8%/10% .*
  - trigger `Passive` → L5: [DamageMod(Friend, Infantry, Damage Taken, -0.1), DamageMod(Friend, Marksman, Damage Dealt, +0.1)]
    L1: [DamageMod(Friend, Infantry, Damage Taken, -0.02), DamageMod(Friend, Marksman, Damage Dealt, +0.02)]

### Vulcanus  (own class: Marksman)
- **S1 Raging Storm** — wiki: *Vulcanus is skilled in the arts of terror and manipulation, reducing all enemy troops' Attack by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [StatMod(Foe, All, Attack, -0.2)]
    L1: [StatMod(Foe, All, Attack, -0.04)]
- **S2 Breaker Steel** — wiki: *There's no steel like the blades in Vulcanus' armory, empowering all troops to deal 20%/40%/60%/80%/100% extra damage after every 5 attacks, and increasing damage taken for the target by 5%/7.5%/10%/12.5%/15% in the next attack.*
  - interpretation: attacks(5) -> real interval 6 (measured 6/12/18)
  - interpretation: target +DT on the attack AFTER each every-6 proc (attacks 7/13/19), not every attack; TARGET = struck unit. Precise arm-on-6/consume-on-7 coupling is engine-resolved.
  - trigger `Cadence(every 6 attack)` → L5: [DamageMod(Friend, All, Damage Dealt, +1)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.2)]
  - trigger `Cadence(every 6 attack, offset 1)` → L5: [DamageMod(Foe, Target, Damage Taken, +0.15, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=6, rng=NOFIRE) → [StatMod(Foe, All, Attack, -0.2), DamageMod(Friend, All, Damage Dealt, +1)]
  - BEHAVIOR (must not fire the cadence): view(attack=5, rng=NOFIRE) → [StatMod(Foe, All, Attack, -0.2)]
- **S3 True Strike** — wiki: *Vulcanus' modified armor-piercing arrows reduce enemy Infantry and Lancer Defense by 12%/24%/36%/48%/60% for 3 turns and increase our Marksmen's Attack by 12%/24%/36%/48%/60% for 1 turn.*
  - trigger `Cadence(every 3 turn)` → L5: [StatMod(Foe, Infantry, Defense, -0.6, dur=3), StatMod(Foe, Lancer, Defense, -0.6, dur=3), StatMod(Friend, Marksman, Attack, +0.6, dur=1)]
    L1: [StatMod(Foe, Infantry, Defense, -0.12, dur=3), StatMod(Foe, Lancer, Defense, -0.12, dur=3), StatMod(Friend, Marksman, Attack, +0.12, dur=1)]
  - BEHAVIOR: level 5, view(turn=3, rng=NOFIRE) → [StatMod(Foe, All, Attack, -0.2), StatMod(Foe, Infantry, Defense, -0.6, dur=3), StatMod(Foe, Lancer, Defense, -0.6, dur=3), StatMod(Friend, Marksman, Attack, +0.6, dur=1)]
  - BEHAVIOR (must not fire the cadence): view(turn=2, rng=NOFIRE) → [StatMod(Foe, All, Attack, -0.2)]

### Wayne  (own class: Marksman)
- **S1 Thunder Strike** — wiki: *Wayne's brilliant battle planning allows all troops to launch an extra attack every 4 turns, dealing 20%/40%/60%/80%/100% damage.*
  - interpretation: fix: extra attack, not a DD buff
  - trigger `Cadence(every 4 turn)` → L5: [ExtraAttack(All, dmg_x=1)]
    L1: [ExtraAttack(All, dmg_x=0.2)]
  - BEHAVIOR: level 5, view(turn=4, rng=NOFIRE) → [ExtraAttack(All, dmg_x=1), Crit(All, rate=0.25)]
  - BEHAVIOR (must not fire the cadence): view(turn=3, rng=NOFIRE) → [Crit(All, rate=0.25)]
- **S2 Roundabout Hit** — wiki: *Wayne's stratagems can pierce the thickest of defense. On every other attack, his Marksmen deal 8%/16%/24%/32%/40% extra damage to enemy Lancer and 4%/8%/12%/16%/20% extra damage to enemy Marksmen.*
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.4, Skills, vs=Lancer)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.08, Skills, vs=Lancer)]
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.2, Skills, vs=Marksman)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.04, Skills, vs=Marksman)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [DamageMod(Friend, Marksman, Damage Dealt, +0.4, Skills, vs=Lancer), DamageMod(Friend, Marksman, Damage Dealt, +0.2, Skills, vs=Marksman), Crit(All, rate=0.25)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → [Crit(All, rate=0.25)]
- **S3 Fleet** — wiki: *Wayne ensure no misstep goes unpunished with an eagle's eye for weakness, granting all troop's attacks a 5%/10%/15%/20%/25% Crit Rate.*
  - trigger `Passive` → L5: [Crit(All, rate=0.25)]
    L1: [Crit(All, rate=0.05)]

### Wu Ming  (own class: Infantry)
- **S1 Shadow's Evasion** — wiki: *Wu Ming moves like a shadow, dodging and coutering ennemies, reducing his troops' damage taken from normal attacks by 5%/10%/15%/20%/25% and from skills by 6%/12%/18%/34%/30% .*
  - interpretation: fix: all troops, not Infantry-only
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Taken, -0.25, Normal)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.05, Normal)]
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Taken, -0.3, Skills)]
    L1: [DamageMod(Friend, All, Damage Taken, -0.06, Skills)]
- **S2 Crescent Uplift** — wiki: *Wu Ming spreads his wisdom and techniques, increasing friendly troops' damage dealt by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.2)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.04)]
- **S3 Elemental Resonance** — wiki: *Wu Ming leads everyone to a heightened affinity with their combat techniques, incresaing troops' skill damage dealt by 5%/10%/15%/20%/25% .*
  - trigger `Passive` → L5: [DamageMod(Friend, All, Damage Dealt, +0.25, Skills)]
    L1: [DamageMod(Friend, All, Damage Dealt, +0.05, Skills)]

### Xura  (own class: Marksman)
- **S1 Fungal Fog** — wiki: *Xura releases an underground fungi that quickly multiplies to block enemy vision, reducing damage dealt to friendly troops by 4%/8%/12%/16%/20% .*
  - trigger `Passive` → L5: [DamageMod(Foe, All, Damage Dealt, -0.2)]
    L1: [DamageMod(Foe, All, Damage Dealt, -0.04)]
- **S2 Piercing Arrow** — wiki: *Being able to identify the weak spots in the enemy's armor, Xura's Marksmen deal 20%/40%/60%/80%/100% additional damage every 2 strikes and make their target take 5%/10%/15%/20%/25% more damage for 1 turn.*
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Friend, Marksman, Damage Dealt, +1)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.2)]
  - trigger `Cadence(every 2 attack)` [only when Marksman attacks] → L5: [DamageMod(Foe, Target, Damage Taken, +0.25, dur=1)]
    L1: [DamageMod(Foe, Target, Damage Taken, +0.05, dur=1)]
  - BEHAVIOR: level 5, view(attack=2, rng=NOFIRE) → [DamageMod(Foe, All, Damage Dealt, -0.2), DamageMod(Friend, Marksman, Damage Dealt, +1), DamageMod(Foe, Target, Damage Taken, +0.25, dur=1), DamageMod(Friend, Marksman, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Taken, -0.1)]
  - BEHAVIOR (must not fire the cadence): view(attack=1, rng=NOFIRE) → [DamageMod(Foe, All, Damage Dealt, -0.2), DamageMod(Friend, Marksman, Damage Dealt, +0.15), DamageMod(Friend, Marksman, Damage Taken, -0.1)]
- **S3 Unorthodoxy** — wiki: *Xura's unorthodox tactics are quite disruptive, increasing Marksmen’s damage dealt by 3%/6%/9%/12%/15% while reducing their damage taken by 2%/4%/6%/8%/10% .*
  - trigger `Passive` → L5: [DamageMod(Friend, Marksman, Damage Dealt, +0.15)]
    L1: [DamageMod(Friend, Marksman, Damage Dealt, +0.03)]
  - trigger `Passive` → L5: [DamageMod(Friend, Marksman, Damage Taken, -0.1)]
    L1: [DamageMod(Friend, Marksman, Damage Taken, -0.02)]

### Zinman  (own class: Marksman)
- **S1 Implacable** — wiki: *Zinman the master builder understands what is required of a strong defensive line, increasing all troops' Defense by 2%/4%/6%/8%/10% and Health by 2%/4%/6%/8%/10% .*
  - trigger `Passive` → L5: [StatMod(Friend, All, Defense, +0.1), StatMod(Friend, All, Health, +0.1)]
    L1: [StatMod(Friend, All, Defense, +0.02), StatMod(Friend, All, Health, +0.02)]
- **S2 Bastionist** — wiki: *Zinman's skillful control of the construction workflow reduces basic resource consumption (Meat, Wood, Coal, Iron) by 3%/6%/9%/12%/15% and increases Building Upgrade speed by 3%/6%/9%/12%/15%*
  - interpretation: building/resource skill; no combat effect
  - trigger `Passive`: NON-COMBAT — resolve emits nothing
- **S3 Positional Battler** — wiki: *Zinman masterfully manipulates the battlefield, increasing Lethality by 5%/10%/15%/20%/25% for all troops.*
  - interpretation: fix: Lethality, not Damage Dealt
  - trigger `Passive` → L5: [StatMod(Friend, All, Lethality, +0.25)]
    L1: [StatMod(Friend, All, Lethality, +0.05)]

