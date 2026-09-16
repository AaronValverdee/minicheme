# Chemical Substances and Physical Properties

> **Source**: Retrieved automatically via PubChem PUG REST / PUG View APIs with supplementary NIST WebBook and Perry's Chemical Engineers' Handbook thermodynamic benchmarks.
> **Role in Minicheme**: Reference physical properties for stoichiometry, reactor thermal balances, vapor-liquid phase distribution, relative volatility, and pump/compressor sizing.

---

## 1. Physical & Thermodynamic Property Table

| Substance | Formula | MW (g/mol) | Normal B.P. (°C) | M.P. (°C) | Liquid Density (g/cm³) | Liquid Viscosity (mPa·s, 25°C) | Vapor Pressure (bar, 25°C) | PubChem CID |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Propene** | `C3H6` | 42.08 | -47.6 | -185.2 | 0.514 (at 20°C, sat) | 0.08 | 11.50 | [8252](https://pubchem.ncbi.nlm.nih.gov/compound/8252) |
| **Propane** | `C3H8` | 44.10 | -42.1 | -187.7 | 0.493 (at 25°C, sat) | 0.09 | 9.53 | [6334](https://pubchem.ncbi.nlm.nih.gov/compound/6334) |
| **Isobutane** | `C4H10` | 58.12 | -11.7 | -159.6 | 0.551 (at 25°C, sat) | 0.15 | 3.50 | [6360](https://pubchem.ncbi.nlm.nih.gov/compound/6360) |
| **Isobutylene** *(Key Reactant)* | `C4H8` | 56.11 | -6.9 | -140.3 | 0.588 (at 25°C, sat) | 0.16 | 3.08 | [8255](https://pubchem.ncbi.nlm.nih.gov/compound/8255) |
| **1-Butene** | `C4H8` | 56.11 | -6.3 | -185.3 | 0.595 (at 20°C, sat) | 0.17 | 3.00 | [7844](https://pubchem.ncbi.nlm.nih.gov/compound/7844) |
| **n-Butane** | `C4H10` | 58.12 | -0.5 | -138.3 | 0.573 (at 25°C, sat) | 0.16 | 2.43 | [7843](https://pubchem.ncbi.nlm.nih.gov/compound/7843) |
| **trans-2-Butene** | `C4H8` | 56.11 | +0.9 | -105.5 | 0.604 (at 20°C, sat) | 0.18 | 2.15 | [62695](https://pubchem.ncbi.nlm.nih.gov/compound/62695) |
| **cis-2-Butene** | `C4H8` | 56.11 | +3.7 | -138.9 | 0.621 (at 20°C, sat) | 0.20 | 1.84 | [5287584](https://pubchem.ncbi.nlm.nih.gov/compound/5287584) |
| **MTBE** *(Target Product)* | `C5H12O` | 88.15 | +55.2 | -109.0 | 0.740 (at 20°C) | 0.36 | 0.33 | [15413](https://pubchem.ncbi.nlm.nih.gov/compound/15413) |
| **Methanol** *(Green Feed)* | `CH4O` | 32.04 | +64.7 | -97.6 | 0.791 (at 20°C) | 0.54 | 0.17 | [887](https://pubchem.ncbi.nlm.nih.gov/compound/887) |
| **tert-Butyl Alcohol (TBA)** | `C4H10O` | 74.12 | +82.4 | +25.7 | 0.786 (at 26°C) | 4.30 (at 30°C) | 0.056 | [6386](https://pubchem.ncbi.nlm.nih.gov/compound/6386) |
| **Water** *(Wash Solvent)* | `H2O` | 18.015 | +100.0 | 0.0 | 0.997 (at 25°C) | 0.89 | 0.032 | [962](https://pubchem.ncbi.nlm.nih.gov/compound/962) |
| **Diisobutylene (DIB)** | `C8H16` | 112.21 | +101.4 | -93.5 | 0.715 (at 20°C) | 0.58 | 0.059 | [7868](https://pubchem.ncbi.nlm.nih.gov/compound/7868) |

---

## 2. Relative Volatilities & Downstream Separation Rankings

In the Debutizer / MTBE Fractionation column ($T_{\text{avg}} \approx 70-85^\circ\text{C}$, $P = 6.5\text{ barg}$), relative volatilities $\alpha_i$ relative to MTBE ($\alpha_{\text{MTBE}} = 1.00$) govern splitability:

| Component | Normal B.P. (°C) | $\alpha_i$ vs. MTBE (at column cond.) | Separation Role / Column Cut |
| :--- | :--- | :--- | :--- |
| **Propane / Propene** | -42.1 / -47.6 | $> 15.0$ | Light ends, distills overhead instantly |
| **Isobutane** | -11.7 | $7.5 - 8.5$ | Light key distillate (Raffinate C4) |
| **Isobutylene** | -6.9 | $6.8 - 7.6$ | Unreacted light reactant (Distillate) |
| **1-Butene / n-Butane** | -6.3 / -0.5 | $5.5 - 7.0$ | Inert C4 distillate |
| **2-Butenes (cis/trans)**| +0.9 to +3.7 | $4.5 - 5.5$ | Heavy C4 distillate |
| **Methanol (azeotropic)**| +64.7 (pure) | $\sim 5.0 - 6.0$ (in C4 azeotrope) | Forms minimum-boiling azeotrope with C4s; distills overhead |
| **MTBE (Product)** | **+55.2** | **1.00 (Reference)** | **High-purity Bottoms Product ($>99.9\text{ wt}\%$)** |
| **tert-Butyl Alcohol** | +82.4 | $0.35 - 0.45$ | Heavy byproduct, leaves in bottoms trace |
| **Diisobutylene (DIB)** | +101.4 | $0.20 - 0.25$ | Heavy byproduct, leaves in bottoms trace |

> [!IMPORTANT]
> **Azeotropic Behavior Note**: While pure methanol has a higher normal boiling point ($64.7^\circ\text{C}$) than MTBE ($55.2^\circ\text{C}$), methanol forms a **minimum-boiling homogeneous azeotrope** with C4 hydrocarbons (boiling at $\sim 48-50^\circ\text{C}$ under $6-7\text{ bar}$). Consequently, in the Debutizer column, unreacted methanol travels **overhead** with the C4 raffinate, leaving MTBE at the bottom with $>99.9\text{ wt}\%$ purity!

---

## 3. Recommended Thermodynamic Model

* **Primary Model**: **NRTL-RK** (Non-Random Two-Liquid activity coefficient model paired with the Redlich-Kwong equation of state for the vapor phase) or **UNIQUAC-RK**.
* **Justification**:
  1. **Strong Polar Association**: Methanol exhibits self-association via hydrogen bonding.
  2. **Non-Ideality in Hydrocarbon Mixtures**: Mixtures of polar methanol with non-polar C4 alkanes/alkenes exhibit extreme positive deviations from Raoult's law, creating azeotropes.
  3. **Liquid-Liquid Immiscibility (LLE)**: The downstream water wash column requires accurate prediction of mutual hydrocarbon-water liquid immiscibility with quantitative partition coefficients for methanol between aqueous and organic phases ($\beta_{\text{MeOH}} > 500$).
  4. **Reaction Equilibrium**: Liquid-phase chemical equilibrium calculations require accurate activity coefficients ($\gamma_i$) since the equilibrium constant is rigorously defined in activities: $K_a = \frac{a_{\text{MTBE}}}{a_{\text{MeOH}} \cdot a_{i\text{-C4}}} = \frac{x_{\text{MTBE}}}{x_{\text{MeOH}} \cdot x_{i\text{-C4}}} \cdot \frac{\gamma_{\text{MTBE}}}{\gamma_{\text{MeOH}} \cdot \gamma_{i\text{-C4}}}$.
