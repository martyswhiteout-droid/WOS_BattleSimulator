"""Full 54-hero roster as per-hero classes (Stage 8 hero rebuild).

Each hero declares its expedition skills (S1-S3) using the hero_kit vocabulary,
with EVERY audit correction applied (shields as absorb, dynamic frontline targets,
Vulcanus/every-5 cadence -> 6, dropped skills restored, attribute/magnitude fixes,
real proc% not EV-average). The 6 exemplars (Bradley, Sergey, Gatot, Vulcanus,
Hector, Mia) are imported from hero_kit; the other 48 are defined here.

NOT wired to the engine (design artifact). Widgets (context-gated flat buffs) and
hero AURAS are out of scope for this pass. `troop` is the hero's own class; where
the wiki gave no class hint it is marked `# troop unverified` for Martin to confirm.
"""
from __future__ import annotations

from wos_sim.formula_research.hero_kit import (
    Hero, Skill, Passive, ChanceProc, ScaledChance, attacks, turns,
    Side, Cls, Stat, Target, DmgKind, Category,
    StatMod, DamageMod, Crit, Shield, ExtraAttack, DecayingDamage,
    Bradley, Sergey, Gatot, Vulcanus, Hector, Mia,   # the 6 exemplars
)

F, E = Side.FRIEND, Side.FOE
DD, DT = DmgKind.DEALT, DmgKind.TAKEN


class Ahmose(Hero):
    name, troop = "Ahmose", Cls.INF
    def build_skills(self):
        return [
            # Viper Formation: DT reductions every 4 attacks for 2 turns. Two ladders.
            # (The "pauses attack once every 4th" sub-mechanic is not yet modeled.)
            Skill("S1", "Viper Formation", attacks(4), (-.10,-.25,-.40,-.55,-.70),
                  lambda v: [DamageMod(F, Target.INF, DT, v, duration_turns=2)]),
            Skill("S1", "Viper Formation", attacks(4), (-.10,-.15,-.20,-.25,-.30),
                  lambda v: [DamageMod(F, Target.LAN, DT, v, duration_turns=2),
                             DamageMod(F, Target.MM, DT, v, duration_turns=2)]),
            Skill("S2", "Prayer of Flame", Passive(), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.INF, DD, v)]),
            Skill("S3", "Blade of Light", attacks(1), (.12,.24,.36,.48,.60),
                  lambda v: [DamageMod(F, Target.INF, DD, v)]),
            Skill("S3", "Blade of Light", attacks(1), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v, duration_turns=1)]),
        ]


class Alonso(Hero):
    name, troop = "Alonso", Cls.MM   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Onslaught", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [StatMod(F, Target.ALL, Stat.LET, v)]),
            Skill("S2", "Iron Strength", ChanceProc(0.20), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(E, Target.ALL, DD, -v, duration_turns=2)]),
            Skill("S3", "Poison Harpoon", ChanceProc(0.50), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
        ]


class Bahiti(Hero):
    name, troop = "Bahiti", Cls.MM   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "Sixth Sense", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
            # S2 Fluorescence was DROPPED (0 rows) -> restored.
            Skill("S2", "Fluorescence", ChanceProc(0.50), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
        ]


class Blanchette(Hero):
    name, troop = "Blanchette", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Armed to the Teeth", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.LET, v)]),
            # Blood Hunter: "every 3 rounds" -> treated as turns (rounds==turns).
            Skill("S2", "Blood Hunter", turns(3), (.15,.30,.45,.60,.75),
                  lambda v: [DamageMod(F, Target.MM, DD, v)]),
            # Crimson Sniper: Marksmen deal +40% vs enemy LANCER, +20% vs enemy MARKSMAN
            # every 2 strikes (QA fix: vs_class condition, no longer cumulative).
            Skill("S3", "Crimson Sniper", attacks(2), (.08,.16,.24,.32,.40),
                  lambda v: [DamageMod(F, Target.MM, DD, v, vs_class=Cls.LAN)]),
            Skill("S3", "Crimson Sniper", attacks(2), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.MM, DD, v, vs_class=Cls.MM)]),
        ]


class Cara(Hero):
    name, troop = "Cara", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Smoky Encounter", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [StatMod(E, Target.ALL, Stat.LET, -v)]),
            # Mech Pet: "normal attack damage" -> Damage Dealt (Normal), NOT Attack.
            Skill("S2", "Mech Pet", Passive(), (.10,.15,.20,.25,.30),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, category=Category.NORMAL)],
                  note="fix: was Attack stat; is normal Damage Dealt"),
            # Witch's Wrath: Marksmen deal +40% vs LANCER, +20% vs MARKSMAN every 2
            # attacks (QA fix: vs_class). Frontline-bypass targeting still not modelled.
            Skill("S3", "Witch's Wrath", attacks(2), (.08,.16,.24,.32,.40),
                  lambda v: [DamageMod(F, Target.MM, DD, v, category=Category.SKILLS, vs_class=Cls.LAN)],
                  note="bypass-to-backline not yet modelled"),
            Skill("S3", "Witch's Wrath", attacks(2), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.MM, DD, v, category=Category.SKILLS, vs_class=Cls.MM)]),
        ]


class Dominic(Hero):
    name, troop = "Dominic", Cls.LAN
    def build_skills(self):
        return [
            Skill("S1", "Mystic Mechanism", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, category=Category.NORMAL)]),
            Skill("S2", "Spiky Assault", attacks(1), (.12,.24,.36,.48,.60),
                  lambda v: [DamageMod(F, Target.LAN, DD, v, category=Category.NORMAL)]),
            Skill("S2", "Spiky Assault", attacks(1), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v, duration_turns=1)]),
            Skill("S3", "Mirror Maze", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [DamageMod(F, Target.INF, DT, -v), DamageMod(F, Target.MM, DT, -v),
                             DamageMod(F, Target.INF, DD, v, category=Category.NORMAL),
                             DamageMod(F, Target.MM, DD, v, category=Category.NORMAL)]),
        ]


class Edith(Hero):
    name, troop = "Edith", Cls.INF   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Strategic Balance", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.LAN, DD, v), DamageMod(F, Target.MM, DT, -v)]),
            Skill("S2", "Ironclad", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.INF, DT, -v)]),
            Skill("S3", "Steel Sentinel", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.HP, v)]),
        ]


class Eleonora(Hero):
    name, troop = "Eleonora", Cls.INF   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "Scorching Sun", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.HP, v)]),
            Skill("S2", "Solaris Nexus", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [DamageMod(F, Target.INF, DT, -v), DamageMod(F, Target.MM, DD, v)]),
            # Soaring Flame: every 5 Infantry attacks -> real interval 6.
            Skill("S3", "Soaring Flame", attacks(5), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, duration_turns=2),
                             DamageMod(F, Target.ALL, DT, -v, duration_turns=2)]),
        ]


class Elif(Hero):
    name, troop = "Elif", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Shackling Veil", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(E, Target.ALL, Stat.ATK, -v)]),
            Skill("S2", "Slash Formation", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S2", "Slash Formation", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v)]),
            # Enchanting Tapestry: SHIELD = Attack*pct on her Infantry each attack (was +Def).
            Skill("S3", "Enchanting Tapestry", attacks(1), (.06,.12,.18,.24,.30),
                  lambda v: [Shield(Target.INF, Stat.ATK, v, duration_turns=1)],
                  on_class=Cls.INF,
                  note="fix: was +30% Defense; is an Attack-scaled Shield (INF attacks only)"),
        ]


class Estrella(Hero):
    name, troop = "Estrella", Cls.LAN   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "Corrosive Color", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(E, Target.ALL, Stat.DEF, -v)]),
            Skill("S2", "Dawn Canvas", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S2", "Dawn Canvas", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v)]),
            Skill("S3", "Splendid Scene", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.INF, DT, -v), DamageMod(F, Target.LAN, DD, v)]),
        ]


class Flint(Hero):
    name, troop = "Flint", Cls.INF
    def build_skills(self):
        return [
            # Pyromaniac: passive per wiki (was mislabelled Turn-based).
            Skill("S1", "Pyromaniac", Passive(), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.INF, DD, v)],
                  note="fix: passive per wiki, not Turn-based"),
            Skill("S2", "Burning Resolve", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S3", "Immolation", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.LET, v)]),
        ]


class Flora(Hero):
    name, troop = "Flora", Cls.LAN   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Enmiring Vines", ChanceProc(0.50), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(E, Target.ALL, DT, v)]),
            Skill("S2", "Plantage", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.INF, DT, -v, category=Category.NORMAL),
                             DamageMod(F, Target.LAN, DD, v, category=Category.NORMAL)]),
            Skill("S3", "Confusion Pollen", turns(4), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(E, Target.INF, DT, v, duration_turns=2, category=Category.NORMAL),
                             DamageMod(E, Target.MM, DD, -v, duration_turns=2, category=Category.NORMAL)]),
        ]


class Fred(Hero):
    name, troop = "Fred", Cls.LAN
    def build_skills(self):
        return [
            Skill("S1", "Hydraulic Suppression", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [StatMod(E, Target.ALL, Stat.LET, -v)]),
            Skill("S2", "Acidification", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(E, Target.INF, DT, v)]),
            Skill("S3", "Floodbringer", attacks(4), (.40,.80,1.20,1.60,2.00),
                  lambda v: [DamageMod(F, Target.LAN, DD, v)]),
            Skill("S3", "Floodbringer", attacks(4), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(E, Target.ALL, DD, -v, duration_turns=1)]),
        ]


class Freya(Hero):
    name, troop = "Freya", Cls.LAN
    def build_skills(self):
        return [
            Skill("S1", "Fog of War", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [StatMod(E, Target.ALL, Stat.ATK, -v)]),
            # Blood Moon Scythe: 50% chance of an EXTRA attack ("Reap") dealing 100% dmg.
            Skill("S2", "Blood Moon Scythe", ChanceProc(0.50), (.20,.40,.60,.80,1.00),
                  lambda v: [ExtraAttack(Target.LAN, v)],
                  note="fix: Reap is an extra strike, not a DD buff"),
            Skill("S3", "Night's Vengeance", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [DamageMod(F, Target.INF, DT, -v), DamageMod(F, Target.MM, DT, -v),
                             DamageMod(F, Target.INF, DD, v), DamageMod(F, Target.MM, DD, v)]),
        ]


class Gisela(Hero):
    name, troop = "Gisela", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Alloyed Defense", Passive(), (.06,.12,.18,.24,.30),
                  lambda v: [StatMod(F, Target.INF, Stat.DEF, v)]),
            Skill("S2", "Scavengeworks", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v, duration_turns=1)]),
            Skill("S3", "Trial Shield", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
        ]


class Gordon(Hero):
    name, troop = "Gordon", Cls.LAN
    def build_skills(self):
        return [
            # Venom Infusion: every 2 attacks, Lancer +100% dmg; poison ALL enemy
            # classes -20% DD (fix: was Inf duplicated, Lancer missing).
            Skill("S1", "Venom Infusion", attacks(2), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.LAN, DD, v)]),
            Skill("S1", "Venom Infusion", attacks(2), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(E, Target.TARGET, DD, -v, duration_turns=1)],
                  note="Martin 2026-07-25: poison hits ONLY the struck target unit "
                       "(1 Lancer -> 1 Infantry, not all of the class), not all-3"),
            Skill("S2", "Chemical Terror", turns(3), (.30,.60,.90,1.20,1.50),
                  lambda v: [DamageMod(F, Target.LAN, DD, v, duration_turns=1)]),
            Skill("S2", "Chemical Terror", turns(3), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(E, Target.ALL, DD, -v, duration_turns=1)]),
            Skill("S3", "Toxic Release", turns(4), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(E, Target.INF, DT, v, duration_turns=2),
                             DamageMod(E, Target.MM, DD, -v, duration_turns=2)]),
        ]

class Greg(Hero):
    name, troop = "Greg", Cls.MM   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Sword of Justice", ChanceProc(0.20), (.08,.16,.24,.32,.40),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, duration_turns=3)]),
            Skill("S2", "Deterrence of Law", ChanceProc(0.20), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(E, Target.ALL, DD, -v, duration_turns=2)]),
            Skill("S3", "Law and Order", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.HP, v)]),
        ]


class Gregory(Hero):
    name, troop = "Gregory", Cls.INF   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "Legion of the Sun", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S1", "Legion of the Sun", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v)]),
            Skill("S2", "Charged Assault", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [Crit(Target.ALL, v)]),
            Skill("S3", "Unbroken", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.INF, DT, -v)]),
        ]


class Gwen(Hero):
    name, troop = "Gwen", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Eagle Vision", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v)]),
            # Air Dominance: every 5 attacks -> 6.
            Skill("S2", "Air Dominance", attacks(5), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
            Skill("S2", "Air Dominance", attacks(5), (.05,.075,.10,.125,.15),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v, duration_turns=1)]),
            # Blastmaster: "her troops" -> ALL (fix: was Marksman-only), every 4 attacks.
            Skill("S3", "Blastmaster", attacks(4), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)],
                  note="fix: all troops, not Marksman-only"),
        ]


class Hank(Hero):
    name, troop = "Hank", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Roaring Rage", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.LET, v)]),
            Skill("S2", "Flying Sparks", attacks(5), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v),
                             DamageMod(F, Target.ALL, DT, -v)]),
            Skill("S3", "Raging Force", turns(4), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(E, Target.INF, DT, v, duration_turns=2),
                             DamageMod(E, Target.MM, DD, -v, duration_turns=2)]),
        ]


class Hendrik(Hero):
    name, troop = "Hendrik", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Worm's Ravage", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(E, Target.ALL, Stat.DEF, -v)]),
            Skill("S2", "Armor of Barnacles", turns(4), (.06,.12,.18,.24,.30),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v, duration_turns=2)]),
            # Dragon's Heir: a SEPARATE attack dealing 8..40% (QA fix: extra strike,
            # not a +40% buff on the normal attack).
            Skill("S3", "Dragon's Heir", turns(3), (.08,.16,.24,.32,.40),
                  lambda v: [ExtraAttack(Target.MM, v)]),
        ]


class Hervor(Hero):
    name, troop = "Hervor", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Call For Blood", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.LET, v)]),
            Skill("S2", "Undying", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.INF, DT, -v, category=Category.NORMAL)]),
            Skill("S2", "Undying", Passive(), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(F, Target.INF, DT, -v, category=Category.SKILLS)]),
            Skill("S3", "Battlethirsty", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [DamageMod(F, Target.INF, DT, -v)]),
            Skill("S3", "Battlethirsty", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [DamageMod(F, Target.INF, DD, v, category=Category.NORMAL)]),
        ]


class Jasser(Hero):
    name, troop = "Jasser", Cls.MM   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Tactical Genius", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
            Skill("S2", "Enlightened Warfare", Passive(), None, None,   # non-combat (research)
                  note="research-speed skill; no combat effect"),
        ]


class Jeronimo(Hero):
    name, troop = "Jeronimo", Cls.INF   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "Battle Manifesto", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
            Skill("S2", "Swordmentor", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S3", "Expert Swordsmanship", turns(4), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, duration_turns=2)]),
        ]


class Jessie(Hero):
    name, troop = "Jessie", Cls.LAN   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Stand of Arms", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
            # Bulwarks was DROPPED (0 rows) -> restored.
            Skill("S2", "Bulwarks", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
        ]


class Karol(Hero):
    name, troop = "Karol", Cls.LAN   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "In the Wings", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
            Skill("S2", "Shieldbreaker", Passive(), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(E, Target.LAN, DT, v)]),
            Skill("S2", "Shieldbreaker", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(E, Target.INF, DT, v)]),
            Skill("S3", "Standard of Ages", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S3", "Standard of Ages", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v)]),
        ]


class Ligeia(Hero):
    name, troop = "Ligeia", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Nerf Poison", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(E, Target.ALL, Stat.DEF, -v)]),
            Skill("S2", "Corrosion", attacks(2), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.MM, DD, v, category=Category.SKILLS)]),
            Skill("S2", "Corrosion", attacks(2), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v, duration_turns=1)]),
            Skill("S3", "Toxic Tip", attacks(2), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.MM, DD, v, category=Category.NORMAL)]),
            Skill("S3", "Toxic Tip", attacks(2), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(E, Target.TARGET, DD, -v, duration_turns=1)]),
        ]


class LingXue(Hero):
    name, troop = "Ling Xue", Cls.LAN   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Fearsome Aura", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [StatMod(E, Target.ALL, Stat.ATK, -v)]),
            Skill("S2", "Total Control", Passive(), None, None,   # non-combat (training)
                  note="training-speed skill; no combat effect"),
        ]


class Lloyd(Hero):
    name, troop = "Lloyd", Cls.LAN
    def build_skills(self):
        return [
            Skill("S1", "Bird Invasion", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [StatMod(E, Target.ALL, Stat.LET, -v)]),
            Skill("S2", "Iceflare Bomb", turns(3), (.30,.60,.90,1.20,1.50),
                  lambda v: [StatMod(F, Target.LAN, Stat.ATK, v, duration_turns=1)]),
            Skill("S2", "Iceflare Bomb", turns(3), (.06,.12,.18,.24,.30),
                  lambda v: [StatMod(E, Target.ALL, Stat.LET, -v, duration_turns=1)]),
            Skill("S3", "Ingenious Mastery", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [StatMod(F, Target.ALL, Stat.LET, v)],
                  note="fix: real proc% (sibling EV-averaging removed)"),
        ]


class Logan(Hero):
    name, troop = "Logan", Cls.INF   # troop unverified
    def build_skills(self):
        return [
            # Lion's Might: passive per wiki (fix: was Turn-based proc).
            Skill("S1", "Lion's Might", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [StatMod(E, Target.ALL, Stat.ATK, -v)],
                  note="fix: passive per wiki, not a proc"),
            Skill("S2", "Lion Intimidation", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
            Skill("S3", "Leader Inspiration", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.HP, v)]),
        ]


class LumakBokan(Hero):
    name, troop = "Lumak Bokan", Cls.LAN   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Tactical Deception", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(E, Target.ALL, DD, -v)]),
            Skill("S2", "Emerald Warrior", Passive(), None, None,   # non-combat (march speed)
                  note="hunting-march-speed skill; no combat effect"),
        ]


class Lynn(Hero):
    name, troop = "Lynn", Cls.MM
    def build_skills(self):
        return [
            # Song of Lion: chance-based per wiki (fix: was Turn-based mislabel).
            Skill("S1", "Song of Lion", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)],
                  note="fix: 40% chance -> Chance-based, not Turn-based"),
            Skill("S2", "Melancholic Ballad", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(E, Target.ALL, DD, -v)]),
            # Oonai Cadenza: stackable ramp; each proc emits +v, engine ledger accumulates.
            Skill("S3", "Oonai Cadenza", attacks(3), (.01,.02,.03,.04,.05),
                  lambda v: [StatMod(F, Target.MM, Stat.ATK, v)],
                  note="stackable-until-end-of-battle: engine must accumulate, not refresh"),
        ]


class Magnus(Hero):
    name, troop = "Magnus", Cls.INF
    def build_skills(self):
        return [
            Skill("S1", "Rapacious", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S2", "Iron Phalanx", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [StatMod(F, Target.INF, Stat.DEF, v, duration_turns=1)],
                  on_class=Cls.INF, note="Infantry gain Defense when INFANTRY attacks"),
            Skill("S3", "Iceman", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [DamageMod(F, Target.INF, DT, -v),
                             DamageMod(F, Target.MM, DD, v)]),
        ]

class Molly(Hero):
    name, troop = "Molly", Cls.LAN   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Snow's Grace", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
            Skill("S2", "Ice Dominion", ChanceProc(0.50), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
            Skill("S3", "Youthful Rage", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
        ]


class Natalia(Hero):
    name, troop = "Natalia", Cls.INF   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "Feral Protection", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
            Skill("S2", "Queen of the Wild", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S3", "Call of the Wild", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
        ]


class Nora(Hero):
    name, troop = "Nora", Cls.LAN   # troop unverified
    def build_skills(self):
        return [
            Skill("S1", "Combined Arms", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [DamageMod(F, Target.INF, DT, -v), DamageMod(F, Target.MM, DT, -v),
                             DamageMod(F, Target.INF, DD, v), DamageMod(F, Target.MM, DD, v)]),
            Skill("S2", "Sneak Strike", ChanceProc(0.20), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.LAN, DD, v)]),
            Skill("S3", "Momentum", attacks(5), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, duration_turns=2),
                             DamageMod(F, Target.ALL, DT, -v, duration_turns=2)]),
        ]


class Patrick(Hero):
    name, troop = "Patrick", Cls.LAN   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Super Nutrients", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.HP, v)]),
            # Caloric Booster was DROPPED (0 rows) -> restored.
            Skill("S2", "Caloric Booster", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
        ]


class Philly(Hero):
    name, troop = "Philly", Cls.LAN   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Vigor Tactics", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S1", "Vigor Tactics", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v)]),
            # Dosage Boost: "200% damage" = 2x = +100% (fix: not +200%).
            Skill("S2", "Dosage Boost", ChanceProc(0.25), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)],
                  note="fix: 200% damage = 2x = +100% max, not +200%"),
            Skill("S3", "Energizing Shot", ChanceProc(0.40), (.10,.20,.30,.40,.50),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v)]),
        ]


class Reina(Hero):
    name, troop = "Reina", Cls.LAN
    def build_skills(self):
        return [
            Skill("S1", "Assassin's Instinct", Passive(), (.10,.15,.20,.25,.30),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, category=Category.NORMAL)]),
            # Swift Jive: dodge. Probability SCALES per level (4/8/12/16/20%); modelled
            # at max (production maxed). Dodge = negate the incoming normal attack.
            # Swift Jive: dodge chance SCALES per level (4/8/12/16/20%) via ScaledChance
            # (QA fix: was a fixed 20%). Effect = negate the incoming normal attack.
            Skill("S2", "Swift Jive", ScaledChance(), (.04,.08,.12,.16,.20),
                  lambda _: [DamageMod(F, Target.ALL, DT, -1.0, category=Category.NORMAL)],
                  note="probability is the per-level value; effect is level-independent"),
            # Shadow Blade: 25% chance EXTRA attack; its damage scales 120..200% of normal.
            Skill("S3", "Shadow Blade", ChanceProc(0.25), (1.20,1.40,1.60,1.80,2.00),
                  lambda v: [ExtraAttack(Target.LAN, v)],
                  note="fix: extra strike (not a DD buff); 200% = 2x strike"),
        ]


class Renee(Hero):
    name, troop = "Renee", Cls.LAN
    def build_skills(self):
        return [
            Skill("S1", "Nightmare Trace", turns(2), (.40,.80,1.20,1.60,2.00),
                  lambda v: [DamageMod(F, Target.LAN, DD, v, duration_turns=1)],
                  note="Dream-Mark targeting approximated"),
            Skill("S2", "Dreamcatcher", turns(2), (.30,.60,.90,1.20,1.50),
                  lambda v: [DamageMod(F, Target.LAN, DD, v, duration_turns=1)],
                  note="marked-target conditional approximated"),
            # Dreamslice: +dmg to marked target for all troops (fix: add Lancer via FRONTLINE).
            Skill("S3", "Dreamslice", turns(2), (.15,.30,.45,.60,.75),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v, duration_turns=1)],
                  note="fix: was Inf+MM only (Lancer missing); now the marked frontline target"),
        ]


class Rufus(Hero):
    name, troop = "Rufus", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Inferno Regiment", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            # Armor Crush: "extra damage each attack" -> Damage Dealt (fix: was Attack).
            Skill("S2", "Armor Crush", attacks(1), (.12,.24,.36,.48,.60),
                  lambda v: [DamageMod(F, Target.MM, DD, v)],
                  note="fix: was Attack stat; is Damage Dealt"),
            Skill("S2", "Armor Crush", attacks(1), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v, duration_turns=1)]),
            Skill("S3", "Wrathful Quake", ChanceProc(0.20), (.10,.20,.30,.40,.50),
                  lambda v: [StatMod(E, Target.ALL, Stat.LET, -v, duration_turns=2)]),
        ]


class SeoYoon(Hero):
    name, troop = "Seo-yoon", Cls.MM   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Rallying Beat", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S2", "Soothing Dance", Passive(), None, None,   # non-combat (healing speed)
                  note="infirmary-healing-speed skill; no combat effect"),
        ]


class Sonya(Hero):
    name, troop = "Sonya", Cls.LAN
    def build_skills(self):
        return [
            Skill("S1", "Treasure Hunter", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
            # Bounty Temptation: Lancer +75% DAMAGE (fix: was folded into Attack) + all +25% Attack 1t.
            Skill("S2", "Bounty Temptation", attacks(2), (.15,.30,.45,.60,.75),
                  lambda v: [DamageMod(F, Target.LAN, DD, v)],
                  note="fix: Lancer '75% more damage' is Damage Dealt, not Attack"),
            Skill("S2", "Bounty Temptation", attacks(2), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v, duration_turns=1)]),
            # Torrential Impact: a periodic surprise-raid strike dealing 50..250% damage
            # (QA fix: extra strike, not additive +250%). Stun dropped (not expedition).
            Skill("S3", "Torrential Impact", turns(5), (.50,1.00,1.50,2.00,2.50),
                  lambda v: [ExtraAttack(Target.LAN, v)],
                  note="deal X% damage = an extra strike at Xx normal; stun dropped"),
        ]


class Viveca(Hero):
    name, troop = "Viveca", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Nightfall Legion", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.ATK, v)]),
            Skill("S2", "Shadow World", ChanceProc(0.20), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.MM, DD, v, category=Category.SKILLS)]),
            Skill("S3", "Children of the Mist", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [DamageMod(F, Target.INF, DT, -v), DamageMod(F, Target.MM, DD, v)]),
        ]


class Wayne(Hero):
    name, troop = "Wayne", Cls.MM   # troop unverified
    def build_skills(self):
        return [
            # Thunder Strike: all troops EXTRA attack every 4 turns (fix: extra strike, not DD).
            Skill("S1", "Thunder Strike", turns(4), (.20,.40,.60,.80,1.00),
                  lambda v: [ExtraAttack(Target.ALL, v)],
                  note="fix: extra attack, not a DD buff"),
            # Roundabout Hit: +40% vs LANCER, +20% vs MARKSMAN (QA fix: vs_class).
            Skill("S2", "Roundabout Hit", attacks(2), (.08,.16,.24,.32,.40),
                  lambda v: [DamageMod(F, Target.MM, DD, v, category=Category.SKILLS, vs_class=Cls.LAN)]),
            Skill("S2", "Roundabout Hit", attacks(2), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.MM, DD, v, category=Category.SKILLS, vs_class=Cls.MM)]),
            Skill("S3", "Fleet", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [Crit(Target.ALL, v)]),
        ]


class WuMing(Hero):
    name, troop = "Wu Ming", Cls.INF
    def build_skills(self):
        return [
            # Shadow's Evasion: "his troops" -> ALL (fix: was Infantry-only).
            Skill("S1", "Shadow's Evasion", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v, category=Category.NORMAL)],
                  note="fix: all troops, not Infantry-only"),
            Skill("S1", "Shadow's Evasion", Passive(), (.06,.12,.18,.24,.30),
                  lambda v: [DamageMod(F, Target.ALL, DT, -v, category=Category.SKILLS)]),
            Skill("S2", "Crescent Uplift", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(F, Target.ALL, DD, v)]),
            Skill("S3", "Elemental Resonance", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(F, Target.ALL, DD, v, category=Category.SKILLS)]),
        ]


class Xura(Hero):
    name, troop = "Xura", Cls.MM
    def build_skills(self):
        return [
            Skill("S1", "Fungal Fog", Passive(), (.04,.08,.12,.16,.20),
                  lambda v: [DamageMod(E, Target.ALL, DD, -v)]),
            Skill("S2", "Piercing Arrow", attacks(2), (.20,.40,.60,.80,1.00),
                  lambda v: [DamageMod(F, Target.MM, DD, v)]),
            Skill("S2", "Piercing Arrow", attacks(2), (.05,.10,.15,.20,.25),
                  lambda v: [DamageMod(E, Target.TARGET, DT, v, duration_turns=1)]),
            Skill("S3", "Unorthodoxy", Passive(), (.03,.06,.09,.12,.15),
                  lambda v: [DamageMod(F, Target.MM, DD, v)]),
            Skill("S3", "Unorthodoxy", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [DamageMod(F, Target.MM, DT, -v)]),
        ]


class Zinman(Hero):
    name, troop = "Zinman", Cls.MM   # canonical
    def build_skills(self):
        return [
            Skill("S1", "Implacable", Passive(), (.02,.04,.06,.08,.10),
                  lambda v: [StatMod(F, Target.ALL, Stat.DEF, v),
                             StatMod(F, Target.ALL, Stat.HP, v)]),
            Skill("S2", "Bastionist", Passive(), None, None,   # non-combat (building/resource)
                  note="building/resource skill; no combat effect"),
            # Positional Battler: Lethality (fix: was coded as Damage Dealt).
            Skill("S3", "Positional Battler", Passive(), (.05,.10,.15,.20,.25),
                  lambda v: [StatMod(F, Target.ALL, Stat.LET, v)],
                  note="fix: Lethality, not Damage Dealt"),
        ]


# --------------------------------------------------------------------------- #
#  Registry
# --------------------------------------------------------------------------- #
ROSTER = {c.name: c for c in Hero.__subclasses__()}

assert len(ROSTER) == 54, f"expected 54 heroes, got {len(ROSTER)}: {sorted(ROSTER)}"

# Class-conditioned triggers ("when [class] attacks" / Strikes semantics): the skill
# fires ONLY on that class's attack events (QA 2026-07-25 — engine supplies
# view.attacker_class). Declared centrally, one auditable place; Gatot/Elif/Magnus
# are set inline (those win). Skills NOT listed are "any attack" (Attacks semantics,
# e.g. Vulcanus S2 "all troops", Gwen "her troops").
_ON_CLASS = {
    "Ahmose":     {"S1": Cls.INF, "S3": Cls.INF},
    "Blanchette": {"S3": Cls.MM},
    "Cara":       {"S3": Cls.MM},
    "Dominic":    {"S2": Cls.LAN},
    "Eleonora":   {"S3": Cls.INF},
    "Fred":       {"S3": Cls.LAN},
    "Freya":      {"S2": Cls.LAN},
    "Gordon":     {"S1": Cls.LAN},
    "Hank":       {"S2": Cls.INF},
    "Ligeia":     {"S2": Cls.MM, "S3": Cls.MM},
    "Lynn":       {"S3": Cls.MM},
    "Nora":       {"S3": Cls.LAN},
    "Rufus":      {"S2": Cls.MM},
    "Sonya":      {"S2": Cls.LAN},
    "Wayne":      {"S2": Cls.MM},
    "Xura":       {"S2": Cls.MM},
}
for _n, _m in _ON_CLASS.items():
    ROSTER[_n].on_class_map = _m

# Guard against troop-class drift: every hero must match the canonical workbook
# (loader.load_hero_roster). QA 2026-07-25 found 15 guessed classes wrong; this
# assertion keeps them correct and fails loudly if any future edit re-introduces one.
try:
    from wos_sim.loader import load_hero_roster as _load_canon
    _canon = _load_canon()
    _CLSMAP = {"Infantry": Cls.INF, "Lancer": Cls.LAN, "Marksman": Cls.MM}
    _drift = {n: (c.troop.value, _canon.get(n).troop_type.value)
              for n, c in ROSTER.items()
              if n in _canon and c.troop != _CLSMAP[_canon.get(n).troop_type.value]}
    assert not _drift, f"troop-class drift vs canonical workbook: {_drift}"
except ImportError:
    pass   # workbook/openpyxl unavailable in this interpreter -> skip the guard


if __name__ == "__main__":
    import random
    from wos_sim.formula_research.hero_kit import BattleView
    print(f"ROSTER: {len(ROSTER)} heroes")
    total_effects = 0
    for name in sorted(ROSTER):
        h = ROSTER[name](level=5)
        for turn in range(1, 13):
            view = BattleView(turn=turn, attack_no=turn,
                              enemy_alive={Cls.LAN: 100, Cls.MM: 50},
                              rng=random.Random(turn))
            total_effects += len(h.resolve(view))
    print(f"OK — all 54 instantiate and resolve 12 turns without error "
          f"({total_effects} effect-intents emitted across the sweep)")


