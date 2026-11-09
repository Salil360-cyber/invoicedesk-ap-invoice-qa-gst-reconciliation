"""InvoiceDesk: synthetic AP + GST data for a fictional company, with planted errors.
Company: Sahyadri Components Pvt Ltd (fictional), Pune, Maharashtra (GST state code 27).
Invoices: 1 Apr - 30 Sep 2026. Review date: 31 Oct 2026. Every name, PAN and GSTIN is made up.
Writes data/*.csv and data/planted_errors.csv (what was planted, used to prove the checks find them)."""
import random, string
from datetime import date, timedelta
import pandas as pd

R = random.Random(2026)
CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
def gst_checksum(s14):
    tot = 0
    for i, c in enumerate(s14):
        p = CH.index(c) * (1 if i % 2 == 0 else 2)
        tot += p // 36 + p % 36
    return CH[(36 - tot % 36) % 36]
def make_pan(kind="C"):
    return "".join(R.choices(string.ascii_uppercase, k=3)) + kind + R.choice(string.ascii_uppercase) + f"{R.randint(0, 9999):04d}" + R.choice(string.ascii_uppercase)
def make_gstin(state, pan):
    s14 = f"{state:02d}{pan}1Z"; return s14 + gst_checksum(s14)

STATES = {27: "Maharashtra", 29: "Karnataka", 24: "Gujarat", 7: "Delhi", 33: "Tamil Nadu", 36: "Telangana", 9: "Uttar Pradesh", 6: "Haryana"}
CATS = {  # category: (gst rate %, taxable value range, invoices per vendor per month)
    "Cloud & Software": (18, (8000, 250000), 2), "Professional Fees": (18, (15000, 300000), 2), "Rent": (18, (60000, 450000), 1),
    "Office Supplies": (18, (1500, 40000), 6), "Raw Materials": (18, (40000, 900000), 10), "Repairs & Maintenance": (18, (3000, 120000), 3),
    "Marketing": (18, (10000, 350000), 2), "Telecom": (18, (2000, 60000), 1), "Logistics": (12, (5000, 180000), 6), "Travel": (5, (2500, 90000), 5)}
TERMS = {"Rent": 15, "Telecom": 15, "Travel": 15, "Office Supplies": 30, "Cloud & Software": 30, "Marketing": 45,
         "Professional Fees": 30, "Repairs & Maintenance": 30, "Logistics": 45, "Raw Materials": 60}
W1 = ["Sahas", "Nimbus", "Vardhan", "Kaveri", "Indus", "Trident", "Prakash", "Shree", "Orbit", "Deccan", "Sapphire", "Ganga", "Ashoka", "Maruti",
      "Konkan", "Vertex", "Aarav", "Neel", "Bharat", "Unity", "Pinnacle", "Sahyog", "Aditya", "Lotus", "Zenith", "Matrix", "Pragati", "Sterling",
      "Riddhi", "Om", "Akash", "Swift", "Nova", "Crest", "Pawan", "Tara", "Meru", "Silver", "Coral", "Sigma"]
W2 = {"Cloud & Software": ["Cloud Services", "Softech", "Infosystems", "Digital Labs"], "Professional Fees": ["& Associates", "Consulting", "Legal LLP", "Advisors"],
      "Rent": ["Realty", "Estates", "Properties"], "Office Supplies": ["Stationers", "Office Mart", "Supplies"], "Raw Materials": ["Metals", "Polymers", "Castings", "Steel Traders"],
      "Repairs & Maintenance": ["Engineering Works", "Facility Services", "Electricals"], "Marketing": ["Media", "Creatives", "Ad Agency"],
      "Telecom": ["Telecom", "Broadband"], "Logistics": ["Logistics", "Roadways", "Freight Carriers"], "Travel": ["Travels", "Tours", "Holidays"]}
SUFFIX = ["Pvt Ltd", "Pvt Ltd", "Ltd", "LLP", "Pvt Ltd"]
NCAT = {"Cloud & Software": 8, "Professional Fees": 8, "Rent": 3, "Office Supplies": 10, "Raw Materials": 20, "Repairs & Maintenance": 10,
        "Marketing": 8, "Telecom": 4, "Logistics": 14, "Travel": 10}  # 95 vendors

# ---------------- vendor master ----------------
vendors, used = [], set()
for cat, n in NCAT.items():
    for _ in range(n):
        while True:
            name = f"{R.choice(W1)} {R.choice(W2[cat])}"
            if name not in used: used.add(name); break
        name = name if name.endswith("LLP") or "&" in name else f"{name} {R.choice(SUFFIX)}"
        st = 27 if R.random() < 0.6 or cat in ("Rent",) else R.choice([s for s in STATES if s != 27])
        pan = make_pan("F" if "LLP" in name or "&" in name else "C")
        vendors.append(dict(vendor_id=None, vendor_name=name, pan=pan, gstin=make_gstin(st, pan), state_code=f"{st:02d}",
                            state_name=STATES[st], payment_terms_days=TERMS[cat], default_category=cat))
R.shuffle(vendors)
for i, v in enumerate(vendors, 1): v["vendor_id"] = f"V{i:03d}"
true_gstin = {v["vendor_id"]: v["gstin"] for v in vendors}  # what the supplier actually uses in GSTR-2B
planted = []
def plant(table, rid, err, note=""): planted.append(dict(table=table, record_id=rid, planted_error=err, note=note))

pool = vendors[:]; R.shuffle(pool)
bad_vendors = []
for v in pool[0:4]:   # GSTIN missing in master
    v["gstin"] = ""; plant("vendor_master", v["vendor_id"], "GSTIN_MISSING"); bad_vendors.append(v["vendor_id"])
for v, how in zip(pool[4:9], ["short", "long", "state00", "notZ", "statealpha"]):  # invalid GSTIN typed in master
    g = v["gstin"]
    g = {"short": g[:14], "long": g + "7", "state00": "00" + g[2:], "notZ": g[:13] + "X" + g[14], "statealpha": "M" + g[1:]}[how]
    v["gstin"] = g; plant("vendor_master", v["vendor_id"], "GSTIN_INVALID", how); bad_vendors.append(v["vendor_id"])
for v in pool[9:12]:  # PAN column typo (GSTIN is right)
    p = v["pan"]; i = R.randint(5, 8); v["pan"] = p[:i] + str((int(p[i]) + 3) % 10) + p[i+1:]
    plant("vendor_master", v["vendor_id"], "PAN_MISMATCH")
dup_pairs = []
nid = len(vendors)
VARIANT = lambda n: n.replace("Pvt Ltd", "Private Limited") if "Pvt Ltd" in n else (n.replace("Ltd", "Limited") if n.endswith("Ltd") else n.upper())
for v in pool[12:16]:  # same supplier created twice under a name variant
    nid += 1; d = dict(v); d["vendor_id"] = f"V{nid:03d}"; d["vendor_name"] = VARIANT(v["vendor_name"])
    vendors.append(d); true_gstin[d["vendor_id"]] = true_gstin[v["vendor_id"]]; dup_pairs.append((v["vendor_id"], d["vendor_id"]))
    plant("vendor_master", d["vendor_id"], "DUPLICATE_VENDOR", f"same PAN as {v['vendor_id']}")
vm = pd.DataFrame(vendors)
vmap = {v["vendor_id"]: v for v in vendors}

# ---------------- purchase register ----------------
start, end, asof = date(2026, 4, 1), date(2026, 9, 30), date(2026, 10, 31)
rows, seq = [], {}
dup_of = {b: a for a, b in dup_pairs}
for v in vendors:
    if v["vendor_id"] in dup_of: continue  # duplicate vendor records get invoices moved to them below
    cat = v["default_category"]; rate, (lo, hi), per = CATS[cat]
    for m in range(4, 10):
        for _ in range(R.randint(max(1, per - 1), per + 1)):
            d0 = date(2026, m, 1); dd = d0 + timedelta(days=R.randint(0, 27))
            k = v["vendor_id"]; seq[k] = seq.get(k, 0) + 1
            prefix = "".join(w[0] for w in v["vendor_name"].split()[:2]).upper()
            taxable = round(R.uniform(lo, hi) / (1 if R.random() < .7 else 3), 2)
            rows.append(dict(vendor_id=k, invoice_no=f"{prefix}/26-27/{seq[k]:04d}", invoice_date=dd, expense_category=cat,
                             taxable_value=taxable, gst_rate=rate))
R.shuffle(rows)
rows.sort(key=lambda r: r["invoice_date"])
for a, b in dup_pairs:  # some invoices of the original vendor were booked under the duplicate vendor id
    mine = [r for r in rows if r["vendor_id"] == a]
    for r in R.sample(mine, len(mine) // 2): r["vendor_id"] = b
def taxes(r, intra):
    t = round(r["taxable_value"] * r["gst_rate"] / 100, 2)
    if intra: c = round(t / 2, 2); return c, round(t - c, 2), 0.0
    return 0.0, 0.0, t
for r in rows:
    v = vmap[r["vendor_id"]]; r["vendor_name"] = v["vendor_name"]; r["vendor_gstin"] = true_gstin[r["vendor_id"]]  # keyed from the invoice itself
    r["cgst"], r["sgst"], r["igst"] = taxes(r, v["state_code"] == "27")
for i, r in enumerate(rows, 1): r["pr_id"] = f"PR{i:05d}"; r["booked_on"] = r["invoice_date"] + timedelta(days=R.randint(1, 6))

clean = [r for r in rows if r["vendor_id"] not in bad_vendors and r["vendor_id"] not in dup_of]
picks = R.sample(clean, 260); P = iter(picks)
nx = lambda: next(P)
tax_calc, tax_type, miscat = [], [], []
for _ in range(15):  # tax worked out at the wrong rate or wrong arithmetic
    r = nx(); f = R.choice([12/18, 1.1, 0.5]) if r["gst_rate"] == 18 else R.choice([1.5, 0.8])
    r["cgst"], r["sgst"], r["igst"] = [round(x * f, 2) for x in (r["cgst"], r["sgst"], r["igst"])]
    tax_calc.append(r["pr_id"]); plant("purchase_register", r["pr_id"], "TAX_AMOUNT_WRONG")
for _ in range(10):  # IGST charged on a Maharashtra supplier, or CGST+SGST on an out-of-state supplier
    r = nx(); t = round(r["cgst"] + r["sgst"] + r["igst"], 2)
    if r["igst"] > 0: c = round(t / 2, 2); r["cgst"], r["sgst"], r["igst"] = c, round(t - c, 2), 0.0
    else: r["cgst"], r["sgst"], r["igst"] = 0.0, 0.0, t
    tax_type.append(r["pr_id"]); plant("purchase_register", r["pr_id"], "TAX_TYPE_WRONG")
for _ in range(20):
    r = nx(); r["expense_category"] = R.choice([c for c in CATS if c != r["expense_category"] and CATS[c][0] == r["gst_rate"]] or [c for c in CATS if c != r["expense_category"]])
    miscat.append(r["pr_id"]); plant("purchase_register", r["pr_id"], "CATEGORY_MISMATCH")
for r in rows: r["total_amount"] = round(r["taxable_value"] + r["cgst"] + r["sgst"] + r["igst"], 2)

# missing fields (the true values are kept for GSTR-2B and payments)
truth = {r["pr_id"]: dict(r) for r in rows}
incomplete = []
for fld in ["invoice_no", "invoice_date", "taxable_value", "vendor_gstin"]:
    for _ in range(5):
        r = nx()
        if fld == "taxable_value": r["taxable_value"] = None
        else: r[fld] = None
        incomplete.append(r["pr_id"]); plant("purchase_register", r["pr_id"], "FIELD_MISSING", fld)
# duplicates: 18 re-booked under the same vendor, 6 re-booked under the duplicate vendor record
dups = []
base = [r for r in rows if r["pr_id"] not in incomplete and r["pr_id"] not in tax_calc + tax_type + miscat and r["vendor_id"] not in bad_vendors]
for r in R.sample([x for x in base if x["vendor_id"] not in dup_of and x["vendor_id"] not in dict(dup_pairs)], 18):
    d = dict(r); d["booked_on"] = r["booked_on"] + timedelta(days=R.randint(5, 40)); dups.append(d)
for a, b in dup_pairs:
    for r in R.sample([x for x in base if x["vendor_id"] == a], 1 if a != dup_pairs[0][0] else 3):
        d = dict(r); d["vendor_id"] = b; d["vendor_name"] = vmap[b]["vendor_name"]; d["booked_on"] = r["booked_on"] + timedelta(days=R.randint(5, 40)); dups.append(d)
nxt = len(rows)
for d in dups:
    nxt += 1; d["pr_id"] = f"PR{nxt:05d}"; plant("purchase_register", d["pr_id"], "DUPLICATE_INVOICE"); rows.append(d)
rows.sort(key=lambda r: (r["booked_on"], r["pr_id"]))
remap = {}
for i, r in enumerate(rows, 1): remap[r["pr_id"]] = f"PR{i:05d}"; r["pr_id"] = remap[r["pr_id"]]
for p in planted:
    if p["table"] == "purchase_register": p["record_id"] = remap[p["record_id"]]
truth = {remap[k]: dict(v, pr_id=remap[k]) for k, v in truth.items()}
incomplete = [remap[x] for x in incomplete]; tax_calc = [remap[x] for x in tax_calc]; tax_type = [remap[x] for x in tax_type]; miscat = [remap[x] for x in miscat]
pr = pd.DataFrame(rows)[["pr_id", "booked_on", "vendor_id", "vendor_name", "vendor_gstin", "invoice_no", "invoice_date", "expense_category",
                         "taxable_value", "gst_rate", "cgst", "sgst", "igst", "total_amount"]]
pr.loc[pr.taxable_value.isna(), "total_amount"] = None

# ---------------- GSTR-2B (what suppliers reported to the GST portal) ----------------
orig = [truth[r["pr_id"]] if r["pr_id"] in truth else None for r in rows]
orig = [o for o in orig if o is not None]  # originals only, true values
def correct_tax(o):
    t = round(o["taxable_value"] * o["gst_rate"] / 100, 2)
    return t
b2 = []
skip = set(R.sample([o["pr_id"] for o in orig if o["pr_id"] not in incomplete + tax_calc + tax_type and o["vendor_id"] not in bad_vendors], 40))
for p in skip: plant("purchase_register", p, "NOT_IN_2B", "supplier did not report it")
mism = set(R.sample([o["pr_id"] for o in orig if o["pr_id"] not in skip and o["pr_id"] not in incomplete + tax_calc + tax_type and o["vendor_id"] not in bad_vendors], 25))
for p in mism: plant("purchase_register", p, "2B_AMOUNT_DIFFERS")
for o in orig:
    if o["pr_id"] in skip: continue
    tv = o["taxable_value"]
    if o["pr_id"] in mism: tv = round(tv * R.choice([0.9, 0.95, 1.05, 1.1, 0.5]), 2)
    tax = round(tv * o["gst_rate"] / 100, 2)
    b2.append(dict(supplier_gstin=true_gstin[o["vendor_id"]], supplier_name=vmap[o["vendor_id"]]["vendor_name"] if o["vendor_id"] not in dup_of else vmap[dup_of[o["vendor_id"]]]["vendor_name"],
                   invoice_no=o["invoice_no"], invoice_date=o["invoice_date"], taxable_value=tv, total_tax=tax,
                   return_period=o["invoice_date"].strftime("%Y-%m")))
good_v = [v for v in vendors if v["vendor_id"] not in bad_vendors and v["vendor_id"] not in dup_of]
for i in range(15):  # supplier reported an invoice the company never booked
    v = R.choice(good_v); cat = v["default_category"]; rate, (lo, hi), _ = CATS[cat]
    prefix = "".join(w[0] for w in v["vendor_name"].split()[:2]).upper(); dd = start + timedelta(days=R.randint(0, 182))
    tv = round(R.uniform(lo, hi) / 2, 2)
    inv = f"{prefix}/26-27/{9000 + i:04d}"
    b2.append(dict(supplier_gstin=v["gstin"], supplier_name=v["vendor_name"], invoice_no=inv, invoice_date=dd, taxable_value=tv,
                   total_tax=round(tv * rate / 100, 2), return_period=dd.strftime("%Y-%m")))
    plant("gstr_2b", inv, "NOT_IN_BOOKS")
R.shuffle(b2); b2.sort(key=lambda x: (x["return_period"], x["supplier_gstin"], x["invoice_no"]))
g2b = pd.DataFrame(b2); g2b.insert(0, "b2b_id", [f"B{i:05d}" for i in range(1, len(g2b) + 1)])
for p in planted:
    if p["planted_error"] == "NOT_IN_BOOKS": p["record_id"] = g2b.loc[g2b.invoice_no == p["record_id"], "b2b_id"].iloc[0]

# ---------------- payments ----------------
TDS_CATS = ("Professional Fees", "Rent")
pays = []
unpaid_overdue = set(R.sample([o["pr_id"] for o in orig if o["invoice_date"] < date(2026, 7, 15) and o["pr_id"] not in incomplete], 20))
for p in unpaid_overdue: plant("purchase_register", p, "UNPAID_OVERDUE")
pool2 = [o for o in orig if o["pr_id"] not in unpaid_overdue and o["pr_id"] not in incomplete + tax_calc + tax_type]
under = set(R.sample([o["pr_id"] for o in pool2], 18)); rest = [o for o in pool2 if o["pr_id"] not in under]
over = set(R.sample([o["pr_id"] for o in rest], 8)); rest = [o for o in rest if o["pr_id"] not in over]
twice = set(R.sample([o["pr_id"] for o in rest], 6)); rest = [o for o in rest if o["pr_id"] not in twice]
notds = set(R.sample([o["pr_id"] for o in rest if vmap[o["vendor_id"]]["default_category"] in TDS_CATS], 8))
for s, e in [(under, "UNDERPAID"), (over, "OVERPAID"), (twice, "PAID_TWICE"), (notds, "TDS_NOT_DEDUCTED")]:
    for p in s: plant("purchase_register", p, e)
for o in orig:
    if o["pr_id"] in unpaid_overdue: continue
    due = o["invoice_date"] + timedelta(days=vmap[o["vendor_id"]]["payment_terms_days"])
    if due > asof and R.random() < 0.85 and o["pr_id"] not in under | over | twice | notds: continue   # not yet due: most still unpaid
    total = round(o["taxable_value"] + round(o["taxable_value"] * o["gst_rate"] / 100, 2), 2) if o["pr_id"] not in tax_calc else None
    rec = truth[o["pr_id"]]; total = round(rec["taxable_value"] + rec["cgst"] + rec["sgst"] + rec["igst"], 2)
    tds = round(o["taxable_value"] * 0.10, 2) if vmap[o["vendor_id"]]["default_category"] in TDS_CATS and o["pr_id"] not in notds else 0.0
    net = round(total - tds, 2)
    if o["pr_id"] in under: net = round(net - R.choice([round(net * 0.1, 2), 500.0, round(rec["cgst"] + rec["sgst"] + rec["igst"], 2)]), 2)
    if o["pr_id"] in over: net = round(net + R.choice([1000.0, round(net * 0.05, 2), 2500.0]), 2)
    pd_ = min(due + timedelta(days=R.randint(-10, 12)), asof); pd_ = max(pd_, o["invoice_date"] + timedelta(days=2))
    pays.append(dict(vendor_id=o["vendor_id"], invoice_no=o["invoice_no"], payment_date=pd_, amount_paid=net, tds_deducted=tds))
    if o["pr_id"] in twice:
        pays.append(dict(vendor_id=o["vendor_id"], invoice_no=o["invoice_no"], payment_date=min(pd_ + timedelta(days=R.randint(3, 20)), asof), amount_paid=net, tds_deducted=tds))
pays.sort(key=lambda x: (x["payment_date"], x["vendor_id"]))
pm = pd.DataFrame(pays); pm.insert(0, "payment_id", [f"PAY{i:05d}" for i in range(1, len(pm) + 1)])
pm.insert(len(pm.columns), "bank_reference", [f"UTR26{R.randint(10**9, 10**10 - 1)}" for _ in range(len(pm))])

cat = pd.DataFrame([dict(expense_category=c, gst_rate=v[0], tds_rate=10 if c in TDS_CATS else 0) for c, v in CATS.items()])
vm.to_csv("data/vendor_master.csv", index=False); pr.to_csv("data/purchase_register.csv", index=False)
g2b.to_csv("data/gstr_2b.csv", index=False); pm.to_csv("data/payments.csv", index=False); cat.to_csv("data/category_rates.csv", index=False)
pd.DataFrame(planted).sort_values(["table", "planted_error", "record_id"]).to_csv("answer_key/planted_errors.csv", index=False)
print(f"vendors {len(vm)}, invoices {len(pr)}, gstr_2b {len(g2b)}, payments {len(pm)}, planted {len(planted)}")
print(pd.DataFrame(planted).planted_error.value_counts().to_string())
