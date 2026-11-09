"""Builds the Excel files:
  excel/InvoiceDesk_Data.xlsx    raw data only (you build the checks yourself, following the guide)
  excel/InvoiceDesk_Solved.xlsx  every check as a formula column (XLOOKUP, needs Excel 2021 / 365)
  --verify  also builds an INDEX/MATCH twin, recalculates it in LibreOffice and compares with the answer key"""
import sys, subprocess, shutil
from datetime import date
from pathlib import Path
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

D = Path("data")
vm = pd.read_csv(D / "vendor_master.csv", dtype=str, keep_default_na=False)
pr = pd.read_csv(D / "purchase_register.csv", dtype={"vendor_gstin": str, "invoice_no": str}, keep_default_na=False, na_values=[""], parse_dates=["booked_on", "invoice_date"])
g2 = pd.read_csv(D / "gstr_2b.csv", dtype={"supplier_gstin": str, "invoice_no": str}, parse_dates=["invoice_date"])
pm = pd.read_csv(D / "payments.csv", dtype={"invoice_no": str}, parse_dates=["payment_date"])
cr = pd.read_csv(D / "category_rates.csv")
vm["payment_terms_days"] = vm.payment_terms_days.astype(int)
HDR = Font(bold=True, color="FFFFFF"); RAW = PatternFill("solid", fgColor="1F4E78"); CHK = PatternFill("solid", fgColor="C55A11")

def put(ws, df, start_col=1):
    for j, c in enumerate(df.columns, start_col):
        ws.cell(1, j, c).font = HDR; ws.cell(1, j).fill = RAW
    for i, row in enumerate(df.itertuples(index=False), 2):
        for j, v in enumerate(row, start_col):
            if v is None or (isinstance(v, float) and pd.isna(v)) or v == "" or v is pd.NaT: continue
            if isinstance(v, pd.Timestamp): v = v.date()
            c = ws.cell(i, j, v)
            if isinstance(v, date): c.number_format = "dd-mmm-yyyy"
            elif isinstance(v, float): c.number_format = "#,##0.00"

def add_checks(ws, n, cols, start_col):
    for k, (name, f) in enumerate(cols):
        j = start_col + k; ws.cell(1, j, name).font = HDR; ws.cell(1, j).fill = CHK
        for i in range(2, n + 2): ws.cell(i, j, "=" + f.replace("{r}", str(i)))

def lk(x, L, R, nf, mode):
    return f'XLOOKUP({x},{L},{R},{nf})' if mode == "x" else f'IFERROR(INDEX({R},MATCH({x},{L},0)),{nf})'

def build(solved, mode, path):
    wb = Workbook(); wb.remove(wb.active)
    sheets = {}
    for name, df in [("Vendor_Master", vm), ("Purchase_Register", pr), ("GSTR_2B", g2), ("Payments", pm), ("Category_Rates", cr)]:
        ws = wb.create_sheet(name); put(ws, df); sheets[name] = ws
    if solved:
        nV, nP, nB, nY = len(vm), len(pr), len(g2), len(pm)
        add_checks(sheets["Vendor_Master"], nV, [
            ("GSTIN_Missing", 'IF(D{r}="","Yes","No")'),
            ("GSTIN_Invalid", 'IF(D{r}="","No",IF(OR(LEN(D{r})<>15,IFERROR(VALUE(LEFT(D{r},2)),0)<1,IFERROR(VALUE(LEFT(D{r},2)),0)>38,MID(D{r},14,1)<>"Z"),"Yes","No"))'),
            ("PAN_Mismatch", 'IF(AND(I{r}="No",J{r}="No",MID(D{r},3,10)<>C{r}),"Yes","No")'),
            ("Duplicate_Vendor", f'IF(COUNTIF($C$2:$C${nV+1},C{{r}})>1,"Yes","No")')], 9)
        V = "Vendor_Master!$A:$A"
        add_checks(sheets["Purchase_Register"], nP, [
            ("Tax_Booked", 'K{r}+L{r}+M{r}'),
            ("Duplicate", 'IF(OR(E{r}="",F{r}=""),"No",IF(COUNTIFS($E$2:E{r},E{r},$F$2:F{r},F{r},$N$2:N{r},N{r})>1,"Yes","No"))'),
            ("Missing_Field", 'IF(OR(E{r}="",F{r}="",G{r}="",I{r}=""),"Yes","No")'),
            ("Tax_Expected", 'IF(I{r}="","",ROUND(I{r}*J{r}/100,2))'),
            ("Tax_Wrong", 'IF(I{r}="","No",IF(ABS(O{r}-I{r}*J{r}/100)>1,"Yes","No"))'),
            ("Supplier_State", lk("C{r}", V, "Vendor_Master!$E:$E", '""', mode)),
            ("Tax_Type_Wrong", 'IF(OR(AND(T{r}="27",M{r}>0),AND(T{r}<>"27",K{r}+L{r}>0)),"Yes","No")'),
            ("Vendor_Category", lk("C{r}", V, "Vendor_Master!$H:$H", '""', mode)),
            ("Category_Mismatch", 'IF(H{r}<>V{r},"Yes","No")'),
            ("GST_Key", 'E{r}&"|"&F{r}'),
            ("2B_Taxable", lk("X{r}", "GSTR_2B!$I:$I", "GSTR_2B!$F:$F", '"Not found"', mode)),
            ("2B_Tax", lk("X{r}", "GSTR_2B!$I:$I", "GSTR_2B!$G:$G", '"Not found"', mode)),
            ("GST_2B_Status", 'IF(P{r}="Yes","EXCLUDED_DUPLICATE",IF(Q{r}="Yes","EXCLUDED_INCOMPLETE",IF(Y{r}="Not found","MISSING_IN_2B",IF(OR(ABS(I{r}-Y{r})>1,ABS(O{r}-Z{r})>1),"AMOUNT_MISMATCH","MATCHED"))))'),
            ("Pay_Key", 'C{r}&"|"&F{r}'),
            ("Pay_Count", 'COUNTIF(Payments!$H:$H,AB{r})'),
            ("Paid_Plus_TDS", 'SUMIF(Payments!$H:$H,AB{r},Payments!$E:$E)+SUMIF(Payments!$H:$H,AB{r},Payments!$F:$F)'),
            ("Due_Date", 'IF(G{r}="","",G{r}+' + lk("C{r}", V, "Vendor_Master!$G:$G", "0", mode) + ')'),
            ("Payment_Status", 'IF(P{r}="Yes","EXCLUDED_DUPLICATE",IF(F{r}="","CANNOT_LINK",IF(AC{r}>1,"PAID_TWICE",IF(AC{r}=1,IF(N{r}="","CANNOT_CHECK",IF(ABS(AD{r}-N{r})<=1,"PAID_OK",IF(AD{r}<N{r},"UNDERPAID","OVERPAID"))),IF(G{r}="","UNPAID_NO_DATE",IF(AE{r}<DATE(2026,10,31),"UNPAID_OVERDUE","UNPAID_NOT_DUE"))))))'),
        ], 15)
        for i in range(2, nP + 2): sheets["Purchase_Register"].cell(i, 31).number_format = "dd-mmm-yyyy"
        add_checks(sheets["GSTR_2B"], nB, [("GST_Key", 'B{r}&"|"&D{r}'),
                                           ("In_Books", 'IF(COUNTIF(Purchase_Register!$X:$X,I{r})>0,"Yes","No")')], 9)
        add_checks(sheets["Payments"], nY, [("Pay_Key", 'B{r}&"|"&C{r}'),
                                            ("Linked", 'IF(COUNTIF(Purchase_Register!$AB:$AB,H{r})>0,"Yes","No")'),
                                            ("Vendor_Category", lk("B{r}", V, "Vendor_Master!$H:$H", '""', mode)),
                                            ("TDS_Not_Deducted", 'IF(AND(I{r}="Yes",OR(J{r}="Professional Fees",J{r}="Rent"),F{r}=0),"Yes","No")')], 8)
        s = wb.create_sheet("Summary", 0)
        s["A1"] = "InvoiceDesk: exception summary"; s["A1"].font = Font(bold=True, size=14)
        s["A2"] = "Sahyadri Components Pvt Ltd (fictional) · invoices Apr–Sep 2026 · review date 31 Oct 2026"
        rows = [("Vendor master", "GSTIN missing", '=COUNTIF(Vendor_Master!I:I,"Yes")'),
                ("Vendor master", "GSTIN invalid format", '=COUNTIF(Vendor_Master!J:J,"Yes")'),
                ("Vendor master", "PAN does not match GSTIN", '=COUNTIF(Vendor_Master!K:K,"Yes")'),
                ("Vendor master", "Vendor records sharing a PAN", '=COUNTIF(Vendor_Master!L:L,"Yes")'),
                ("Invoices", "Duplicate invoice", '=COUNTIF(Purchase_Register!P:P,"Yes")'),
                ("Invoices", "Missing field", '=COUNTIF(Purchase_Register!Q:Q,"Yes")'),
                ("Invoices", "Tax amount wrong", '=COUNTIF(Purchase_Register!S:S,"Yes")'),
                ("Invoices", "Tax type wrong (IGST vs CGST/SGST)", '=COUNTIF(Purchase_Register!U:U,"Yes")'),
                ("Invoices", "Category mismatch", '=COUNTIF(Purchase_Register!W:W,"Yes")'),
                ("GST 2B", "Missing in 2B", '=COUNTIF(Purchase_Register!AA:AA,"MISSING_IN_2B")'),
                ("GST 2B", "Amount mismatch", '=COUNTIF(Purchase_Register!AA:AA,"AMOUNT_MISMATCH")'),
                ("GST 2B", "Matched", '=COUNTIF(Purchase_Register!AA:AA,"MATCHED")'),
                ("GST 2B", "In 2B but not in books", '=COUNTIF(GSTR_2B!J:J,"No")'),
                ("GST 2B", "Input tax credit at risk (Rs)", '=SUMIFS(Purchase_Register!O:O,Purchase_Register!AA:AA,"MISSING_IN_2B")'),
                ("Payments", "Paid twice", '=COUNTIF(Purchase_Register!AF:AF,"PAID_TWICE")'),
                ("Payments", "Underpaid", '=COUNTIF(Purchase_Register!AF:AF,"UNDERPAID")'),
                ("Payments", "Overpaid", '=COUNTIF(Purchase_Register!AF:AF,"OVERPAID")'),
                ("Payments", "Unpaid and overdue", '=COUNTIF(Purchase_Register!AF:AF,"UNPAID_OVERDUE")'),
                ("Payments", "Payment not linked to an invoice", '=COUNTIF(Payments!I:I,"No")'),
                ("Payments", "TDS not deducted", '=COUNTIF(Payments!K:K,"Yes")')]
        for j, h in enumerate(["Area", "Check", "Count"], 1):
            c = s.cell(4, j, h); c.font = HDR; c.fill = RAW
        for i, (a, b, f) in enumerate(rows, 5):
            s.cell(i, 1, a); s.cell(i, 2, b); c = s.cell(i, 3, f); c.number_format = "#,##0"
        s.column_dimensions["A"].width = 16; s.column_dimensions["B"].width = 38; s.column_dimensions["C"].width = 16
    for ws in wb.worksheets:
        if ws.title == "Summary": continue
        ws.freeze_panes = "B2"
        for j in range(1, ws.max_column + 1): ws.column_dimensions[get_column_letter(j)].width = 15
    wb.save(path)

build(False, "x", "excel/InvoiceDesk_Data.xlsx")
build(True, "x", "excel/InvoiceDesk_Solved.xlsx")
print("built excel/InvoiceDesk_Data.xlsx and excel/InvoiceDesk_Solved.xlsx")

if "--verify" in sys.argv:
    tmp = Path("/tmp/idv"); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()
    build(True, "im", tmp / "twin.xlsx")
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp / "out"), str(tmp / "twin.xlsx")], capture_output=True)
    wb = load_workbook(tmp / "out" / "twin.xlsx", data_only=True)
    summ = {(r[0], r[1]): r[2] for r in wb["Summary"].iter_rows(min_row=5, values_only=True)}
    exp = pd.read_csv("answer_key/expected_counts.csv").set_index("check")["count"].to_dict()
    st = pd.read_csv("answer_key/invoice_status.csv")
    want = {"GSTIN missing": exp["GSTIN_MISSING"], "GSTIN invalid format": exp["GSTIN_INVALID"], "PAN does not match GSTIN": exp["PAN_MISMATCH"],
            "Vendor records sharing a PAN": exp["DUPLICATE_VENDOR"], "Duplicate invoice": exp["DUPLICATE_INVOICE"], "Missing field": exp["FIELD_MISSING"],
            "Tax amount wrong": exp["TAX_AMOUNT_WRONG"], "Tax type wrong (IGST vs CGST/SGST)": exp["TAX_TYPE_WRONG"], "Category mismatch": exp["CATEGORY_MISMATCH"],
            "Missing in 2B": exp["MISSING_IN_2B"], "Amount mismatch": exp["AMOUNT_MISMATCH"], "Matched": int((st.gst_2b_status == "MATCHED").sum()),
            "In 2B but not in books": exp["NOT_IN_BOOKS"], "Paid twice": exp["PAID_TWICE"], "Underpaid": exp["UNDERPAID"], "Overpaid": exp["OVERPAID"],
            "Unpaid and overdue": exp["UNPAID_OVERDUE"], "Payment not linked to an invoice": exp["PAYMENT_NOT_LINKED"], "TDS not deducted": exp["TDS_NOT_DEDUCTED"]}
    bad = 0
    for (a, b), v in summ.items():
        w = want.get(b)
        flag = "" if w is None or v == w else "  <-- MISMATCH"; bad += bool(flag)
        print(f"{a:14} {b:38} excel={v}  expected={w}{flag}")
    # row level: every invoice's 2B and payment status
    ws = wb["Purchase_Register"]; got = {r[0]: (r[26], r[31]) for r in ws.iter_rows(min_row=2, values_only=True)}
    diff = [(k, got[k], (a, b)) for k, a, b in st.itertuples(index=False) if got[k] != (a, b)]
    print("row-level status differences:", len(diff), diff[:3]); print("ALL MATCH" if not bad and not diff else "CHECK FAILED")
