
import openpyxl
wb=openpyxl.load_workbook('input/egrid2023_data_rev2.xlsx')
for ws in wb.worksheets:
    print(ws.title, ws.max_row, ws.max_column, 'charts',len(ws._charts),'imgs',len(ws._images),'merged',len(ws.merged_cells.ranges),'cf',len(list(ws.conditional_formatting)),'dv',len(ws.data_validations.dataValidation),'freeze',ws.freeze_panes)
print('defined names', list(wb.defined_names))
print('ext links', wb._external_links)
ws=wb['US23']
for a in ['A1','A2','A3','G3','M3','U3','DZ3']:
    c=ws[a]; print(a, repr(c.value), c.font.name, c.font.sz, c.number_format, c.fill.fgColor.rgb if c.fill and c.fill.fill_type else None)
print('contents A1..B10')
ws=wb['Contents']
for r in ws.iter_rows(min_row=1,max_row=12,max_col=4,values_only=True): print(r)
