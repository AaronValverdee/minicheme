# Chemical Substances and Physical Properties

> **Thermodynamic Engine**: Python `chemicals` library (DIPPR / Perry's / NIST) & PubChem PUG REST API.
> **Role in Minicheme**: Conceptual reference for phase equilibria, normal boiling point ordering, and equipment screening.
> **Process context**: Green MTBE from isobutylene-rich naphtha (19 wt% isobutylene) + green methanol; MTBE purity ≥ 99.9 wt%.

---

## 1. Primary Species Property Table

| Substance | Formula | CAS RN | MW (g/mol) | Normal B.P. | M.P. | Liquid Density | Viscosity | $P^{\text{sat}}$ (25°C) | PubChem CID |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Isobutylene** *(Key Reactant)* | `C4H8` | 115-11-7 | 56.11 | -6.9 °C | -140.4 °C | 0.588 g/cm³ (25°C) | 0.16 mPa·s | 3.08 bar | [8255](https://pubchem.ncbi.nlm.nih.gov/compound/8255) |
| **Methanol** *(Green Feed)* | `CH4O` | 67-56-1 | 32.04 | 64.7 °C | -97.8 °C | 0.790 g/cm³ (25°C) | 0.54 mPa·s | 0.169 bar | [887](https://pubchem.ncbi.nlm.nih.gov/compound/887) |
| **MTBE** *(Target Product)* | `C5H12O` | 1634-04-4 | 88.15 | 55.2 °C | -108.6 °C | 0.736 g/cm³ (25°C) | 0.34 mPa·s | 0.33 bar | [15413](https://pubchem.ncbi.nlm.nih.gov/compound/15413) |
| **Water** *(Wash Solvent)* | `H2O` | 7732-18-5 | 18.02 | 100.0 °C | 0.0 °C | 0.997 g/cm³ (25°C) | 0.91 mPa·s | 0.032 bar | [962](https://pubchem.ncbi.nlm.nih.gov/compound/962) |

## 2. Critical Properties

| Substance | Critical Temp ($T_c$) | Critical Press ($P_c$) | Acentric Factor ($\omega$) |
| :--- | :--- | :--- | :--- |
| **Isobutylene** | 144.8 °C | 40.0 bar | 0.197 |
| **Methanol** | 239.9 °C | 81.0 bar | 0.565 |
| **MTBE** | 223.5 °C | 34.1 bar | 0.265 |
| **Water** | 373.9 °C | 220.6 bar | 0.344 |

## 3. Naphtha Battery-Limit Composition (from Basis of Design)

| Compound | Mass % | Role |
| :--- | :--- | :--- |
| Propane | 0.5 | Light inert |
| Propene | 0.5 | Light inert |
| i-Butane | 35 | Major inert diluent / heat sink |
| n-Butane | 10 | Inert |
| 2-Butene | 21 | Inert olefin (non-reactive under MTBE resin conditions) |
| 1-Butene | 11 | Inert olefin |
| **Isobutylene** | **19** | **Reactive olefin** |
| C5+ | 1 | Heavy ends |

Battery limits: Naphtha at **4 barg / 25 °C**; Methanol at **0 barg / 25 °C**.

## 4. Relative Volatility & Separation Ranking

> Sorted by normal boiling point (lightest overhead → heaviest bottoms), with azeotropic correction:

| Component | Normal B.P. (°C) | Role in Debutizer (T-201) |
| :--- | :--- | :--- |
| C3 / C4 hydrocarbons | −47.6 to +3.7 | Distillate (Raffinate precursors) |
| Methanol (azeotropic with C4) | 64.7 (pure) | Travels **overhead** with C4s via min-boiling azeotrope |
| **MTBE** | **55.2** | **Bottoms product (≥ 99.9 wt%)** |
| Water | 100.0 | Extractive wash solvent (T-202 / T-203) |

> [!IMPORTANT]
> **Azeotropic Behavior**: Pure methanol boils above MTBE, but in a C4-rich matrix $\gamma^\infty_{\text{MeOH}} \approx 8\text{–}12$, so residual MeOH forms a **minimum-boiling homogeneous azeotrope** with C4s and leaves in the debutizer overhead—leaving high-purity MTBE as bottoms.

## 5. Recommended Thermodynamic Model

* **Primary Model**: **NRTL-RK** or **UNIQUAC-RK**.
* **Justification**:
  1. Polar methanol hydrogen bonding and strong positive deviations with C4 hydrocarbons (azeotropes).
  2. Liquid–liquid immiscibility for the downstream water wash (LLE partition of MeOH).
  3. Liquid-phase reaction equilibrium requires accurate activity coefficients: $K_a = \frac{a_{\text{MTBE}}}{a_{\text{MeOH}} \cdot a_{i\text{-C4}}}$.
