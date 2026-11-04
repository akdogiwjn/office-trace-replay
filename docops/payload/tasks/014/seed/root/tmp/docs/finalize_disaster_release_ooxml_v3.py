import re
import shutil
import tempfile
import zipfile
from pathlib import Path


OUTPUT = Path("/root/submission/docops_v2_l3_014_xlsx_disaster_housing_grant_public_release_output.xlsx")
SHEETS = {
    "xl/worksheets/sheet1.xml": "FF70AD47",
    "xl/worksheets/sheet2.xml": "FF5B9BD5",
    "xl/worksheets/sheet3.xml": "FFFFC000",
    "xl/worksheets/sheet4.xml": "FFC00000",
    "xl/worksheets/sheet5.xml": "FF7030A0",
}


def add_tab_color(xml, color):
    if re.search(r"<sheetPr\b[^>]*>(?:(?!</sheetPr>).)*<tabColor\b", xml, re.DOTALL):
        return re.sub(r'<tabColor\b[^>]*/>', f'<tabColor rgb="{color}"/>', xml, count=1)
    return re.sub(
        r"(<sheetPr\b[^>]*>)",
        rf'\1<tabColor rgb="{color}"/>',
        xml,
        count=1,
    )


temp_dir = Path(tempfile.mkdtemp(prefix="disaster_release_finalize_", dir="/root/tmp/docs"))
temp_path = temp_dir / OUTPUT.name
with zipfile.ZipFile(OUTPUT, "r") as source_zip, zipfile.ZipFile(
    temp_path, "w", compression=zipfile.ZIP_DEFLATED
) as target_zip:
    for item in source_zip.infolist():
        data = source_zip.read(item.filename)
        if item.filename in SHEETS:
            xml = data.decode("utf-8")
            xml = add_tab_color(xml, SHEETS[item.filename])
            xml = xml.replace(' draft="false"', "")
            if item.filename == "xl/worksheets/sheet2.xml":
                xml = xml.replace("FALSE()", "FALSE")
            data = xml.encode("utf-8")
        elif item.filename == "xl/workbook.xml":
            xml = data.decode("utf-8")
            xml = re.sub(
                r"<workbookProtection\b[^>]*/>",
                '<workbookProtection lockStructure="1"/>',
                xml,
                count=1,
            )
            xml = re.sub(r'\s+fullCalcOnLoad="[^"]*"', "", xml, count=1)
            xml = re.sub(
                r"(<calcPr\b[^>]*?)(/?>)",
                r'\1 fullCalcOnLoad="true"\2',
                xml,
                count=1,
            )
            data = xml.encode("utf-8")
        elif item.filename == "xl/styles.xml":
            xml = data.decode("utf-8")
            xml = re.sub(
                r'(<numFmt numFmtId="165" formatCode=")[^"]*(")',
                r'\1$#,##0;($#,##0);-\2',
                xml,
                count=1,
            )
            data = xml.encode("utf-8")
        target_zip.writestr(item, data)

shutil.move(temp_path, OUTPUT)
print(OUTPUT)
