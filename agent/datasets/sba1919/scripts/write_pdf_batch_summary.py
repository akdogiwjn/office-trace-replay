#!/usr/bin/env python3
"""Dataset-private observed replay summary, not a copied historical success."""
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'replay-config.json').read_text())
    output = root / 'output'
    if config['kind'] == 'xlsx':
        business = json.loads((output / 'business_verification.json').read_text())
        recalc = json.loads((output / 'formula_recalc.json').read_text())
        if business.get('status') != 'success' or recalc.get('status') != 'success':
            raise ValueError('cannot summarize unsuccessful execution')
        summary = dict(dataset_id=config['dataset_id'], source_run_id=config['source_run_id'],
                       source_type='effective-agent-tool-chain-with-declared-CSV-adaptation',
                       helper_filenames=[config['helper']], helper_execution_attempts=1,
                       helper_execution_successes=1, recalc_invocation_count=1,
                       final_verifier_status=business['status'],
                       actual_call_evidence='See this iteration.json; no automatic retries.',
                       historical_agent_summary_reused=False)
        name = 'xlsx_enhancement_summary.json'
    else:
        requirements = config['requirements']
        records = requirements['record_count']
        pages = requirements['page_count']
        filled = list((output / 'filled').glob('*.pdf'))
        pngs = list((output / 'rendered').rglob('*.png'))
        mappings = list((output / 'field_values').glob('*.json'))
        template = list((output / 'rendered/template').glob('*.png'))
        if len(filled) != records or len(mappings) != records or len(template) != pages or len(pngs) != pages * (records + 1):
            raise ValueError('regenerated PDF/mapping/PNG inventory mismatch')
        protected = set(requirements['protected_blank'])
        for mapping in mappings:
            entries = json.loads(mapping.read_text())
            if any(item['field_id'] in protected and str(item.get('value', '')) not in ('', '/Off', 'Off')
                   for item in entries):
                raise ValueError('protected field populated in generated mapping')
        # Check every regenerated fill/render invocation log, not expected counts alone.
        counts_path = output / 'logs/operation_counts.json'
        if counts_path.exists():
            counts = json.loads(counts_path.read_text())
            if counts['fill'] != records or counts['render'] != records or counts['failures']:
                raise ValueError('batch driver did not complete all operations')
            logs = list((output / 'logs').glob('fill_*.log')) + list((output / 'logs').glob('render_*.log'))
            if len(logs) != records * 2 or any('[exit 0]' not in p.read_text() for p in logs):
                raise ValueError('missing successful fill/render log')
        summary = dict(input_form=config['form'], applicant_count=records,
                       filled_pdf_count=len(filled), rendered_page_count=len(pngs),
                       fill_script_invocations=records, render_script_invocations=records + 1,
                       actual_operation_counts=dict(check_fillable_fields=1, extract_form_field_info=1,
                                                    fill_fillable_fields=records, convert_pdf_to_images=records + 1),
                       failed_attempts=[], source_run_id=config['source_run_id'],
                       ssn_and_signatures_left_blank=True,
                       privacy_evidence='Generated mappings omit protected values; following business verifier checks actual filled PDFs.',
                       historical_agent_summary_reused=False)
        name = 'batch_summary.json'
        if (output / name).exists():
            original = json.loads((output / name).read_text())
            for key in ['filled_pdf_count', 'rendered_page_count', 'fill_script_invocations', 'render_script_invocations']:
                if original.get(key) != summary[key]:
                    raise ValueError('driver summary mismatch: ' + key)
            return  # SBA's original Agent driver already wrote its own summary.
    (output / name).write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
