# Chemical Engineering Heuristics & Property Engine

Central knowledge store queried by `minicheme.py`:
- **`heuristics.json`**: 90 verified chemical engineering heuristics across 13 families (Turton, Seider, Ulrich & Vasudevan, Sinnott & Towler, Walas, Branan).
- **`Rules and intuition for process design.md`**: Conceptual synthesis handbook (Douglas hierarchy, PAR method).
- **`pubchem_fetcher.py`**: Pure-component property engine (`chemicals` library with PubChem REST fallback).

## Agent Token Rule
**Do NOT read `heuristics.json` directly (193 KB).** Query compactly through `minicheme.py`:
```bash
python minicheme.py heuristics --block RX-01 -p <folder>
python minicheme.py heuristics --search "reflux" --limit 6
python minicheme.py heuristics --families
```
