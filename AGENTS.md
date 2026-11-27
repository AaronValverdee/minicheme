# Minicheme Agent Instructions

Plan and execute conceptual chemical process design on `process.json` via `minicheme.py`; follow [`.agents/skills/minicheme/SKILL.md`](.agents/skills/minicheme/SKILL.md).

## Quick Path (Token-Optimized)
1. **Do NOT read `resources/heuristics/heuristics.json` directly.** Use `python minicheme.py next -p <folder>` and `python minicheme.py heuristics ...`.
2. **Do NOT edit `process.json` manually.** Every transition goes through `python minicheme.py <command>`.
3. Start with `python minicheme.py next -p <folder>` to get the active block, upstream decisions, and relevant verified heuristics in one compact call.
4. Keep outputs strictly conceptual (Douglas hierarchy: Basis → Reactor → Separation → Heat Exchangers → Brief) — no detailed stream balance matrices, piping lists, metallurgy schedules, or simulator convergence guides.
5. Watch the live HTML board with `python minicheme.py serve`.
