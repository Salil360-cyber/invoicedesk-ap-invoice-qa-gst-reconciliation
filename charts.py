"""Draws the README charts from the summary tables that sql/07_report_tables.sql writes to outputs/.
The asserts stop the script if a table drifts from the answer key."""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.patches import Patch

OUT, IMG = Path("outputs"), Path("images"); IMG.mkdir(exist_ok=True)
BLUE, ORANGE, AQUA, GREY, INK = "#2a78d6", "#eb6834", "#1baf7a", "#9a9a95", "#222222"
SEV = {"High": ORANGE, "Medium": BLUE, "Low": GREY}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12})
LABEL = {"MISSING_IN_2B": "Missing in GSTR-2B", "AMOUNT_MISMATCH": "Amount differs from 2B", "NOT_IN_BOOKS": "In 2B, not in books",
         "DUPLICATE_INVOICE": "Duplicate invoice", "UNPAID_OVERDUE": "Unpaid past due date", "FIELD_MISSING": "Field missing",
         "CATEGORY_MISMATCH": "Category mismatch", "UNDERPAID": "Underpaid", "TAX_AMOUNT_WRONG": "Tax amount wrong",
         "TAX_TYPE_WRONG": "IGST vs CGST/SGST wrong", "OVERPAID": "Overpaid", "DUPLICATE_VENDOR": "Duplicate vendor (rows)",
         "TDS_NOT_DEDUCTED": "TDS not deducted", "PAID_TWICE": "Paid twice", "GSTIN_INVALID": "GSTIN invalid",
         "PAYMENT_NOT_LINKED": "Payment not linked", "GSTIN_MISSING": "GSTIN missing", "PAN_MISMATCH": "PAN mismatch"}

ex = pd.read_csv(OUT / "exceptions_by_check.csv")
key = pd.read_csv("answer_key/expected_counts.csv").set_index("check")["count"]
assert ex.set_index("check_name").exceptions.sort_index().equals(key.sort_index()), "exception counts differ from the answer key"
assert ex.exceptions.sum() == 279
g2 = pd.read_csv(OUT / "gst_2b_summary.csv").set_index("status")
pay = pd.read_csv(OUT / "payment_summary.csv").set_index("status")
money = pd.read_csv(OUT / "money_at_risk.csv")
sup = pd.read_csv(OUT / "missing_2b_by_supplier.csv")
assert g2.loc["MISSING_IN_2B", "invoices"] == 40 and round(g2.loc["MISSING_IN_2B", "tax_in_books"], 2) == 957674.90
assert sup.invoices.sum() == 40 and round(sup.tax_at_risk.sum(), 2) == 957674.90

def save(fig, name):
    fig.tight_layout(); fig.savefig(IMG / name, dpi=150, bbox_inches="tight"); plt.close(fig); print("saved", IMG / name)
lakh = lambda x: f"₹{x / 1e5:,.2f} lakh"

# 1. every exception, by check and severity
e = ex.sort_values("exceptions")
fig, ax = plt.subplots(figsize=(9, 6))
ax.barh([LABEL[c] for c in e.check_name], e.exceptions, color=[SEV[s] for s in e.severity])
for y, v in enumerate(e.exceptions): ax.text(v + 0.5, y, str(v), va="center", fontsize=9)
ax.set_xlabel("Exceptions"); ax.set_title("279 exceptions across 18 checks")
n = ex.groupby("severity").exceptions.sum()
ax.legend(handles=[Patch(color=SEV[s], label=f"{s} ({n[s]})") for s in ["High", "Medium", "Low"]], frameon=False, loc="lower right")
save(fig, "01_exceptions_by_check.png")

# 2. money involved in each issue
m = money.sort_values("amount_rs")
fig, ax = plt.subplots(figsize=(9, 4))
cols = [GREY if "caught before" in i else ORANGE for i in m.issue]
ax.barh(m.issue, m.amount_rs / 1e5, color=cols)
for y, v in enumerate(m.amount_rs): ax.text(v / 1e5 + 0.4, y, lakh(v), va="center", fontsize=9)
ax.set_xlim(0, m.amount_rs.max() / 1e5 * 1.28); ax.set_xlabel("₹ lakh")
ax.set_title("Money involved in each issue")
ax.legend(handles=[Patch(color=ORANGE, label="Money lost, at risk or overdue"), Patch(color=GREY, label="Stopped before payment")],
          frameon=False, loc="lower right")
save(fig, "02_money_at_risk.png")

# 3. GSTR-2B reconciliation
order = ["MATCHED", "AMOUNT_MISMATCH", "MISSING_IN_2B", "EXCLUDED_DUPLICATE", "EXCLUDED_INCOMPLETE"]
names = ["Matched", "Amount differs", "Missing in 2B", "Excluded:\nduplicate", "Excluded:\nincomplete"]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9))
cc = [AQUA, BLUE, ORANGE, GREY, GREY]
a1.bar(names, g2.loc[order, "invoices"], color=cc); a1.set_yscale("log"); a1.set_title("Invoices (log scale)", fontsize=10.5)
for i, v in enumerate(g2.loc[order, "invoices"]): a1.text(i, v * 1.12, f"{v:,}", ha="center", fontsize=9)
a1.set_ylim(10, 9000); a1.set_yticks([10, 100, 1000]); a1.set_yticklabels(["10", "100", "1,000"]); a1.tick_params(axis="x", labelsize=8.5)
nm = [o for o in order if o != "MATCHED"]
a2.bar([names[order.index(o)] for o in nm], g2.loc[nm, "tax_in_books"] / 1e5, color=cc[1:])
for i, v in enumerate(g2.loc[nm, "tax_in_books"]): a2.text(i, v / 1e5 + 0.15, lakh(v), ha="center", fontsize=8.5)
a2.set_title("GST in books outside 'Matched' (₹ lakh)", fontsize=10.5); a2.tick_params(axis="x", labelsize=8.5)
a2.set_ylim(0, g2.loc[nm, "tax_in_books"].max() / 1e5 * 1.2)
fig.suptitle(f"Purchase register vs GSTR-2B: {g2.loc['MATCHED', 'invoices']:,} of {g2.invoices.sum():,} invoices match", fontweight="bold")
save(fig, "03_gst_2b_reconciliation.png")

# 4. suppliers to chase
s = sup.head(10).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 4.3))
ax.barh(s.vendor_name, s.tax_at_risk / 1e5, color=ORANGE)
for y, (v, k) in enumerate(zip(s.tax_at_risk, s.invoices)): ax.text(v / 1e5 + 0.04, y, f"{lakh(v)} · {k} invoice{'s' if k > 1 else ''}", va="center", fontsize=9)
ax.set_xlim(0, s.tax_at_risk.max() / 1e5 * 1.45); ax.set_xlabel("GST credit at risk (₹ lakh)")
top = sup.head(10).tax_at_risk.sum() / sup.tax_at_risk.sum()
ax.set_title(f"Who to chase first: 10 suppliers hold {top:.0%} of the credit at risk")
save(fig, "04_missing_2b_chase_list.png")

# 5. payment status
po = ["UNPAID_OVERDUE", "UNDERPAID", "OVERPAID", "PAID_TWICE", "CANNOT_LINK", "CANNOT_CHECK", "UNPAID_NO_DATE"]
pn = ["Unpaid past\ndue date", "Underpaid", "Overpaid", "Paid twice", "Can't link\n(no inv. no.)", "Can't check\n(no amount)", "Unpaid,\nno date"]
fig, ax = plt.subplots(figsize=(9, 3.8))
ax.bar(pn, pay.loc[po, "invoices"], color=[BLUE, BLUE, ORANGE, ORANGE, GREY, GREY, GREY])
ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
ax.legend(handles=[Patch(color=ORANGE, label="High"), Patch(color=BLUE, label="Medium"), Patch(color=GREY, label="Low / can't assess")], frameon=False)
for i, v in enumerate(pay.loc[po, "invoices"]): ax.text(i, v + 0.4, str(v), ha="center", fontsize=9)
ax.set_ylabel("Invoices"); ax.tick_params(axis="x", labelsize=8.5)
ax.set_title(f"Payment problems ({pay.loc['PAID_OK', 'invoices']:,} invoices paid correctly, {pay.loc['UNPAID_NOT_DUE', 'invoices']} not yet due)")
save(fig, "05_payment_status.png")
