python3 - <<'PY'
from docx import Document
from docx.shared import Inches
from docx.oxml.ns import qn
from pathlib import Path
p=Path('/root/submission/docops_v2_l3_001_docx_controlled_document_release_repair_output.docx')
d=Document(p)
expected_headings=[
'Controlled Document Release Repair Packet',
'Correction Register Applied',
'Controlled Document Metadata',
'Revision History',
'Distribution and Training Workflow',
'Obsolete Copy Retirement Checklist',
'Final Release Appendix']
actual=[x.text for x in d.paragraphs if x.style.name in ('Title','Heading 1')]
print('headings_match',actual==expected_headings)
print('heading_styles',[(x.text,x.style.name) for x in d.paragraphs if x.style.name in ('Title','Heading 1')])
print('page_break_headings',[(x.text,x.paragraph_format.page_break_before) for x in d.paragraphs if x.style.name=='Heading 1' and x.paragraph_format.page_break_before])
print('margins_inches',[round(s.top_margin.inches,2) for s in d.sections],round(d.sections[0].bottom_margin.inches,2),round(d.sections[0].left_margin.inches,2),round(d.sections[0].right_margin.inches,2))
print('normal_style',d.styles['Normal'].font.name,d.styles['Normal'].font.size.pt)
print('title_style',d.styles['Title'].font.name,d.styles['Title'].font.size.pt,str(d.styles['Title'].font.color.rgb))
print('heading_style',d.styles['Heading 1'].font.name,d.styles['Heading 1'].font.size.pt,str(d.styles['Heading 1'].font.color.rgb))
print('core',d.core_properties.author,'|',d.core_properties.title,'|',d.core_properties.last_modified_by)
print('table_header_fill',d.tables[0].rows[0].cells[0]._tc.tcPr.find(qn('w:shd')).get(qn('w:fill')))
print('section_count',len(d.sections),'table_count',len(d.tables))
PY