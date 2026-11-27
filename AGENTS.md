# Minicheme Agent Instructions

Populate the conceptual chemical process dashboard (`process.json`) via `minicheme.py`; follow [`.agents/skills/minicheme/SKILL.md`](.agents/skills/minicheme/SKILL.md).

## Quick Path (Token-Optimized)
1. **Do NOT propose or invent process decisions.** Base every block strictly on user input, `./references/` bibliography, physical properties, and verified heuristics. If required data is missing, call `python minicheme.py block <ID> ...` so the block stays **🔴 Red & Blocked**, then stop.
2. **Complete blocks strictly in Douglas order** (`BP-01` → `BP-02` → `RX-*` → `SP-*` → `HX-*` → `SM-01`): 🔴 Pending → 🔵 Processing (`start`) → 🟢 Solved (`finish`), continuing automatically until all blocks are Green or one hits Red (Blocked).
3. **Do NOT read `resources/heuristics/heuristics.json` directly.** Use `python minicheme.py next -p <folder>` and `python minicheme.py heuristics ...`.
4. **Do NOT edit `process.json` manually.** Every transition goes through `python minicheme.py <command>`.
5. Keep outputs strictly conceptual — no detailed stream balance matrices, piping lists, metallurgy schedules, or simulator convergence guides. Watch the live dashboard with `python minicheme.py serve`.
