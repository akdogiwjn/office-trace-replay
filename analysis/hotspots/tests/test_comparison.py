import hashlib
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import compare as c


class Comparison(unittest.TestCase):
    def test_seven_current_profiles_replace_historical_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            baseline=root/'legacy.json';baseline.write_text(json.dumps(dict(profiles={'old-only':{}})))
            datasets=['opm-n10','irs_w4','sba1919','tlc','hr_metro','egrid','industry_productivity']
            profiles={}
            for dataset in datasets:
                p=root/(dataset+'.json')
                p.write_text(json.dumps(dict(image_id='same-image',roi_samples=12,
                    processes=[dict(script='inspect.py',share_roi=1)],contexts=[],
                    functions=[dict(dso='/lib/libpython.so',function='gc_collect_main',share_roi=1)])))
                profiles[dataset]=dict(path=p.name,sha256=c.sha(p))
            config=dict(reference_mode='current-image',baseline=dict(path=baseline.name,sha256=c.sha(baseline)),
                profiles=profiles,output='report',assessment=dict(metadata_sources=[],xlsx_datasets=[],pdf_datasets=[],trace_sources=[]),
                groups=[dict(title='PDF',datasets=datasets[:3]),dict(title='XLSX',datasets=datasets[3:])])
            path=root/'config.json';path.write_text(json.dumps(config))
            with patch.object(c,'ROOT',root),redirect_stdout(io.StringIO()):c.compare(path)
            result=json.loads((root/'report/comparison.json').read_text())
            self.assertEqual(set(result['profiles']),set(datasets))
            self.assertEqual(set(result['comparisons']),set(datasets)-{'opm-n10','tlc'})
            self.assertEqual(set(result['historical_profiles']),{'old-only'})
            self.assertIn('industry_productivity',(root/'report/report.md').read_text())

    def test_inline_owners_aggregate_before_ranking_and_period_weight_repeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'metadata').mkdir();(root/'processed/packed').mkdir(parents=True)
            records=[]
            for name in ('opm-n10','tlc'):
                def repeat(period,inline_share):
                    return dict(total_period=period,roi_samples=2,process_layer={'pdf-fill':1},
                        function_layer=[dict(entity_symbol='owner',entity_dso='/lib/libpython.so',
                                             symbol='inline',share_of_roi=inline_share),
                                        dict(entity_symbol='other',entity_dso='/lib/libpython.so',
                                             symbol='other',share_of_roi=1-inline_share)])
                payload=json.dumps(dict(repeats={'r1':repeat(10,1),'r2':repeat(30,0)})).encode()
                archive=f'processed/packed/{name}.json.gz';path=root/archive
                path.write_bytes(gzip.compress(payload))
                records.append(dict(path=f'processed/{name}.json',archive=archive,
                    archive_sha256=c.sha(path),sha256=hashlib.sha256(payload).hexdigest()))
            (root/'metadata/profile-artifacts.json').write_text(json.dumps(dict(files=records)))
            (root/'metadata/run-provenance.json').write_text(json.dumps(dict(runs=[
                dict(config='opm-n10',collector='native',repeat='r1',requested_iterations=3,rate_hz=99),
                dict(config='tlc',collector='native',repeat='r1',requested_iterations=1,rate_hz=49)])))
            dest=root/'baseline.json';c.freeze_legacy(root,dest)
            profile=json.loads(dest.read_text())['profiles']['tlc']
            functions={f['function']:f['share_roi'] for f in profile['functions']}
            self.assertEqual(functions,{'other':.75,'owner':.25})
            self.assertEqual(profile['roi_period'],40)
            self.assertEqual((profile['loops_per_repeat'],profile['sample_rate_hz']),(1,49))
            with self.assertRaises(ValueError):c.freeze_legacy(root,dest)

    def test_unknown_function_is_not_evidence_of_matching(self):
        functions=[dict(library='unknown',function='[unknown]',share_roi=.9),
                   dict(library='libpython',function='owner',share_roi=.1)]
        result=c.overlap(dict(functions=functions),dict(functions=functions))
        self.assertEqual(result['common_top10_count'],1)
        self.assertEqual(result['common_top10'][0]['function'],'owner')

    def test_embedded_expat_and_zlib_extensions_are_identified(self):
        self.assertEqual(c.library('/opt/python/lib-dynload/pyexpat.cpython-312.so'),'expat')
        self.assertEqual(c.library('/opt/python/lib-dynload/zlib.cpython-312.so'),'zlib')
        self.assertEqual(c.library('/opt/libreoffice/program/libsclo.so'),'LibreOffice')


if __name__=='__main__':unittest.main()
