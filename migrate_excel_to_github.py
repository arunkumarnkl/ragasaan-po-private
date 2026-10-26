"""Convert a CURRENT Google Sheets Excel export to GitHub JSON on your PC.

Does NOT change GitHub remotely. It intentionally skips Users so that
plaintext passwords from Excel are never published to the repository.
Usage: python migrate_excel_to_github.py latest-export.xlsx
Then upload the generated database/*.json files to the private repo.
"""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import re,json,sys

S='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
TABLES={'Ingredients':'ingredients','Recipe':'recipe','Vendor Data':'vendor_data',
        'Contacts':'contacts','Venue':'venue','PO_Rules':'po_rules',
        'PO_Alcohol_Matrix':'po_alcohol_matrix','PO_Settings':'po_settings',
        'PO_Supplier_Prices':'po_supplier_prices',
        'PO_Recipe_Notes':'po_recipe_notes','PO_Recipe_Images':'po_recipe_images'}

def to_rows(z,target,strings):
    xml=ET.fromstring(z.read(target))
    result=[]
    for row in xml.findall('.//'+S+'sheetData/'+S+'row'):
        values={}
        for c in row.findall(S+'c'):
            idx=0
            for letter in re.match(r'[A-Z]+',c.attrib['r']).group(0):idx=idx*26+ord(letter)-64
            idx-=1
            v=c.find(S+'v');ty=c.get('t','')
            if ty=='inlineStr':value=''.join(x.text or '' for x in c.iter(S+'t'))
            elif v is None:value=''
            elif ty=='s':value=strings[int(v.text)]
            elif ty=='b':value=v.text=='1'
            elif ty in ('n',''):
                try:value=float(v.text) if any(c in v.text for c in '.Ee') else int(v.text)
                except (ValueError,TypeError):value=v.text or ''
            else:value=v.text or ''
            values[idx]=value
        if values:result.append([values.get(i,'') for i in range(max(values)+1)])
    return result

def convert(path,outdir):
    with ZipFile(path) as z:
        b=ET.fromstring(z.read('xl/workbook.xml'))
        rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        links={n.attrib['Id']:n.attrib['Target'].lstrip('/') for n in rel}
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            sr=ET.fromstring(z.read('xl/sharedStrings.xml'))
            strings=[''.join(x.text or '' for x in si.iter(S+'t')) for si in sr]
        for sheet in b.find(S+'sheets'):
            name=sheet.get('name')
            if name not in TABLES:continue
            target=links[sheet.get(R+'id')]
            if not target.startswith('xl/'):target='xl/'+target
            rows=to_rows(z,target,strings)
            if not rows:continue
            output=Path(outdir)/f'{TABLES[name]}.json'
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps({'rows':rows},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
            print(name,len(rows)-1,'records ->',output)
    print('Accounts were NOT imported. Keep database/users.json with hashed passwords.')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python migrate_excel_to_github.py latest-export.xlsx')
    convert(sys.argv[1],Path(__file__).parent/'database')
