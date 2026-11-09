-- InvoiceDesk 01: create the tables and load the CSV files
-- Run from the project folder:  psql -d invoicedesk -f sql/01_load.sql
DROP TABLE IF EXISTS vendor_master, purchase_register, gstr_2b, payments, category_rates CASCADE;

CREATE TABLE vendor_master (
  vendor_id TEXT PRIMARY KEY, vendor_name TEXT, pan TEXT, gstin TEXT, state_code TEXT, state_name TEXT,
  payment_terms_days INT, default_category TEXT);
CREATE TABLE purchase_register (
  pr_id TEXT PRIMARY KEY, booked_on DATE, vendor_id TEXT, vendor_name TEXT, vendor_gstin TEXT, invoice_no TEXT,
  invoice_date DATE, expense_category TEXT, taxable_value NUMERIC(14,2), gst_rate NUMERIC(5,2),
  cgst NUMERIC(14,2), sgst NUMERIC(14,2), igst NUMERIC(14,2), total_amount NUMERIC(14,2));
CREATE TABLE gstr_2b (
  b2b_id TEXT PRIMARY KEY, supplier_gstin TEXT, supplier_name TEXT, invoice_no TEXT, invoice_date DATE,
  taxable_value NUMERIC(14,2), total_tax NUMERIC(14,2), return_period TEXT);
CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY, vendor_id TEXT, invoice_no TEXT, payment_date DATE,
  amount_paid NUMERIC(14,2), tds_deducted NUMERIC(14,2), bank_reference TEXT);
CREATE TABLE category_rates (expense_category TEXT PRIMARY KEY, gst_rate NUMERIC(5,2), tds_rate NUMERIC(5,2));

-- empty cells load as NULL
\copy vendor_master     FROM 'data/vendor_master.csv'     CSV HEADER
\copy purchase_register FROM 'data/purchase_register.csv' CSV HEADER
\copy gstr_2b           FROM 'data/gstr_2b.csv'           CSV HEADER
\copy payments          FROM 'data/payments.csv'          CSV HEADER
\copy category_rates    FROM 'data/category_rates.csv'    CSV HEADER

-- row counts: expect 99 / 2,884 / 2,835 / 2,625 / 10
SELECT 'vendor_master' AS tbl, COUNT(*) FROM vendor_master UNION ALL
SELECT 'purchase_register', COUNT(*) FROM purchase_register UNION ALL
SELECT 'gstr_2b', COUNT(*) FROM gstr_2b UNION ALL
SELECT 'payments', COUNT(*) FROM payments UNION ALL
SELECT 'category_rates', COUNT(*) FROM category_rates;
