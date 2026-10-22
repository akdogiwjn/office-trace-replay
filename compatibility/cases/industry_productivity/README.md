# Industry productivity compatibility case

This case stages the complete BLS labor productivity workbook and runs a
canonicalized four-step replay derived from one accepted real Agent execution.
The source workbook is unchanged (SHA256
`9c1213923977e6dcefd20b6185537434e9057428cb9a16b3329a8ccb4dd117dd`); Annual,
MachineReadable and ReadMe are retained. Manufacturing is the business focus,
while the source covers multiple industries. The Annual wide view and
MachineReadable long view are alternate representations and are never summed
together.

The Agent execution is `xlsx-industry_productivity-20261019T043257Z-06a71220`.
Its canonical trace SHA256 is
`b3393b732fc10ead2557db2230d2cff231d1a297d17aff3d4db665e6926db8e1`. The run
passed the loop verifier, independent verifier, context audit and baseline
acceptance. The canonical trace and its content-addressed objects are stored
under `canonical/` and are validated against the parent run inventory.

The recipe preserves the unified P01→P02→P03→P04 boundary and uses the original
`recalc.py`. It runs one loop verifier; the strict independent verifier is run
once after the loop. The Agent trace contains extra source-preservation audit
work and duplicate manual verifier calls. Those remain trace evidence but are
not replayed in the timed workflow. The recipe and this adaptation are bound to
the parent run, canonical trace, helper, inputs and verifier contract.

The dataset is selected for future hotspot analysis in
`analysis/hotspot-comparison/config/next-comparison-suite.json`. Manufacturing
and all historical Manufacturing artifacts remain available. No performance
sample was collected for this case during onboarding.
