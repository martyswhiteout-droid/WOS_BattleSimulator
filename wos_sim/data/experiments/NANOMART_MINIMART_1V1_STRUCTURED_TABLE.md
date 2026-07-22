# NanoMart vs MiniMart 1v1 Structured Corpus

Generated 2026-07-10 from:

- `E:/WOS/WOS_BattleReports_NanoMart_Exp_1.pdf`
- prior NanoMart 1v1 screenshots already captured in `ENGINE_REBUILD`

Important capture limitation: the screenshots show visible `Attack` and `Defense`
rows only. `Lethality` and `Health` below are base troop values unless/until a
full scrolled stat panel is captured.

## Source Discrepancy

Martin's list included `T11 inf vs T6 inf`, but the PDF embedded heading and
page render show `T1 inf vs T6 Inf`. The JSON preserves the PDF heading as
`NanoMart_1v1_T1InfvT6Inf_SeoYoonlvl3_Vulcanus.json`.

## Troop Passive Correction

The cross-class formula reads must include the deterministic T1 troop passives
from `GAME_RULES.md` / `wos_sim.troop_catalog`:

| Source class | Target class | Passive | Formula effect |
| --- | --- | --- | --- |
| Infantry | Lancer | Master Brawler | `Damage Dealt x1.10` |
| Lancer | Marksman | Charge | `Damage Dealt x1.10` |
| Marksman | Infantry | Ranged Strike | `Damage Dealt x1.10` |

These are directional. For example, `Infantry -> Lancer` gets Master Brawler,
but `Lancer -> Infantry` does not get Charge; instead the defending Infantry's
return attack into Lancer gets Master Brawler. Same-class mirror rows are not
affected by these T1 target passives.

## Structured Table

`A/D/L/H*` means visible Attack/Defense bonus applied, with base Lethality/Health
because those panel rows were not visible.

| Report | Heroes | Result | Turns | Attacker base A/D/L/H | Attacker A/D/L/H* | Defender base A/D/L/H | Defender A/D/L/H* |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| T1 Inf vs T1 Inf | Seo-yoon vs Vulcanus | A wins | 264 | T1 Infantry `1/4/1/6` | `1.02/4.01/1/6` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T1 Lancer vs T1 Lancer | Seo-yoon vs Vulcanus | A wins | 30 | T1 Lancer `4/2/5/2` | `4.09/2.00/5/2` | T1 Lancer `4/2/5/2` | `4.08/2/5/2` |
| T1 Lancer vs T1 Infantry | Seo-yoon vs Vulcanus | A loses | 8 | T1 Lancer `4/2/5/2` | `4.09/2.00/5/2` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T1 Marksman vs T1 Infantry | Vacant vs Vulcanus | A wins | 68 | T1 Marksman `5/1/5/1` | `5.11/1.00/5/1` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T1 Marksman vs T1 Lancer | Vacant vs Vulcanus | A loses | 20 | T1 Marksman `5/1/5/1` | `5.11/1.00/5/1` | T1 Lancer `4/2/5/2` | `4.08/2/5/2` |
| T1 Infantry vs T1 Marksman | Seo-yoon vs Vulcanus | A loses | 8 | T1 Infantry `1/4/1/6` | `1.02/4.01/1/6` | T1 Marksman `5/1/5/1` | `30.86/6.15/5/1` |
| T1 Marksman vs T1 Marksman | Vulcanus vs Vulcanus | A loses | 12 | T1 Marksman `5/1/5/1` | `21.81/4.34/5/1` | T1 Marksman `5/1/5/1` | `30.86/6.15/5/1` |
| T1 Lancer vs T1 Marksman | Seo-yoon vs Vulcanus | A loses | 80 | T1 Lancer `4/2/5/2` | `4.09/2.00/5/2` | T1 Marksman `5/1/5/1` | `30.86/6.15/5/1` |
| T2 Infantry vs T2 Infantry | Seo-yoon vs Vulcanus | A wins | 266 | T2 Infantry `2/5/2/7` | `2.04/5.01/2/7` | T2 Infantry `2/5/2/7` | `2.04/5/2/7` |
| T3 Infantry vs T3 Infantry | Seo-yoon vs Vulcanus | A wins | 266 | T3 Infantry `3/6/3/8` | `3.07/6.01/3/8` | T3 Infantry `3/6/3/8` | `3.06/6/3/8` |
| T6 Infantry vs T6 Infantry | Seo-yoon vs Vulcanus | A wins | 264 | T6 Infantry `6/9/6/11` | `6.13/9.02/6/11` | T6 Infantry `6/9/6/11` | `6.12/9/6/11` |
| T2 Infantry vs T1 Infantry | Seo-yoon vs Vulcanus | A wins | 176 | T2 Infantry `2/5/2/7` | `2.04/5.01/2/7` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T3 Infantry vs T1 Infantry | Seo-yoon vs Vulcanus | A wins | 126 | T3 Infantry `3/6/3/8` | `3.07/6.01/3/8` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T4 Infantry vs T1 Infantry | Seo-yoon vs Vulcanus | A wins | 96 | T4 Infantry `4/7/4/9` | `4.09/7.01/4/9` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T5 Infantry vs T1 Infantry | Seo-yoon vs Vulcanus | A wins | 80 | T5 Infantry `5/8/5/10` | `5.11/8.02/5/10` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T6 Infantry vs T1 Infantry | Seo-yoon vs Vulcanus | A wins | 96 | T6 Infantry `6/9/6/11` | `6.13/9.02/6/11` | T1 Infantry `1/4/1/6` | `1.02/4/1/6` |
| T1 Infantry vs T6 Infantry | Seo-yoon vs Vulcanus | A loses | 68 | T1 Infantry `1/4/1/6` | `1.02/4.01/1/6` | T6 Infantry `6/9/6/11` | `6.12/9/6/11` |
| T1 Infantry vs T1 Lancer | Seo-yoon vs Vulcanus | A wins | 80 | T1 Infantry `1/4/1/6` | `1.02/4.01/1/6` | T1 Lancer `4/2/5/2` | `4.08/2/5/2` |

## Formula Read So Far

The current corpus strongly rejects the old direct formula:

`damage ~ Attack * Lethality / (Defense * Health)`

That formula predicts T6 Infantry mirror should resolve far faster than T1
Infantry mirror. The reports show the opposite: T1, T2, T3, and T6 Infantry
mirrors all land at roughly `264-266` turns.

The apparent structure is:

1. The game is using hidden accumulated damage / HP, not immediate fractional
   troop removal.
2. Same-class mirror fights are tier-normalized. Tier scaling mostly cancels
   when both sides use the same class and tier.
3. Class identity matters a lot. T1 Lancer mirror is about `30` turns, while
   T1 Infantry mirror is about `264` turns.
4. Cross-class direction matters. `T1 Inf -> T1 Lancer` and `T1 Lancer -> T1 Inf`
   do not behave symmetrically, partly because the T1 troop passives are
   directional target-class Damage Dealt modifiers.
5. The cleanest first-principles candidate remains a mitigation/durability
   shape near:

`damage_clock ~ Attack / (Attack + target Defense) / (target Defense + target Health)`

This explains the tier-invariant Infantry mirror and the much faster Lancer and
Marksman mirrors better than the old formula. It is not final because the
cross-class rows require the troop-passive multiplier above plus an additional
class/counter/targeting term.

## Next Data Needed

To pin the exact count-scaling law, the next best controlled tests are 2v1 and
1v2 versions of:

- T1 Infantry vs T1 Infantry
- T1 Lancer vs T1 Lancer
- T1 Marksman vs T1 Marksman, using the fairest available clock setup
- T1 Infantry vs T1 Lancer
- T1 Lancer vs T1 Infantry

These will tell us whether damage per turn is linear in troop count, sublinear,
or uses a fixed one-unit duel/frontage rule.
