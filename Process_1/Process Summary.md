# Process Summary: Conceptual Process Brief for Green MTBE Plant

> **Project**: Conceptual Process Plan for Green MTBE Production from Isobutylene-Rich Naphtha  
> **Workspace**: `Process_1/`  
> **Target Capacity**: $10,000\text{ metric tons/year}$ Naphtha ($8,000\text{ operating hr/year}$)  
> **Status**: 🟢 Conceptual Screening Complete & Heuristically Validated

---

## 1. Operating Mode & Capacity Basis (`PROC-002`)

* **Operating Mode**: **Continuous Processing** ($1,250\text{ kg/h}$ feed rate, $8,000\text{ hr/year}$ stream factor).
* **Turndown Flexibility**: Designed for a minimum **$50\%$ turndown coefficient** ($625\text{ kg/h}$).
* **Primary Chemistry**:
  $$\text{Isobutylene} + \text{Methanol} \xrightleftharpoons[\text{Amberlyst 15}]{\Delta H^\circ = -37.2\text{ kJ/mol}} \text{MTBE}$$
* **Thermodynamic Model**: **NRTL-RK** or **UNIQUAC-RK** to account for polar alcohol non-ideality, minimum-boiling C4/methanol azeotropes, and LLE water-wash extraction.

---

## 2. Conceptual Reaction Synthesis ({Reactor})

* **Reactor Configuration (`REACT-003`, `REACT-005`)**: Two-stage fixed-bed catalytic reactor train with intermediate cooling (R-101 primary fixed bed + E-102 intercooler + R-102 finishing bed).
* **Catalyst (`REACT-007`)**: Strongly acidic macroporous cation exchange resin (**Amberlyst 15** beads, $d_p \approx 0.75\text{ mm}$).
* **Operating Regime**: Single liquid phase maintained at **$12.0\text{ barg}$** (safely above bubble point $\sim 7\text{ bar}$).
* **Thermal Management**: Moderate exotherm ($\Delta T_{\text{ad}} \approx 42.4^\circ\text{C}$). Primary inlet at $50^\circ\text{C}$, peak limited to $\le 75^\circ\text{C}$ ($<120^\circ\text{C}$ resin stability limit).
* **Stoichiometry (`PROC-004`)**: $5\%$ stoichiometric excess of methanol ($\text{MeOH}/i\text{-C}_4 = 1.05$) to drive conversion and suppress olefin dimerization.

---

## 3. Conceptual Separation Synthesis ({Separation})

A 3-step sequence exploiting the minimum-boiling C4/methanol azeotrope:
1. **T-201 (Debutizer Column, `DIST-001`, `DIST-002`)**:
   - Operates at **$6.5\text{ barg}$** to permit overhead condensation at $49^\circ\text{C}$ with cooling water (`DIST-003`).
   - Bottoms product recovers MTBE at **$\ge 99.9\text{ wt}\%$ purity** directly.
   - C4 hydrocarbons and unreacted azeotropic methanol distill overhead.
2. **T-202 (Methanol Extraction Water Wash, `EXTR-001`, `EXTR-002`)**:
   - Countercurrent liquid-liquid extraction using demineralized water.
   - Overhead yields spent C4 **Raffinate-II** with $<20\text{ ppm}$ residual methanol.
3. **T-203 (Methanol Recovery Distillation, `DIST-001`, `PROC-007`)**:
   - Operates at **$1.2\text{ barg}$** to separate methanol from water.
   - Distillate recovers green methanol for direct recycle to the reactor; bottoms returns clean water to T-202 in a closed zero-discharge loop.

---

## 4. Conceptual Energy & Utility Synthesis ({Heat Exchangers})

* **Heat Recovery Match (`PROC-010`)**: Hot MTBE bottoms ($138^\circ\text{C}$) preheats cold incoming reactor feed ($25 \to 50^\circ\text{C}$) in E-101, reducing steam heating duty by $>20\%$.
* **Stripped Water Economizer**: Hot water from T-203 bottoms preheats the aqueous extract feed to T-203 in E-203.
* **Utility Selection**:
  - **Heating**: Standard Low-Pressure (LP) saturated steam header at **$3.5\text{ barg}$ ($148^\circ\text{C}$)** (`UTIL-REF-003`). Reboiler approach $\Delta T = 10^\circ\text{C} \le 25^\circ\text{C}$ guarantees stable nucleate boiling (`HEX-007`).
  - **Cooling**: Standard mechanical-draft cooling water supplied at **$30^\circ\text{C}$** (`UTIL-REF-001`). No cryogenic refrigeration required.

---

## 5. Transition to Process Simulation

The conceptual foundation, chemical data, equipment families, and operating envelopes are now established. The engineer can confidently proceed to open **Aspen Plus**, **Aspen HYSYS**, or **DWSIM** to construct the rigorous flowsheet model.
