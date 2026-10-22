# Standalone PDF slice replay

This directory replays one PDF hotspot process at a time from immutable stage
inputs. It does not run the complete four-step document benchmark.

## Usage

```bash
/opt/document-bench-slicing-xpdf/run_slice.sh PDF-01
/opt/document-bench-slicing-xpdf/run_slice.sh --slice PDF-03
```

The six slice IDs are:

| ID | Process |
|---|---|
| `PDF-01` | `check_fillable_fields.py` |
| `PDF-02` | `extract_form_field_info.py` |
| `PDF-03` | template `convert_pdf_to_images.py`, including Poppler children |
| `PDF-04` | `fill_fillable_fields.py` for `applicant_01` |
| `PDF-05` | filled-PDF `convert_pdf_to_images.py`, including Poppler children |
| `PDF-06` | `verify_pdf_batch.py` for the one-applicant checkpoint |

Each invocation recreates the fixed workspace at
`/root/.openclaw/workspace/tool-modeling/SUB-MEM-PDF-01`. The saved files under
`inputs/` are read-only checkpoints and are never modified by `run_slice.sh`.

`PDF-03` and `PDF-05` intentionally use separate copies of the conversion
script so they can be instrumented independently.

Example with CPU binding and `perf stat`:

```bash
perf stat \
  -e task-clock,cycles:u,cycles:k,instructions:u,instructions:k,context-switches,page-faults \
  -- taskset -c 100 \
  /opt/document-bench-slicing-xpdf/run_slice.sh PDF-03
```

Because the selected Python process is launched directly with `exec`, `perf`
also inherits its `pdfinfo` and `pdftoppm` child processes by default.
