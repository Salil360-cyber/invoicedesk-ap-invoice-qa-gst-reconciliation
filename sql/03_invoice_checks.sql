-- InvoiceDesk 03: purchase register checks
DROP VIEW IF EXISTS invoice_checks CASCADE;
DROP VIEW IF EXISTS pr_flags CASCADE;
CREATE VIEW pr_flags AS
SELECT p.*,
       (cgst + sgst + igst) AS tax,
       -- duplicate = same supplier GSTIN + invoice number + total already booked earlier
       ROW_NUMBER() OVER (PARTITION BY vendor_gstin, invoice_no, total_amount ORDER BY booked_on, pr_id) > 1
         AND vendor_gstin IS NOT NULL AND invoice_no IS NOT NULL                      AS is_duplicate,
       CONCAT_WS(', ', CASE WHEN invoice_no    IS NULL THEN 'invoice_no' END,
                       CASE WHEN invoice_date  IS NULL THEN 'invoice_date' END,
                       CASE WHEN taxable_value IS NULL THEN 'taxable_value' END,
                       CASE WHEN vendor_gstin  IS NULL THEN 'vendor_gstin' END)       AS missing_fields,
       v.state_code, v.default_category, v.payment_terms_days
FROM purchase_register p JOIN vendor_master v USING (vendor_id);

CREATE VIEW invoice_checks AS
SELECT pr_id, 'DUPLICATE_INVOICE' AS check_name, NULL AS detail FROM pr_flags WHERE is_duplicate
UNION ALL
SELECT pr_id, 'FIELD_MISSING', missing_fields FROM pr_flags WHERE missing_fields <> ''
UNION ALL
SELECT pr_id, 'TAX_AMOUNT_WRONG', 'booked ' || tax || ', expected ' || ROUND(taxable_value * gst_rate / 100, 2)
FROM pr_flags WHERE ABS(tax - taxable_value * gst_rate / 100) > 1
UNION ALL
-- Maharashtra (27) supplier -> CGST + SGST; any other state -> IGST
SELECT pr_id, 'TAX_TYPE_WRONG', 'supplier state ' || state_code
FROM pr_flags WHERE (state_code = '27' AND igst > 0) OR (state_code <> '27' AND cgst + sgst > 0)
UNION ALL
SELECT pr_id, 'CATEGORY_MISMATCH', 'booked ' || expense_category || ', vendor is ' || default_category
FROM pr_flags WHERE expense_category <> default_category;

SELECT check_name, COUNT(*) FROM invoice_checks GROUP BY 1 ORDER BY 1;
