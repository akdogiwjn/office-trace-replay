from openpyxl import load_workbook
wb=load_workbook('output/industry_productivity_enhanced.xlsx')
s=wb['Productivity_Summary']
for c in s._charts:
    a=c.anchor
    print(type(a).__name__, a._from.col, a._from.row, getattr(a,'ext',None) and (a.ext.cx, a.ext.cy))
for col in 'ABCDEF':
    print(col, s.column_dimensions[col].width)
print('row heights', {r:s.row_dimensions[r].height for r in (1,2,4,11,12,18,19,20,26)})
print('merged', [str(x) for x in s.merged_cells.ranges])
print('cf', [(str(g.sqref), len(s.conditional_formatting[g])) for g in s.conditional_formatting])
