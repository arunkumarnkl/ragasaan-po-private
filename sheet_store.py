"""Google Sheets repository, and read-only local Excel preview for pre-connection QA."""
from __future__ import annotations
import io
import json
import os
import gspread
import pandas as pd

SHEET_ID = "1uRbY-CehE2s9oVXRYkdSl6qcLIaYDYTfGXzFgGT4cmw"
TABS = ["Users", "Ingredients", "Recipe", "Vendor Data", "Contacts", "Venue"]

class GoogleStore:
    writable=True
    def __init__(self, sheet_id, credentials):
        if not credentials:raise RuntimeError("Google service-account credentials are required")
        self.credentials=dict(credentials)
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
        self.client=gspread.service_account_from_dict(dict(credentials),scopes=scopes)
        self.book=self.client.open_by_key(sheet_id)

    def read(self, title):
        try:
            ws=self.book.worksheet(title)
        except gspread.WorksheetNotFound:
            return []
        return ws.get_all_values(value_render_option="UNFORMATTED_VALUE")

    def sheet(self,title,create=False):
        try:return self.book.worksheet(title)
        except gspread.WorksheetNotFound:
            if not create:raise
            return self.book.add_worksheet(title=title,rows=500,cols=35)

    def save_table(self,title,rows,headers):
        ws=self.sheet(title,create=True)
        values=[headers]+[[safe_cell(r.get(h,"")) for h in headers] for r in rows]
        ws.clear()
        if values:ws.update(range_name="A1",values=values,value_input_option="RAW")

    def update_cells(self,title,changes):
        from gspread import Cell
        ws=self.sheet(title)
        cells=[Cell(row,col,safe_cell(value)) for row,col,value in changes]
        if cells:
            required_cols=max(c.col for c in cells)
            if required_cols>ws.col_count:
                ws.add_cols(required_cols-ws.col_count)
            ws.update_cells(cells,value_input_option="RAW")

    def append_rows(self,title,rows):
        self.sheet(title).append_rows([[safe_cell(c) for c in row] for row in rows],value_input_option="RAW")

    def delete_row(self,title,row_number):
        """Delete one 1-based worksheet row, never the Recipe header rows."""
        if row_number < 3:
            raise ValueError("Cannot delete header rows")
        self.sheet(title).delete_rows(int(row_number))


def safe_cell(x):
    if x is None:return ""
    if isinstance(x,(int,float,bool,str)):return x
    return str(x)

class ExcelPreview:
    """Upload Excel at runtime to preview without exposing or bundling workbook data."""
    writable=False
    def __init__(self,content):
        self.all=pd.read_excel(io.BytesIO(content),sheet_name=None,header=None,keep_default_na=False,dtype=object)
    def read(self,title):
        if title not in self.all:return []
        df=self.all[title].fillna("")
        return [[c.item() if hasattr(c,"item") and callable(c.item) else c for c in row]
                for row in df.values.tolist()]


def credentials_from_secrets(secrets):
    try:
        if "gcp_service_account" in secrets:return dict(secrets["gcp_service_account"])
    except Exception:pass
    raw=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON","")
    return json.loads(raw) if raw else None


KEYRING_SERVICE="Ragasaan_Purchase_Order_Google"
KEYRING_ACCOUNT="sheet_connection_v3"

def load_saved_connection():
    """OS credential vault. Keyring uses Windows Credential Manager on Windows."""
    try:
        import keyring
        stored=keyring.get_password(KEYRING_SERVICE,KEYRING_ACCOUNT)
        if not stored:return None
        return json.loads(stored)
    except Exception:
        return None

def save_connection_to_keyring(sheet_id,credentials):
    import keyring
    payload={'sheet_id':sheet_id,'credentials':credentials}
    keyring.set_password(KEYRING_SERVICE,KEYRING_ACCOUNT,json.dumps(payload))

def clear_saved_connection():
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE,KEYRING_ACCOUNT)
    except Exception:pass
