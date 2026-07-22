# Agent instructions (Codex / all agents)

Read `CLAUDE.md` in this folder — it is the canonical agent entry point and applies to ALL agents (Claude Code, Codex, or otherwise), not just Claude.

Summary of the binding points:

1. This repo (`E:\WOS\Battle Simulator`) is the **PROTOTYPE**. `E:\WOS\WOSTests.com` is **PRODUCTION ONLY** and stays empty unless a release passes `PRODUCTION_CRITERIA.md` with Martin's explicit sign-off.
2. Use `CONTEXT_INDEX.md` to find the right doc instead of reading everything — several docs contain known-stale sections, and the index flags them.
3. Commands for running, testing, and deploying are in `TOOLS.md`.
4. Before any engine change: no-fudge rule (`ENGINE_REBUILD/ENGINE_CHANGE_CHECKLIST.md`) + mandatory `py -m wos_sim.backtest` (pass count may only increase).
5. Only touch the engine through `wos_sim/predictor/api.py`.
