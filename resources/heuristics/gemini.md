# Chemical Engineering Heuristics & Knowledge Retrieval Skill

> **Directory Role**: Central Skill & Knowledge Retrieval Engine for Chemical Engineering Process Design.
> 
> **The Golden Heuristic**:  
> *"Never use a heuristic rule unless you understand where it came from and how it was derived."*  
> — *Turton et al. (adapted from B. V. Koen)*

---

## 1. Directory Purpose & Architecture

This directory operates as a **self-contained, pre-compiled skill and heuristics retrieval hub** for conceptual process design, equipment screening, and shortcut chemical engineering calculations.

All empirical engineering wisdom from foundational textbooks and industrial references (Turton et al., Sinnott & Towler, Seider et al., Ulrich & Vasudevan, Walas, and Branan) has been distilled, validated, cross-referenced, and cataloged into ready-to-query assets. The directory is completely self-contained and does not rely on external raw documents.

### Core Assets in this Directory:

1. **`heuristics.json` (Primary Retrieval Target)**:
   - Contains 90 verified, deduplicated chemical engineering heuristics organized across 13 families.
   - Each rule contains: `id`, `family`, `subfamily_or_equipment`, `rule`, `explanation_and_derivation`, `quantitative_guidelines`, `conditions_and_limitations`, `variations_and_discrepancies`, `references`, and `tags`.
   - **How to use**: Query directly by `family`, equipment type, tag, or ID (`PROC-xxx`, `REACT-xxx`, `DIST-xxx`, `HEX-xxx`, etc.) to retrieve exact numerical criteria and justifications.

2. **`Rules and intuition for process design.md` (Conceptual Guide & Mental Models)**:
   - In-depth synthesis of process synthesis strategy and chemical engineering intuition.
   - Covers Douglas hierarchy (Levels 1–5), the PAR method (Predict, Authenticate, Re-evaluate), safety, heuristic boundaries, and trade-off logic.
   - **How to use**: Consult for high-level process reasoning, qualitative trade-off justifications, or conceptual explanations.

3. **`pubchem_fetcher.py` (Automated Property Retrieval Tool)**:
   - Fast, non-blocking retrieval script powered by the Python `chemicals` library (DIPPR, Perry's Handbook, NIST) with automatic PubChem API fallback.
   - Fetches formula, CAS, molecular weight, boiling/melting points, critical properties ($T_c, P_c, \omega$), liquid densities, viscosities, vapor pressures, and relative volatility rankings directly into markdown format.
   - **How to use**: Execute via terminal for reacting species and solvents:
     ```powershell
     python pubchem_fetcher.py Compound1 Compound2 ... --out "Chemical substances.md"
     ```

---

## 2. Agent Retrieval Protocol & Operating Rules

> [!IMPORTANT]
> **SELF-CONTAINED KNOWLEDGE REPOSITORY**:
> All literature references (Turton, Sinnott & Towler, Seider, Ulrich & Vasudevan, Walas, Branan) have been pre-compiled and verified directly within `heuristics.json` and `Rules and intuition for process design.md`.
> Agents should use `heuristics.json` as the single authoritative source of truth for heuristic parameters, equations, and sizing rules.

### ✅ Standard Retrieval Workflow for Agents:
1. **Targeted Heuristic Lookup**: When evaluating process flowsheets, reactors, separation columns, heat integration, or utility systems, search `heuristics.json` for the relevant family:
   - `process_synthesis_and_strategy`: Flowsheet hierarchy, batch vs continuous, purges, recycles, pinch analysis.
   - `reactors_and_kinetics`: Reactor type selection, thermal control, catalyst sizing, agitation.
   - `separations_distillation_and_absorption`: Column sequencing, reflux ratio, operating pressure, tray vs packing, HETP.
   - `separations_liquid_liquid_extraction`: Solvent selection, dispersed phase, stage counts.
   - `separations_solids_and_slurries`: Crystallizers, evaporators, filters, centrifuges, dryers, size reduction.
   - `heat_transfer_exchangers_and_furnaces`: Exchanger allocation, LMTD, approach temperatures, typical $U$ values, reboiler $\Delta T \le 45^\circ\text{F}$, fired heaters.
   - `cooling_towers_and_refrigeration`: Utility levels, cooling tower water, refrigerants.
   - `fluid_handling_pumps_and_piping`: Pump selection, hydraulic power, line velocities.
   - `gas_compression_and_vacuum`: Compressor staging, vacuum equipment, air inleakage equation.
   - `pressure_vessels_and_storage`: Vessel orientation ($L/D$), holdup times, design margins.
   - `mixing_and_agitation`: Agitator power, impeller types, tank geometry.
   - `materials_of_construction`: MOC selection, temperature/chemical limits, corrosion allowances.
   - `physical_properties_and_shortcuts`: Order-of-magnitude physical properties and estimation shortcuts.
2. **Respect Limitations & Boundaries**: Always examine `conditions_and_limitations` in `heuristics.json` to verify that process conditions (extreme temperatures, pressures, or unusual kinetics) do not violate the empirical foundation of the rule.
3. **Compound Data**: Use `pubchem_fetcher.py` to retrieve verified compound properties early in the conceptual stage.