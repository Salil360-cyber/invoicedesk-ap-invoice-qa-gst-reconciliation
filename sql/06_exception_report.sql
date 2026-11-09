-- InvoiceDesk 06: one exception report with severity, likely cause and next action
DROP TABLE IF EXISTS exception_report;
CREATE TABLE exception_report AS
WITH e AS (
  SELECT 'vendor_master' AS source, vendor_id AS record_id, check_name, detail FROM vendor_checks
  UNION ALL SELECT 'purchase_register', pr_id, check_name, detail FROM invoice_checks
  UNION ALL SELECT 'purchase_register', pr_id, status, NULL FROM gst_2b_match WHERE status IN ('MISSING_IN_2B', 'AMOUNT_MISMATCH')
  UNION ALL SELECT 'gstr_2b', b.b2b_id, 'NOT_IN_BOOKS', b.invoice_no FROM gstr_2b b
            WHERE NOT EXISTS (SELECT 1 FROM purchase_register p WHERE p.vendor_gstin = b.supplier_gstin AND p.invoice_no = b.invoice_no)
  UNION ALL SELECT 'purchase_register', pr_id, status, NULL FROM payment_match WHERE status IN ('PAID_TWICE', 'UNDERPAID', 'OVERPAID', 'UNPAID_OVERDUE')
  UNION ALL SELECT 'payments', payment_id, check_name, detail FROM payment_checks)
SELECT e.*,
  CASE WHEN check_name IN ('DUPLICATE_INVOICE', 'PAID_TWICE', 'OVERPAID', 'MISSING_IN_2B', 'GSTIN_MISSING', 'GSTIN_INVALID', 'TAX_AMOUNT_WRONG') THEN 'High'
       WHEN check_name IN ('CATEGORY_MISMATCH', 'NOT_IN_BOOKS', 'PAYMENT_NOT_LINKED') THEN 'Low'
       ELSE 'Medium' END AS severity,
  CASE check_name
    WHEN 'GSTIN_MISSING'      THEN 'GSTIN never captured when the vendor was created'
    WHEN 'GSTIN_INVALID'      THEN 'GSTIN typed wrongly in the vendor master'
    WHEN 'PAN_MISMATCH'       THEN 'PAN typed wrongly in the vendor master'
    WHEN 'DUPLICATE_VENDOR'   THEN 'Same supplier created twice under a different name'
    WHEN 'DUPLICATE_INVOICE'  THEN 'Same invoice booked again (often under a duplicate vendor record)'
    WHEN 'FIELD_MISSING'      THEN 'Field left blank at data entry'
    WHEN 'TAX_AMOUNT_WRONG'   THEN 'Tax worked out at the wrong rate'
    WHEN 'TAX_TYPE_WRONG'     THEN 'IGST and CGST/SGST mixed up for the supplier''s state'
    WHEN 'CATEGORY_MISMATCH'  THEN 'Expense coded to the wrong category'
    WHEN 'MISSING_IN_2B'      THEN 'Supplier has not reported the invoice on the GST portal'
    WHEN 'AMOUNT_MISMATCH'    THEN 'Amount booked differs from what the supplier reported'
    WHEN 'NOT_IN_BOOKS'       THEN 'Invoice reported by supplier but not booked, or booked with missing details'
    WHEN 'PAID_TWICE'         THEN 'Invoice paid in two separate payment runs'
    WHEN 'UNDERPAID'          THEN 'Short payment'
    WHEN 'OVERPAID'           THEN 'Excess payment'
    WHEN 'UNPAID_OVERDUE'     THEN 'Payment not released after the due date'
    WHEN 'PAYMENT_NOT_LINKED' THEN 'Payment made against an invoice with no matching booking'
    WHEN 'TDS_NOT_DEDUCTED'   THEN 'TDS skipped on a professional fee or rent payment' END AS likely_cause,
  CASE check_name
    WHEN 'GSTIN_MISSING'      THEN 'Get the GSTIN certificate from the vendor and update the master'
    WHEN 'GSTIN_INVALID'      THEN 'Correct the GSTIN from the vendor''s certificate'
    WHEN 'PAN_MISMATCH'       THEN 'Correct the PAN to match the GSTIN'
    WHEN 'DUPLICATE_VENDOR'   THEN 'Merge into one vendor record and block the other'
    WHEN 'DUPLICATE_INVOICE'  THEN 'Reverse the second booking before it is paid'
    WHEN 'FIELD_MISSING'      THEN 'Fill the field from the invoice copy'
    WHEN 'TAX_AMOUNT_WRONG'   THEN 'Recalculate tax and correct the entry'
    WHEN 'TAX_TYPE_WRONG'     THEN 'Rebook with the correct tax type'
    WHEN 'CATEGORY_MISMATCH'  THEN 'Reclassify to the vendor''s category or confirm the exception'
    WHEN 'MISSING_IN_2B'      THEN 'Ask the supplier to file; hold the credit until it appears'
    WHEN 'AMOUNT_MISMATCH'    THEN 'Compare with the invoice copy and ask the supplier to amend'
    WHEN 'NOT_IN_BOOKS'       THEN 'Check for an unbooked invoice and book it if valid'
    WHEN 'PAID_TWICE'         THEN 'Recover the extra payment or adjust against the next bill'
    WHEN 'UNDERPAID'          THEN 'Confirm the reason and pay the balance'
    WHEN 'OVERPAID'           THEN 'Recover or adjust the excess'
    WHEN 'UNPAID_OVERDUE'     THEN 'Release payment or record why it is on hold'
    WHEN 'PAYMENT_NOT_LINKED' THEN 'Find the invoice and complete the booking'
    WHEN 'TDS_NOT_DEDUCTED'   THEN 'Recover TDS from the vendor and deposit it' END AS next_action
FROM e;

SELECT severity, check_name, COUNT(*) AS exceptions FROM exception_report GROUP BY 1, 2 ORDER BY 1, 3 DESC;
SELECT severity, COUNT(*) FROM exception_report GROUP BY 1 ORDER BY 1;
\copy (SELECT * FROM exception_report ORDER BY CASE severity WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, check_name, record_id) TO 'outputs/exception_report.csv' CSV HEADER
