# DocOps synthetic scale variants (24-variant unified package)

Manually labelled **synthetic scale variants** of the frozen DocOps tasks. Two
variants (small/large) per parent task so all twelve frozen tasks have a small
and a large scale. **Nothing here is a historical benchmark task, and no parent
score is inherited as an acceptance result.**

All new code, data and configuration lives under `docops/scaling/`. The frozen
official payload (`docops/payload/`, twelve tasks) is never modified; only
`docops/replay.py` received the minimal public-entry wiring described below.

## Round 3 (this round)

- Eight new parents added: Word `001` (controlled document release) and `009`
  (incident manual), Excel `013` (bid evaluation) and `016` (forecast cascade),
  PPT `026` (climate disclosure) and `029` (QBR release), PDF `031` (public
  hearing packet) and `pdfwf005` (closeout binder), each with two scale
  variants.
- Unified package `docops/scaling/payload-all/` = existing eight variants
  (014×2, 021×2, 003×2, 037×2, carried byte-identically) + new sixteen
  variants; `catalog.json`/`payload-index.json`/`recipe.json`/`manifest.json`
  are consistent with the actual task directories (24 tasks, 416 files).
- Dispatch in `prepare.py` is now by parent task (`PARENT_CONFIG`), so 013 never
  reuses 014's scripts and 001 never reuses 003's.
- Each new case has its own `synth.py`, independent `expected.py`,
  `scripts/build_*.py`, `scripts/validate_*.py` and `tests/test_scaling_*.py`.
- Sixteen new variants each had one real functional replay (fresh offline
  retained container, per-loop business validation, PDF conversion, rendering
  and checks) plus an independent read-only re-check; evidence in
  `results/docops/scaling-all-functional-20261106T041702Z-fa404f12/`.
- New unified image `docops-replay:openeuler-scaled` based on
  `docops-replay:openeuler-unified-candidate-04`
  (`sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164`),
  containing the official twelve-task payload and the 24-variant scaling
  payload; install-state acceptance (network=none, no source mounts) passed.
  Build record: `docops/docker/records/20261106T051308Z-scaled-416cc456/`.
- Summary: `docops/scaling/round3-delivery.md`.

## Round 3 audit fix (R1-R5)

Audit findings in `analysis/docops/processed/scaling-round3-review-20261106/` were
fixed for the affected six variants:

- R1/R2: 016 validator now verifies every model/Demand-Raw/exception/KPI/four-
  period-chart cache and value; chart returns to the four-period aggregate and
  Exception Review carries the complete default-scenario breach list (with a
  Unit column); Base/Stress scenario cascade re-verifies full values on copies.
- R3: 009 adds a private TOC-update step that measures real section pages from
  a LibreOffice layout pass, bakes them into the delivered DOCX TOC cache and
  re-verifies stability; the validator independently re-renders and checks all
  TOC entries.
- R4: 029 restores the frozen parent's eight slide types (title, agenda,
  market_context, kpi, risks, mitigation, decision, appendix) parameterized per
  unit; locked legal page preserved.
- R5: `analysis/docops/pilot.py` gained explicit `--image`/`--expected-image-id`
  and `--installed-payload` selection (immutable-ID verification, container-path
  payload), keeping the default current-image.json behaviour.

Fixed image: `docops-replay:openeuler-scaled-fixed`
(`sha256:fb037c236fefa455f63c3a22ac957ad24928a5494cddc4675abb66a1df0de089`),
built from candidate-04 with the updated payload-all. The six affected variants
were re-verified on that image with its installed payload. Details:
`docops/scaling/round3-fix-delivery.md` and
`results/docops/scaling-fixed-functional-20261106T065416Z-cd25a37f/`.



## Layout

```
docops/scaling/
  README.md
  prepare.py            # scheduler: synthesize variants, assemble payload + index
  cases/
    common.py           # variant registry + shared hashing/zip helpers
    014/                # Excel case (independent code)
      synth.py          # raw intake workbook generator (deterministic)
      expected.py       # independent oracle (eligible/priority/status in Python)
      scripts/
        build_disaster_release_variant.py          # parameterized builder
        finalize_disaster_release_variant_ooxml.py  # OOXML repair (parent parity)
        validate_disaster_release_variant.py        # dynamic validator vs expected.json
    021/                # PPTX case (independent code)
      synth.py          # regions.json + messy internal source deck generator
      expected.py       # per-region page/oracle derivation
      scripts/
        build_public_shelter_briefing_variant.py    # per-region 8-page builder
        validate_public_shelter_briefing_variant.py # dynamic per-slide validator
        make_contact_sheets.py                      # per-region montage grouping
        make_qa_fonts.py                            # frozen parent helper (copied)
    003/                # Word case (second round, independent code)
      synth.py          # units.json + multi-unit source DOCX (comments/tracked/bookmarks)
      expected.py       # independent oracle (headings/tables/per-unit facts)
      scripts/
        build_public_packet_variant.py    # parameterized builder (parent stage order)
        validate_public_packet_variant.py # dynamic validator vs expected.json
    037/                # PDF case (second round, independent code)
      synth.py          # notices.json + small unread seed PDF artifact
      expected.py       # independent oracle (pages/bookmarks/orientation/facts)
      scripts/
        build_bus_detour_packet_variant.py    # data-driven ReportLab builder
        validate_bus_detour_packet_variant.py # dynamic validator vs expected.json
  tests/                # small directed checks (tiny fixtures only)
  staging/              # round-1 prep artifacts: manifest.json, raw_records snapshots
  payload/              # round-1 scaling payload (kind=scaling, 4 tasks)
  staging-word-pdf/     # round-2 prep artifacts: manifest.json, raw_records snapshots
  payload-word-pdf/     # round-2 scaling payload (kind=scaling, 4 Word/PDF tasks)
```

## Variants

| task | parent | scale | output | seed |
|------|--------|-------|--------|------|
| `014-n1000`  | 014 | 1,000 deduped applications  | 1 xlsx       | 2026110501 |
| `014-n10000` | 014 | 10,000 deduped applications | 1 xlsx       | 2026110502 |
| `021-g5`     | 021 | 5 regions                 | 5 x 8 = 40 slides | 2026110503 |
| `021-g10`    | 021 | 10 regions                | 10 x 8 = 80 slides | 2026110504 |
| `003-u100`   | 003 | 100 business units (claims) | 1 docx, 103 public tables, real pages by layout | 2026110509 |
| `003-u500`   | 003 | 500 business units (claims) | 1 docx, 503 public tables, real pages by layout | 2026110510 |
| `037-u5`     | 037 | 5 notice groups           | 5 x 5 = 25 pages  | 2026110507 |
| `037-u20`    | 037 | 20 notice groups          | 20 x 5 = 100 pages | 2026110508 |

Round-1 scale is defined by the number of **valid applications after
deduplication** (014) or by the **region count** driving `8 * regions` output
pages (021). Round-2 Word scale is defined by the number of **business units
(claims)** that pass through the whole frozen 003 pipeline (tracked changes,
comments, metadata, corrections, working-content redaction, per-unit public
rebuild, OOXML safety pass, audit and render) and appear in the final packet.
Round-2 PDF scale is defined by the number of **frozen structured notice
groups** in `notices.json` that drive actual ReportLab page construction (5
pages per group; pages are never duplicated from a 5-page base).

Exact byte sizes, hashes, structure counts and branch coverage are recorded in
each variant's `task_metadata.json` (`scale_metadata`) and in the staging
`manifest.json` for each round.

## Generation

Round-1 default (unchanged):

```bash
/opt/docops/venv/bin/python3 docops/scaling/prepare.py --payload-out docops/scaling/payload
```

Round-2 is generated **only when the four Word/PDF variants are selected
explicitly** (the default `--variants` still selects the four 014/021 variants
and the round-1 `payload/` is never overwritten):

```bash
SCALING_STAGING=docops/scaling/staging-word-pdf \
/opt/docops/venv/bin/python3 docops/scaling/prepare.py build \
  --payload-out docops/scaling/payload-word-pdf \
  --variants 003-u100 003-u500 037-u5 037-u20
```

`prepare.py` only synthesizes inputs, prepared materials, frozen expected
oracles, recipes, commands and the payload index. It never runs a workload and
never touches the frozen official payload. Generation is byte-deterministic
(same seed/params -> identical payload; verified by rebuilding twice and
diffing). It finishes by running the existing static `validate_payload` from
`docops/compile.py`; a tampered/missing file is rejected before any replay.

## What the variants do differently from their parents

014:
- Raw intake retains the original H-101..H-112 seed rows (so the original
  H-104 / H-109 / H-112 corrections and the H-107 duplicate example are
  preserved), plus coverage anchors and deterministic extra rows.
- Controlled duplicates (older and newer inspection dates) test the
  "dedup keeps the latest inspection record" rule; rows are shuffled.
- Every fixed range in the parent builder became data-driven: register rows,
  tables, auto-filters, conditional-format ranges, county-rollup and dashboard
  formulas, appeal queue and currency ranges all scale to the actual count.
- The oracle (`expected.json`) is generated once at prepare time by an
  independent Python implementation; the builder only writes Excel formula
  strings, so oracle and builder cannot share the same computation bug. The
  validator compares every row/aggregate against the frozen oracle and never
  regenerates it.
- The parent's print-area/data-validation ranges did not exist in the frozen
  recipe, so there was no frozen fixed range of those kinds to scale; none were
  invented, to keep the measurement footprint unchanged.

021:
- The builder now reads `regions.json` (prepared material) and iterates
  regions, producing the same eight public slide types per region. Output size
  is therefore driven by input scale, not by appending unprocessed pages.
- Every region has distinct facts (shelter count, accessible count, hotline,
  website, email, transit services) with `accessible_count <= shelter_count`.
- The render step groups rendered pages **by region** (8 pages per contact
  sheet) and sorts filenames **numerically** (zero-padded names included)
  instead of the parent's fixed `slide-{1..8}.jpg` brace expansion.
- Validation covers all pages: per-region titles/facts/links, alt text, notes,
  style, banned terms; the fixed "exactly eight pages" assertion is replaced
  by dynamic totals from `expected.json`.

## What the Word 003 variants do differently from their parent

- The source DOCX contains N business units. Each unit has a unique id
  (`CLM-001`..`CLM-0NN`), a working table, its own tracked insertion/deletion
  pair(s), a comment, a bookmark and private working values (claimant, address,
  phone, note). OOXML comment/bookmark/del/ins ids are allocated in distinct
  ranges and python-docx emits valid comment relationships, so no dangling
  relationship or duplicate id is produced.
- The parent's stage order and tools are unchanged (1 resolve tracked changes ->
  2 remove comments -> 3 clean metadata -> 4 correction memo -> 5 redact working
  content -> 6 rebuild public packet -> final OOXML safety pass). Only stage 4
  and stage 6 are parameterized:
  - stage 4 derives the correction memo from frozen `units.json` (global facts
    plus every unit's corrected amount/status); the per-unit wrong values are
    unique across the document so replacement keys are unambiguous;
  - stage 6 rebuilds one determination table per unit plus the aggregate
    determination/category/checklist tables, so the final packet and the real
    LibreOffice render scale with the unit count (the source is not "big but the
    output is one fixed copy").
- The independent oracle (`expected.json`) is generated at prepare time and
  never regenerated in the loop. Document-level controls (margins, footer, core
  properties, title/heading style, page breaks, table header fill) are checked
  once; per-unit facts are checked per unit against their own section. Page
  count is decided by real LibreOffice layout and is never forged.
- Large-count scaling (u100/u500): the generator widens the uniqueness pools
  without changing business semantics — draft wrong amounts are 4-digit values
  in `[6500, 9999]` (above the $650 cap), corrected right amounts are unique
  3-digit values in `[100, 649]` (500 excluded), so no corrected value is a
  substring of any wrong value and correction keys cannot cross-match; wrong
  statuses get a unique qualifier beyond the first 20; names/addresses/phones
  are unique. Expected output is `N + 3` tables (u100 -> 103, u500 -> 503). The
  validator builds a one-time heading->unit index so matching is O(1) per
  heading instead of scanning all N units per heading; matching semantics are
  unchanged (exact heading equality).

## What the PDF 037 variants do differently from their parent

- The parent builder does not repair the seed PDF page by page; it generates a
  fresh ReportLab packet. This variant therefore defines scale with a frozen
  structured declaration (`notices.json`): every notice group carries its route,
  dates, stops, timeline, checklist and corrected facts.
- The builder iterates every group and actually calls the five page-drawing
  functions per group (cover, corrected summary, stop/shuttle matrix, rider
  timeline, release checklist), sets the correct portrait/landscape page size,
  computes `PAGE x OF total` footers and pypdf bookmarks over all groups, then
  renders PNG at 150 DPI. Pages are never duplicated from a 5-page base.
- The synthetic input PDF is an artifact only: like the frozen parent input, the
  builder does not read it for content. The task metadata records this scale
  definition explicitly; do not read the seed PDF page count as the scale.
- The dynamic validator covers every group (titles, business facts, stop ids,
  bookmarks and page targets, orientation, required/forbidden content). Forbidden
  matching is **token-boundary aware** so a legal id/date/count that merely
  contains an old forbidden word as a substring (`17 stops` vs `7 stops`,
  `Route 210` vs `Route 21`, `2026-10-130` vs `2026-10-13`) is not a false
  positive. Legal stop counts exclude 7 and legal October dates exclude 13/27 so
  the corrected content can never collide with the frozen draft errors.

## Public replay entry wiring

`docops/replay.py` gained a payload-kind aware environment check:

- Official payload (catalog has no `kind` or `kind == "official"`): the exact
  previous "twelve installed tasks" constraint is preserved.
- Scaling payload (catalog `kind: "scaling"` with the declared task set): the
  task count check uses the declared count. `list`, `validate-only` and `run`
  work unchanged; task IDs, workspace seeds and results paths are distinct per
  variant. Both round-1 `payload/` (4 tasks) and round-2 `payload-word-pdf/`
  (4 tasks) are plain `scaling` payloads and need no extra wiring.

All other assumptions (preparation, font environment setup, workspace reset,
archiving, result paths) already keyed off the per-task recipe, so no further
changes were needed.

## Measurement boundary

- OUT of ROI (prepare time, never re-run in the loop): synthesis, prepared
  materials, full input hashing, expected-oracle generation, payload assembly.
- IN ROI (unchanged replay steps): build, original-style validation, PDF
  conversion, page rendering. For Word: the per-unit public rebuild and render.
  For PDF: the data-driven ReportLab construction, pypdf finalization and 150
  DPI PNG rendering.
- The loop never re-synthesizes data and never regenerates the oracle.

## PPT experiment scope (explicit)

The scaled 021 builder reads `regions.json` and iterates regions, producing 40
or 80 pages; it does not edit the synthetic source PPTX. This variant therefore
measures **per-region document generation, validation, conversion and rendering
scale** (regions -> 8 public slides each). It does NOT measure a larger
source-PPT parse or cleanup cost. Always distinguish:
input-PPTX page count (small, synthetic) vs region count (5/10) vs expected
output pages (40/80). Do not read the results as evidence about bigger source
presentations.

## Word experiment scope (explicit)

The scaled 003 variants genuinely process a larger source DOCX through stages 1-4
(tracked changes, comments, metadata, per-unit corrections) AND rebuild a larger
public packet (N determination tables) through stages 5-6, so both the source
processing cost and the build/render/validation scale with the unit count. Page
count is a LibreOffice-layout outcome, not an input: do not compare the four
variants' PDF page counts as if page count were the declared scale. The declared
scale is the business-unit count.

## PDF experiment scope (explicit)

The scaled 037 variants define scale by the number of frozen structured notice
groups; every group goes through the real ReportLab page functions. The
synthetic input PDF is an artifact only (the builder, like its parent, does not
read it). Do not read the input-PDF page count or any "page duplication" claim
into the results: there is no pypdf page copying, every group enters the build
functions.

## Status of verification

Round 1 (done): deterministic synthesis, no official-material changes, Excel
dedup/corrections/formulas/ranges (positive/negative), PPTX multi-region page
count/order/facts/validation scope, numeric zero-padded sorting/grouping, scaling
payload recognition, tamper rejection, result-path isolation, original
twelve-task hashes unchanged.

Round 2 (static / tiny fixtures only): Word per-unit comments/tracked
changes/bookmarks with valid OOXML, front stages cover unit 2, final rebuild
covers every unit, negative checks fail; PDF 2-group/20-group pages + bookmarks,
orientation, forbidden-substring guard; prepare selective generation, replay
recognition, tamper rejection, result-path isolation; real-tool compatibility on
1-2 unit fixtures.

Round 3 (active Word scales u100/u500, PDF u5/u20 unchanged; functional):
- Word u100/u500 single-loop functional runs passed (1/1/1/0 each, in-loop and
  independent validation 0 errors); 103/503 public tables; real LibreOffice
  pages measured (not presumed 104/504); all units verified including first /
  middle / last; PDF u5/u20 task bytes unchanged.
- generator uniqueness widened to arbitrary N (4-digit wrong amounts, 3-digit
  right amounts <= cap, unique statuses/names/addresses/phones) without changing
  business semantics; validator heading->unit matching indexed (O(1) per
  heading, identical exact-match semantics).
- original twelve-task materials, round-1 014/021 payload and historical
  u5/u20 records are unchanged; historical campaign index mismatch (summary file
  updated after index generation) corrected via a supplementary record +
  `campaign.sha256-index-v2.json`, original index preserved.

Not verified (out of scope): perf / DevKit capture, image build, official
report/HTML updates; all require explicit user confirmation.

## Minimal functional trial (one small variant each)

These run inside the existing unified image
`docops-replay:openeuler-unified-candidate-04` (do not rebuild/install). The
scaling payload and the public entry are mounted read-only; results directories
are separate writable mounts. Two small variants only: `014-n1000`, `021-g5`.

```bash
# precheck: image id, interpreter/versions, validate-only --env-check
# (commands documented in the round's run log under results/docops/scaling-fix-trial-*)

# 014-n1000, one round
docker run --rm --network none \
  --entrypoint /opt/docops/venv/bin/python3 \
  -v /home/lcq/office-trace-replay/docops/scaling/payload:/opt/docops/scaling/payload:ro \
  -v /home/lcq/office-trace-replay/docops/replay.py:/opt/docops/replay.py:ro \
  -v /home/lcq/office-trace-replay/docops/compile.py:/opt/docops/compile.py:ro \
  -v /home/lcq/office-trace-replay/results/docops/scaling-fix-trial-014:/results \
  docops-replay:openeuler-unified-candidate-04 \
  -B /opt/docops/replay.py run --payload /opt/docops/scaling/payload \
    --workdir /workspace/docops/work --results-dir /results \
    --task 014-n1000 --loops 1 --step-timeout 1800

# 021-g5, one round (own container and results dir)
docker run --rm --network none \
  --entrypoint /opt/docops/venv/bin/python3 \
  -v /home/lcq/office-trace-replay/docops/scaling/payload:/opt/docops/scaling/payload:ro \
  -v /home/lcq/office-trace-replay/docops/replay.py:/opt/docops/replay.py:ro \
  -v /home/lcq/office-trace-replay/docops/compile.py:/opt/docops/compile.py:ro \
  -v /home/lcq/office-trace-replay/results/docops/scaling-fix-trial-021:/results \
  docops-replay:openeuler-unified-candidate-04 \
  -B /opt/docops/replay.py run --payload /opt/docops/scaling/payload \
    --workdir /workspace/docops/work --results-dir /results \
    --task 021-g5 --loops 1 --step-timeout 1800
```

Expect the 014 variant to produce a multi-hundred-page PDF; do not cap the
print area or shrink the page set without a separate, recorded decision.

## Round-2 Word/PDF functional trial (next round; not run yet)

Same image, read-only payload + entry, file-by-file mount of `replay.py` and
`compile.py` (never mount the whole host `docops/` over `/opt/docops`), and a
separate writable results dir per variant. Run each variant in its own container
so the shared `/root` workspace is not shared concurrently.

```bash
IMAGE=docops-replay:openeuler-unified-candidate-04   # sha256:57483856a27942ffd4aef853950ca66b00c12b0787aae6c1dac74371d03e6164

for TASK in 003-u100 003-u500; do
  docker run --rm --network none \
    --entrypoint /opt/docops/venv/bin/python3 \
    -v /home/lcq/office-trace-replay/docops/scaling/payload-word-pdf:/opt/docops/scaling/payload:ro \
    -v /home/lcq/office-trace-replay/docops/replay.py:/opt/docops/replay.py:ro \
    -v /home/lcq/office-trace-replay/docops/compile.py:/opt/docops/compile.py:ro \
    -v /home/lcq/office-trace-replay/results/docops/scaling-word-pdf-trial-$TASK:/results \
    "$IMAGE" \
    -B /opt/docops/replay.py run --payload /opt/docops/scaling/payload \
      --workdir /workspace/docops/work --results-dir /results \
      --task "$TASK" --loops 1 --step-timeout 3600
done
```

Precheck before the loop:

```bash
docker run --rm --network none --entrypoint /opt/docops/venv/bin/python3 \
  -v /home/lcq/office-trace-replay/docops/scaling/payload-word-pdf:/opt/docops/scaling/payload:ro \
  -v /home/lcq/office-trace-replay/docops/replay.py:/opt/docops/replay.py:ro \
  -v /home/lcq/office-trace-replay/docops/compile.py:/opt/docops/compile.py:ro \
  "$IMAGE" -B /opt/docops/replay.py validate-only \
    --payload /opt/docops/scaling/payload --env-check \
    --workdir /workspace/docops/work
```

Do not run these until the user confirms the formal functional trial and perf
collection. The 003 outputs' real page counts are an outcome of that run, not a
value to pre-declare.
