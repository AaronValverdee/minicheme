# Process Summary: Conceptual Process Brief for Green MTBE Plant

> **Project**: Conceptual Process Plan for Green MTBE Production from Isobutylene-Rich Naphtha  
> **Workspace**: `Example1/`  
> **Target Capacity**: $10,000\text{ metric tons/year}$ Naphtha ($8,000\text{ operating hr/year}$)  
> **Status**: 🟢 Conceptual Screening Complete & Heuristically Validated

---

## 1. Target & Capacity (`PROC-002`)

* **Operating Mode**: **Continuous** ($1,250\text{ kg/h}$ naphtha; $8,000\text{ hr/year}$).
* **Turndown**: Minimum **50%** utilization ($625\text{ kg/h}$).
* **Product Spec**: MTBE $\ge 99.9\text{ wt}\%$.
* **Primary Chemistry**:
  $$\text{Isobutylene} + \text{Methanol} \xrightleftharpoons[\text{Amberlyst 15}]{\Delta H^\circ = -37.2\text{ kJ/mol}} \text{MTBE}$$
* **Thermodynamic Model**: **NRTL-RK** or **UNIQUAC-RK** (polar MeOH non-ideality, C4/MeOH azeotropes, LLE water wash).

---

## 2. Reaction Basis ({Reactor})

* **Configuration**: Two-stage liquid-phase fixed-bed train with intercooler (R-101 → E-102 → R-102).
* **Catalyst**: Amberlyst 15 (or equivalent) macroporous sulfonic resin, $d_p \approx 0.6\text{–}0.8\text{ mm}$.
* **Window**: $12\text{ barg}$ liquid phase; $50\text{–}75^\circ\text{C}$ (peak $<120^\circ\text{C}$ resin limit); $\text{MeOH}/i\text{-C}_4 = 1.05$.
* **Thermal**: Moderate exotherm, $\Delta T_{\text{ad}} \approx 42.4^\circ\text{C}$; C4 inerts provide heat sink.

---

## 3. Separation Basis ({Separation})

1. **T-201 Debutizer** ($6.5\text{ barg}$): MTBE bottoms $\ge 99.9\text{ wt}\%$; C4 + azeotropic MeOH overhead (CW-condensable).
2. **T-202 Water Wash (LLE)**: Raffinate-II with MeOH $<20\text{ ppm}$.
3. **T-203 MeOH Recovery** ($1.2\text{ barg}$): Recycle MeOH to reactor; closed water loop to T-202.

---

## 4. Energy Basis ({Heat Exchangers})

* **Recovery**: E-101 feed/MTBE economizer; E-203 extract/water economizer ($\approx 20\%$ steam savings).
* **Utilities**: LP steam $3.5\text{ barg}$ ($148^\circ\text{C}$); CW $30^\circ\text{C}$ supply—no refrigeration.
* **$\Delta T_{\min}$**: $10^\circ\text{C}$; reboiler approaches kept $\le 25^\circ\text{C}$ (nucleate boiling).

---

## 5. Next Step

Conceptual framework, chemical data, equipment families, and operating envelopes are established. Proceed to build the rigorous flowsheet in **Aspen Plus**, **Aspen HYSYS**, or **DWSIM**.
