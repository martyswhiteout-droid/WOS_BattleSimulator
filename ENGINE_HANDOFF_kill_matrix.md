# Engine handoff — per-turn attacker×victim kill matrix

**Requested by:** front-end / app layer
**Owner to implement:** engine agent (owns `wos_sim/pvp_turn_engine.py`)
**Goal:** expose, per turn, how many of each *victim* troop class was killed by each *attacker* troop class — e.g. "Turn 12: my Infantry killed 200 Infantry, 10 Lancer, 10 Marksman."

The data is already computed transiently inside the kill loop; today only the two
**marginals** are kept (kills-per-attacker and casualties-per-victim). This adds the
**joint** matrix and plumbs it to the app timeline. No model/behaviour change — pure
instrumentation. Existing marginals remain the row/column sums of the new matrix
(free validation).

---

## The one place the joint already exists

`_apply_packets_full` (`wos_sim/pvp_turn_engine.py:1324`). Inside the per-packet loop,
at the moment of the kill we have **both** sides of the exchange:

```python
killed = min(st.n, remaining)          # line ~1338
...
casualties[troop] += killed             # `troop`      = VICTIM class
...
src_troop = pkt.source_troop            # `src_troop`  = ATTACKER class
if src_troop is not None:
    kills_by_troop[src_troop] += killed # attacker marginal (already kept)
```

So `(src_troop, troop, killed)` is right there — we just aren't recording the pair.

---

## Minimal change (6 small edits)

### 1. `_apply_packets_full` — accumulate the matrix (`pvp_turn_engine.py:1324`)
```python
kills_by_troop:  dict[TroopType, float]                 = defaultdict(float)
kills_matrix:    dict[tuple[TroopType, TroopType], float] = defaultdict(float)  # (attacker, victim) -> killed
...
    if src_troop is not None:
        kills_by_troop[src_troop] += killed
        kills_matrix[(src_troop, troop)] += killed     # NEW  (troop = victim)
...
return casualties, dict(kills_by_source), dict(kills_by_troop), dict(kills_matrix)  # add 4th
```

### 2. `apply_packets` — keep the thin wrapper's arity (`pvp_turn_engine.py:1355`)
```python
casualties, kills_by_source, _kbt, _kmx = _apply_packets_full(packets, stacks)
return casualties, kills_by_source
```

### 3. `TurnRecord` — one new field (`pvp_turn_engine.py:177`)
```python
kills_matrix: dict = field(default_factory=dict)   # {"attacker": {(atk,vic): n}, "defender": {...}}
```

### 4. Turn loop — capture + store (`pvp_turn_engine.py:1497`)
```python
cas_d, kills_a, kills_a_troop, kmx_a = _apply_packets_full(a_packets, d)
cas_a, kills_d, kills_d_troop, kmx_d = _apply_packets_full(d_packets, a)
...
turn_log.append(TurnRecord(
    t, start, {"attacker": cas_a, "defender": cas_d},
    {"attacker": kills_a, "defender": kills_d},
    turn_attack_events, turn_procs,
    {"attacker": kills_a_troop, "defender": kills_d_troop},
    {"attacker": kmx_a, "defender": kmx_d}))          # NEW
```

### 5. `_compact_timeline` — append two 3×3 matrices (`pvp_turn_engine.py:1634`)
Emit as nested tuples in class order `_TL_CLASSES` (attacker rows, victim cols):
```python
ma = tr.kills_matrix.get("attacker") or {}
md = tr.kills_matrix.get("defender") or {}
a_kmx = tuple(tuple(ma.get((atk, vic), 0.0) for vic in _TL_CLASSES) for atk in _TL_CLASSES)
d_kmx = tuple(tuple(md.get((atk, vic), 0.0) for vic in _TL_CLASSES) for atk in _TL_CLASSES)
out.append((a_alive, d_alive, sum(ca.values()), sum(cd.values()),
            a_lost, d_lost, a_dealt, d_dealt, a_kmx, d_kmx))   # fields 8,9
```
Update the docstring's field list (add `8-9: attacker/defender kill matrix [attacker_class][victim_class]`).

### 6. Predictor plumbing (already reads the tuple)
- `wos_sim/predictor/api.py` → `battle_timeline` (per-battle, exact): read `r[8]/r[9]`
  and add to the returned dict, e.g.
  `"kill_matrix": {"own": [...3×3...], "enemy": [...3×3...]}` (map attacker/defender→own/enemy
  the same way the file already flips `a_*`/`d_*` on `con.own_is_attacker`).
- `wos_sim/predictor/summary.py` → `_battle_timeline` (Average mode): sum the 3×3s across
  sims and divide by n, per turn, same as the other averaged series. Optional — Per-Battle
  mode is enough for v1; Average can ship later.
- `wos_sim/predictor/serialize.py` → pass the field through in `forecast_to_dict`.

---

## Data shape delivered to the front-end

Per turn, per side, a 3×3 in fixed class order `[Infantry, Lancer, Marksman]`:

```
kill_matrix.own[attackerClass][victimClass] = kills
```

Example the app will render (Turn 12, own side):
```
own = [[200, 10, 10],   # Infantry attacker -> 200 Inf, 10 Lan, 10 Mar
       [ 90, 40,  8],   # Lancer   attacker
       [ 70, 30, 55]]   # Marksman attacker
```

## Invariants (please assert in tests)

For each turn and side, the new matrix must reconcile with the existing marginals:
- `sum_v matrix[a][v]  == kills_by_troop[a]`      (row sums = attacker marginal)
- `sum_a matrix[a][v]  == casualties[v]` on the opposing side (col sums = victim casualties)
- `sum_all matrix       == total kills that turn`  (already asserted by `_assert_conservation`)

A cheap `_assert_conservation`-style check on the matrix keeps this honest.

## Notes / gotchas
- `pkt.source_troop` can be `None` for some non-troop sources; those kills already fall
  out of `kills_by_troop` and will likewise be absent from the matrix — the matrix will
  sum to `sum(kills_by_troop.values())`, which may be ≤ total casualties. That's fine and
  consistent with today's attacker marginal; just don't assert matrix-sum == total-casualties.
- Targeting is frontline-ordered (`ORDER`) unless a packet is `backline`, so victim columns
  will skew to Infantry for most attackers and toward backline classes for backline skills —
  expected, not a bug.

## Front-end plan once this lands
Wire into the **Timeline → Per Battle** view (it already has the turn context): a
"Who killed what" block under the per-turn charts — for the slider's battle, a per-turn
(or turn-selected) attacker→victim breakdown. Design preview built in the app style;
horizontal stacked bar per attacker class, segment = victim class, count labels + hover.
Colours (CVD-validated): Infantry `#2a78d6`, Lancer `#1baf7a`, Marksman `#eda100`.
