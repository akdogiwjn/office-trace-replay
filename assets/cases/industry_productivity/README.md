# Industry productivity — staged input

Dataset ID: `industry_productivity`. This input is intended to take the place of
the small Census M3 `manufacturing` case in future hotspot comparisons. Existing
Manufacturing inputs, recipes, traces and historical analysis remain intact.

The original workbook is stored at
`source/datasets/xlsx/industry_productivity/input/labor-productivity-detailed-industries.xlsx`.
It was moved from the owner-supplied local file without rewriting any workbook
content. Its SHA256 is
`9c1213923977e6dcefd20b6185537434e9057428cb9a16b3329a8ccb4dd117dd`.

BLS [Tables](https://www.bls.gov/productivity/tables/home.htm) links
[Labor productivity by detailed industries](https://www.bls.gov/productivity/tables/labor-productivity-detailed-industries.xlsx)
as an XLSX release dated September 24, 2026. The workbook's release statement
agrees. The owner explicitly confirmed downloading this exact supplied file from
the BLS official website, so it is accepted as an official-source input. The
historical HTTP 403 independent-download attempt is retained as a provenance
note and does not block onboarding; no independent byte comparison is claimed.
Acquisition and verification details are recorded
in `source/datasets/xlsx/industry_productivity/provenance.json`.

The complete input is 22,639,809 bytes and contains three worksheets:

| Sheet | Rows | Columns | Serialized populated cells |
|---|---:|---:|---:|
| Annual | 15,183 | 46 | 698,328 |
| MachineReadable | 566,659 | 9 | 5,099,931 |
| ReadMe | 14 | 2 | 15 |

There are 5,798,274 populated cells, no formulas or charts, five cell styles,
no merged ranges, and shared strings. Full counts and their definitions are
in `complexity.json` beside the provenance file.

The input covers multiple industries. Manufacturing is a business focus within
the complete workbook. Annual year headers span 1987–2025; availability varies
by series. Manufacturing rows include labor productivity, real sectoral output,
hours worked, employment and labor compensation, alongside other measures.
`content-summary.json` records the inspected sectors, measures and units.

Annual and MachineReadable present wide and long views of published statistical
series. Their rows must not be summed as independent firm or worker records.
There is no synthetic row expansion.

Task manifest and semantic expectations are in the sibling `datasets/` tree.
A real Agent run, accepted canonical trace, and derived P01→P04 replay recipe
are registered under `compatibility/cases/industry_productivity/`. The accepted
run used Python 3.12.3 and the existing runtime image; it did not rebuild the
image or collect performance data. Its trace was adapted into the current
deterministic replay contract, with the Agent's extra full source audit and
duplicate verifier calls retained in the canonical trace but excluded from the
timed recipe. The exact parent run and artifact hashes are recorded in
`compatibility/cases/industry_productivity/canonical/parent-run.json`.

Future comparison selection is read by the hotspot analysis entry point from
`analysis/hotspot-comparison/config/next-comparison-suite.json`. It uses TLC,
Retail, HR and this dataset for XLSX comparisons. Manufacturing remains
registered and runnable as historical evidence; the historical run plan and
reports retain their original meaning. This onboarding does not add a new
performance run or establish performance representativeness.
