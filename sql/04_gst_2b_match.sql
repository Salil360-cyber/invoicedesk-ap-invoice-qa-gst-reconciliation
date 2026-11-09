-- InvoiceDesk 04: purchase register vs GSTR-2B
-- Input tax credit can only be claimed for invoices the supplier has reported in GSTR-2B.
DROP VIEW IF EXISTS gst_2b_match CASCADE;
CREATE VIEW gst_2b_match AS
SELECT f.pr_id, f.vendor_id, f.vendor_gstin, f.invoice_no, f.taxable_value, f.tax,
       b.b2b_id, b.taxable_value AS b2b_taxable, b.total_tax AS b2b_tax,
       CASE WHEN f.is_duplicate          THEN 'EXCLUDED_DUPLICATE'
            WHEN f.missing_fields <> ''  THEN 'EXCLUDED_INCOMPLETE'
            WHEN b.b2b_id IS NULL        THEN 'MISSING_IN_2B'
            WHEN ABS(f.taxable_value - b.taxable_value) > 1 OR ABS(f.tax - b.total_tax) > 1 THEN 'AMOUNT_MISMATCH'
            ELSE 'MATCHED' END AS status
FROM pr_flags f
LEFT JOIN gstr_2b b ON b.supplier_gstin = f.vendor_gstin AND b.invoice_no = f.invoice_no;

SELECT status, COUNT(*) AS invoices, SUM(tax) AS tax_in_books FROM gst_2b_match GROUP BY 1 ORDER BY 1;

-- credit at risk: tax on invoices the supplier has not reported
SELECT SUM(tax) AS itc_at_risk FROM gst_2b_match WHERE status = 'MISSING_IN_2B';

-- the other side: invoices suppliers reported that are not in our books
SELECT b.b2b_id, b.supplier_name, b.invoice_no, b.total_tax
FROM gstr_2b b
WHERE NOT EXISTS (SELECT 1 FROM purchase_register p WHERE p.vendor_gstin = b.supplier_gstin AND p.invoice_no = b.invoice_no)
ORDER BY b.total_tax DESC;
