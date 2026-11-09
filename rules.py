"""Independent rule engine: reads data/*.csv and writes the answer key.
The SQL and Excel solutions are checked against answer_key/expected_results.csv."""
import pandas as pd, numpy as np
D = "data/"; ASOF = pd.Timestamp("2026-10-31"); TOL = 1.0; HOME = "27"; TDS_CATS = {"Professional Fees", "Rent"}
vm = pd.read_csv(D + "vendor_master.csv", dtype=str, keep_default_na=False)
pr = pd.read_csv(D + "purchase_register.csv", dtype={"vendor_gstin": str, "invoice_no": str}, keep_default_na=False, na_values=[""])
g2 = pd.read_csv(D + "gstr_2b.csv", dtype=str, keep_default_na=False)
pm = pd.read_csv(D + "payments.csv", dtype={"invoice_no": str})
out = []
def add(table, rid, check, detail=""): out.append(dict(table=table, record_id=rid, check=check, detail=detail))

# ---- vendor master ----
def gst_invalid(g):
    if g == "": return False
    return len(g) != 15 or not g[:2].isdigit() or not (1 <= int(g[:2]) <= 38) or g[13] != "Z"
pan_n = vm.pan.value_counts()
for v in vm.itertuples():
    if v.gstin == "": add("vendor_master", v.vendor_id, "GSTIN_MISSING")
    elif gst_invalid(v.gstin): add("vendor_master", v.vendor_id, "GSTIN_INVALID", v.gstin)
    elif v.gstin[2:12] != v.pan: add("vendor_master", v.vendor_id, "PAN_MISMATCH", f"GSTIN has {v.gstin[2:12]}, PAN column {v.pan}")
    if pan_n[v.pan] > 1: add("vendor_master", v.vendor_id, "DUPLICATE_VENDOR", f"PAN {v.pan} used by {pan_n[v.pan]} vendor records")

# ---- purchase register ----
vinfo = vm.set_index("vendor_id")
pr["tax"] = (pr.cgst + pr.sgst + pr.igst).round(2)
seen, dup = set(), {}
for r in pr.itertuples():   # rows are in booking order
    if pd.isna(r.vendor_gstin) or pd.isna(r.invoice_no): continue
    k = (r.vendor_gstin, r.invoice_no, r.total_amount)
    if k in seen: dup[r.pr_id] = True
    seen.add(k)
miss_cols = ["invoice_no", "invoice_date", "taxable_value", "vendor_gstin"]
inc = {}
for r in pr.itertuples():
    m = [c for c in miss_cols if pd.isna(getattr(r, c))]
    if m: inc[r.pr_id] = m
for r in pr.itertuples():
    v = vinfo.loc[r.vendor_id]
    if r.pr_id in dup: add("purchase_register", r.pr_id, "DUPLICATE_INVOICE")
    if r.pr_id in inc: add("purchase_register", r.pr_id, "FIELD_MISSING", ", ".join(inc[r.pr_id]))
    if not pd.isna(r.taxable_value) and abs(r.tax - r.taxable_value * r.gst_rate / 100) > TOL:
        add("purchase_register", r.pr_id, "TAX_AMOUNT_WRONG", f"booked {r.tax:.2f}, expected {r.taxable_value * r.gst_rate / 100:.2f}")
    if (v.state_code == HOME and r.igst > 0) or (v.state_code != HOME and r.cgst + r.sgst > 0):
        add("purchase_register", r.pr_id, "TAX_TYPE_WRONG", f"supplier state {v.state_code}")
    if r.expense_category != v.default_category: add("purchase_register", r.pr_id, "CATEGORY_MISMATCH", f"booked {r.expense_category}, vendor is {v.default_category}")

# ---- GSTR-2B match ----
g2["taxable_value"] = g2.taxable_value.astype(float); g2["total_tax"] = g2.total_tax.astype(float)
g2k = g2.set_index(["supplier_gstin", "invoice_no"])
assert g2k.index.is_unique
status = {}
for r in pr.itertuples():
    if r.pr_id in dup: s = "EXCLUDED_DUPLICATE"
    elif r.pr_id in inc: s = "EXCLUDED_INCOMPLETE"
    elif (r.vendor_gstin, r.invoice_no) not in g2k.index: s = "MISSING_IN_2B"
    else:
        b = g2k.loc[(r.vendor_gstin, r.invoice_no)]
        s = "MATCHED" if abs(r.taxable_value - b.taxable_value) <= TOL and abs(r.tax - b.total_tax) <= TOL else "AMOUNT_MISMATCH"
    status[r.pr_id] = s
    if s in ("MISSING_IN_2B", "AMOUNT_MISMATCH"): add("purchase_register", r.pr_id, s)
prk = set(zip(pr.vendor_gstin, pr.invoice_no))
for b in g2.itertuples():
    if (b.supplier_gstin, b.invoice_no) not in prk: add("gstr_2b", b.b2b_id, "NOT_IN_BOOKS")

# ---- payments ----
pg = pm.groupby(["vendor_id", "invoice_no"]).agg(n=("payment_id", "size"), paid=("amount_paid", "sum"), tds=("tds_deducted", "sum"))
pay_status = {}
for r in pr.itertuples():
    if r.pr_id in dup: s = "EXCLUDED_DUPLICATE"
    elif pd.isna(r.invoice_no): s = "CANNOT_LINK"
    elif (r.vendor_id, r.invoice_no) in pg.index:
        g = pg.loc[(r.vendor_id, r.invoice_no)]
        if g.n > 1: s = "PAID_TWICE"
        elif pd.isna(r.total_amount): s = "CANNOT_CHECK"
        else:
            d = g.paid + g.tds - r.total_amount
            s = "PAID_OK" if abs(d) <= TOL else ("UNDERPAID" if d < 0 else "OVERPAID")
    else:
        if pd.isna(r.invoice_date): s = "UNPAID_NO_DATE"
        else:
            due = pd.Timestamp(r.invoice_date) + pd.Timedelta(days=int(vinfo.loc[r.vendor_id].payment_terms_days))
            s = "UNPAID_OVERDUE" if due < ASOF else "UNPAID_NOT_DUE"
    pay_status[r.pr_id] = s
    if s in ("PAID_TWICE", "UNDERPAID", "OVERPAID", "UNPAID_OVERDUE"): add("purchase_register", r.pr_id, s)
prv = pr.dropna(subset=["invoice_no"]).drop_duplicates(["vendor_id", "invoice_no"]).set_index(["vendor_id", "invoice_no"])
for p in pm.itertuples():
    if (p.vendor_id, p.invoice_no) not in prv.index: add("payments", p.payment_id, "PAYMENT_NOT_LINKED"); continue
    if vinfo.loc[p.vendor_id].default_category in TDS_CATS and p.tds_deducted == 0: add("payments", p.payment_id, "TDS_NOT_DEDUCTED")

res = pd.DataFrame(out)
res.to_csv("answer_key/expected_results.csv", index=False)
pr["gst_2b_status"] = pr.pr_id.map(status); pr["payment_status"] = pr.pr_id.map(pay_status)
pr[["pr_id", "gst_2b_status", "payment_status"]].to_csv("answer_key/invoice_status.csv", index=False)
summ = res.groupby(["table", "check"]).size().rename("count").reset_index()
summ.to_csv("answer_key/expected_counts.csv", index=False)
print(summ.to_string(index=False))
print("\n2B status:", pr.gst_2b_status.value_counts().to_dict()); print("payment status:", pr.payment_status.value_counts().to_dict())
m2b = pr.gst_2b_status == "MISSING_IN_2B"; print("ITC at risk (missing in 2B):", round(pr.loc[m2b, "tax"].sum(), 2))

# every planted error must be found by the matching check
pl = pd.read_csv("answer_key/planted_errors.csv", keep_default_na=False)
MAP = {"GSTIN_MISSING": "GSTIN_MISSING", "GSTIN_INVALID": "GSTIN_INVALID", "PAN_MISMATCH": "PAN_MISMATCH", "DUPLICATE_VENDOR": "DUPLICATE_VENDOR",
       "DUPLICATE_INVOICE": "DUPLICATE_INVOICE", "FIELD_MISSING": "FIELD_MISSING", "TAX_AMOUNT_WRONG": "TAX_AMOUNT_WRONG", "TAX_TYPE_WRONG": "TAX_TYPE_WRONG",
       "CATEGORY_MISMATCH": "CATEGORY_MISMATCH", "NOT_IN_2B": "MISSING_IN_2B", "2B_AMOUNT_DIFFERS": "AMOUNT_MISMATCH", "NOT_IN_BOOKS": "NOT_IN_BOOKS",
       "UNDERPAID": "UNDERPAID", "OVERPAID": "OVERPAID", "PAID_TWICE": "PAID_TWICE", "UNPAID_OVERDUE": "UNPAID_OVERDUE", "TDS_NOT_DEDUCTED": "TDS_NOT_DEDUCTED"}
found = set(zip(res.record_id, res.check))
miss = []
for p in pl.itertuples():
    if p.planted_error == "TDS_NOT_DEDUCTED":
        ok = any(c == "TDS_NOT_DEDUCTED" for _, c in found if _.startswith("PAY")) ; continue
    if (p.record_id, MAP[p.planted_error]) not in found: miss.append((p.record_id, p.planted_error))
print("\nplanted errors not found:", miss)
