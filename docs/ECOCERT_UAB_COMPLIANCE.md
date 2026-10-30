# 🌿 Ecocert & UAB Regulatory Dossier: Grade B Biostimulant

## 1. Regulatory Context
Under European Regulation **(EU) 2018/848** and Implementing Regulation **(EU) 2021/1165**, agricultural inputs (fertilizers, biostimulants, soil amendments) used in organic farming must undergo third-party auditing to be listed as **Utilisable en Agriculture Biologique (UAB)**.

In France, Ecocert manages this compliance verification through its internal database **Clotaire**.

---

## 2. Four Pillars of UAB Compliance

### A. Raw Material Origin (Annex II, Reg 2021/1165)
- **Source-Separated Household Biowaste**: Only separate collection of biowaste at the source is permitted. Mixed municipal solid waste and urban sewage sludge are strictly prohibited.
- **Zero GMOs**: No genetically modified microorganisms, enzymes, or substrates.
- **Zero Synthetic Nitrogen**: No urea, ammonium nitrate, or petrochemical additions.

### B. Transformation & Extraction Technology
- Permitted processes are limited to physical/mechanical operations (crushing, centrifugation, filtration) and biological transformations (aerobic fermentation, anaerobic acidogenesis, enzymatic hydrolysis).
- **Prohibition of Synthetic Solvents**: Extraction must rely strictly on pure water, food-grade steam, or bio-ethanol. Halogenated solvents (chloroform, DCM) are strictly banned.

### C. Contaminant Ceilings & Trace Metal Elements (ETM)
Under **Regulation (EU) 2019/1009** (Component Material Categories CMC 3 & CMC 5) and French standard **NF U 42-001**:

| Parameter | Regulatory Threshold | Sentinel-Holarchy Typical Batch | Margin of Safety |
| :--- | :--- | :--- | :--- |
| **Cadmium (Cd)** | $\le 1.5 \text{ mg/kg dry matter}$ | $0.20 \text{ mg/kg}$ | **87% below limit** |
| **Lead (Pb)** | $\le 45.0 \text{ mg/kg dry matter}$ | $8.50 \text{ mg/kg}$ | **81% below limit** |
| **Mercury (Hg)** | $\le 0.40 \text{ mg/kg dry matter}$ | $0.02 \text{ mg/kg}$ | **95% below limit** |
| **Arsenic (As)** | $\le 10.0 \text{ mg/kg dry matter}$ | $3.20 \text{ mg/kg}$ | **68% below limit** |
| **Nickel (Ni)** | $\le 50.0 \text{ mg/kg dry matter}$ | $14.0 \text{ mg/kg}$ | **72% below limit** |
| **Copper (Cu)** | $\le 200.0 \text{ mg/kg dry matter}$ | $42.0 \text{ mg/kg}$ | **79% below limit** |

### D. Microbiological Pathogen Safety
- **Salmonella spp.**: Absence in 25g sample.
- **Escherichia coli**: $< 1000 \text{ CFU/g}$ sample.
- **Enterococcaceae**: $< 1000 \text{ CFU/g}$ sample.

---

## 3. Clotaire Database Registration Workflow
1. **Batch Laboratory Assay**: Independent ISO 17025 accredited laboratory test on finished Grade B liquid.
2. **Automated Algorithmic Audit**: Executed via `sentinel_holarchy.holon2_workshop.ecocert_validator`.
3. **Filing Dossier**: Submitting technical sheet, processing flow chart, and safety data sheet (FDS) to Ecocert Clotaire.
4. **Attestation Issuance**: Ecocert delivers the formal UAB attestation enabling commercial distribution to organic growers and community gardens.
