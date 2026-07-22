# Other Complete Type 1 Controls

These seven controlled reports have enough source stats to remain in the exact-fit pool. They are separate from Far Seer and from Alpaca/Colonel Mueller FC1 reports.

`A/D/L/H` means Attack, Defense, Lethality, Health percentage bonus.

| Source and deployed matchup | Attacker panel A/D/L/H % | Defender panel A/D/L/H % | Hero and passive inputs |
|---|---|---|---|
| `exp0_beast.json`: Colonel Mueller, 20,000 T1 Infantry vs Lv18 Titan Roc | I 181.3/153.0/112.0/108.7; L 184.6/150.7/105.3/102.6; M 185.6/155.7/121.2/118.6 | Titan Roc: flat +57.0% to every stat; 2,595 I, 3,025 L, 3,025 M at Lv6 | No hero. Beast Marksman Ranged Strike +10% DD vs attacker Infantry; attacker Infantry Master Brawler +10% DD vs beast Lancers. |
| `exp1_mirror_20k.json`: 20,000 T1 Infantry vs 20,000 T1 Infantry | I 176.2/169.0/109.7/109.3; L 182.7/163.0/135.5/134.1; M 176.2/166.0/129.1/129.0 | I 174.3/153.0/112.0/108.7; L 178.6/150.7/105.3/102.6; M 178.6/155.7/121.2/118.6 | No heroes or procs. No active class-counter passive in Infantry vs Infantry. |
| `exp2_mirror_2k.json`: 2,000 T1 Infantry vs 2,000 T1 Infantry | Same captured panel as exp1 | Same captured panel as exp1 | No heroes or procs. No active class-counter passive. |
| `exp4_inf_vs_lancer.json`: 10,000 T6 Infantry vs 10,000 T6 Lancer | I 199.2/192.0/119.7/119.3; L 205.7/186.0/145.5/144.1; M 199.2/189.0/139.1/139.0 | I 189.1/167.2/122.0/118.7; L 189.1/160.7/115.3/112.6; M 189.1/165.7/131.2/128.6 | No hero skills or procs. Attacker Infantry Master Brawler +10% DD vs defender Lancers. |
| `exp4b_inf_vs_lancer_mueller_updated.json`: 10,000 T6 Infantry vs 10,000 T6 Lancer | I 199.2/192.0/119.7/119.3; L 205.7/186.0/145.5/144.1; M 199.2/189.0/139.1/139.0 | I 194.1/172.2/122.0/118.7; L 194.1/165.7/115.3/112.6; M 194.1/170.7/131.2/128.6 | No hero skill procs. Attacker Infantry Master Brawler +10% DD vs defender Lancers. |
| `exp4c_inf_vs_lancer_gordon.json`: 10,000 T6 Infantry vs 10,000 T6 Lancer | I 199.2/192.0/119.7/119.3; L 457.3/437.6/145.5/144.1; M 199.2/189.0/139.1/139.0 | I 194.1/172.2/122.0/118.7; L 194.1/165.7/115.3/112.6; M 194.1/170.7/131.2/128.6 | Gordon S2 L2: all enemy troops Damage Dealt -12% for one turn on turns 3, 6, 9, ... . Gordon S3 is inert for this pure Infantry-vs-Lancer matchup. Attacker Master Brawler +10% DD vs defender Lancers. |
| `exp5_inf_vs_marksman.json`: 10,000 T6 Infantry vs 10,000 T6 Marksman | I 199.2/192.0/119.7/119.3; L 205.7/186.0/145.5/144.1; M 199.2/189.0/139.1/139.0 | I 189.1/167.2/122.0/118.7; L 189.1/165.7/115.3/112.6; M 189.1/165.7/131.2/128.6 | No hero skills or procs. Attacker Master Brawler is inactive; defender Ranged Strike +10% DD vs attacker Infantry is active. |

Source fixtures: [exp0](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/exp0_beast.json), [exp1](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/exp1_mirror_20k.json), [exp2](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/exp2_mirror_2k.json), [exp4](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/exp4_inf_vs_lancer.json), [exp4b](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/exp4b_inf_vs_lancer_mueller_updated.json), [exp4c](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/exp4c_inf_vs_lancer_gordon.json), and [exp5](E:/WOS/Battle%20Simulator/wos_sim/data/experiments/exp5_inf_vs_marksman.json).
