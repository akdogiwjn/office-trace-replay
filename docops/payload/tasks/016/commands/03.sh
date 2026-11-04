python - <<'PY'
from pathlib import Path
from openpyxl import load_workbook
src=Path('/root/submission/docops_v2_l3_016_xlsx_forecast_driver_cascade_output.xlsx')
test=Path('/root/tmp/docs/scenario_switch_base_test.xlsx')
wb=load_workbook(src,data_only=False)
wb['Assumptions']['B5']='Base'
wb.calculation.fullCalcOnLoad=True
wb.calculation.forceFullCalc=True
wb.save(test)
print(test)
PY
python /root/.codex/skills/xlsx/scripts/recalc.py /root/tmp/docs/scenario_switch_base_test.xlsx 120
python - <<'PY'
from openpyxl import load_workbook
p='/root/tmp/docs/scenario_switch_base_test.xlsx'
wb=load_workbook(p,data_only=True)
print('title:',wb['Dashboard']['A1'].value)
print('flags:',[wb['Forecast Model'].cell(r,9).value for r in range(2,6)])
print('dashboard breach count:',wb['Dashboard']['G5'].value)
print('dashboard overage:',wb['Dashboard']['A8'].value)
print('exception months:',[wb['Exception Review'].cell(r,1).value for r in range(2,4)])
assert [wb['Forecast Model'].cell(r,9).value for r in range(2,6)]==['OK']*4
assert wb['Dashboard']['G5'].value==0
assert wb['Dashboard']['A8'].value==0
assert [wb['Exception Review'].cell(r,1).value for r in range(2,4)]==[None,None]
print('BASE_SCENARIO_CASCADE_OK')
PY