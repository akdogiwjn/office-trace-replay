python3 - <<'PY'
from zipfile import ZipFile
from lxml import etree
from pathlib import Path
p=Path('/root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output.docx')
forbidden=['DRAFT','PRIVATE','TODO','uncertain','QMS-PR-700','version 4.1','2026-07-01','QA analyst','Interim Approver','2026-08-25','5 years','2026-09-05','aproval','effectve','obsolte','distribtuion','trainng','retetion']
with ZipFile(p) as z:
    bad=[]
    for n in z.namelist():
        if n.endswith(('.xml','.rels')):
            raw=z.read(n)
            etree.fromstring(raw)
            text=raw.decode('utf-8','ignore')
            for item in forbidden:
                if item in text:
                    bad.append((n,item))
    print('zip_xml_entries',len(z.namelist()))
    print('zip_crc_test',z.testzip())
    print('raw_forbidden_matches',bad)
PY
unzip -t /root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output.docx | tail -2
sha256sum /root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output.docx