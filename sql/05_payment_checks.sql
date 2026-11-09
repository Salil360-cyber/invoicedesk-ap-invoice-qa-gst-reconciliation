-- InvoiceDesk 05: invoice vs payment, and TDS
-- Expected: amount_paid + tds_deducted = invoice total (Rs 1 tolerance). Review date: 31 Oct 2026.
DROP VIEW IF EXISTS payment_match CASCADE;
CREATE VIEW payment_match AS
WITH pay AS (
  SELECT vendor_id, invoice_no, COUNT(*) AS n, SUM(amount_paid) AS paid, SUM(tds_deducted) AS tds
  FROM payments GROUP BY 1, 2)
SELECT f.pr_id, f.vendor_id, f.invoice_no, f.total_amount, p.n, p.paid, p.tds,
       f.invoice_date + f.payment_terms_days AS due_date,
       CASE WHEN f.is_duplicate THEN 'EXCLUDED_DUPLICATE'
            WHEN f.invoice_no IS NULL THEN 'CANNOT_LINK'
            WHEN p.n > 1 THEN 'PAID_TWICE'
            WHEN p.n = 1 AND f.total_amount IS NULL THEN 'CANNOT_CHECK'
            WHEN p.n = 1 AND ABS(p.paid + p.tds - f.total_amount) <= 1 THEN 'PAID_OK'
            WHEN p.n = 1 AND p.paid + p.tds < f.total_amount THEN 'UNDERPAID'
            WHEN p.n = 1 THEN 'OVERPAID'
            WHEN f.invoice_date IS NULL THEN 'UNPAID_NO_DATE'
            WHEN f.invoice_date + f.payment_terms_days < DATE '2026-10-31' THEN 'UNPAID_OVERDUE'
            ELSE 'UNPAID_NOT_DUE' END AS status
FROM pr_flags f
LEFT JOIN pay p ON p.vendor_id = f.vendor_id AND p.invoice_no = f.invoice_no;

SELECT status, COUNT(*) AS invoices, SUM(total_amount) AS invoice_value FROM payment_match GROUP BY 1 ORDER BY 1;

DROP VIEW IF EXISTS payment_checks CASCADE;
CREATE VIEW payment_checks AS
-- payments that do not match any booked invoice
SELECT p.payment_id, 'PAYMENT_NOT_LINKED' AS check_name, p.invoice_no AS detail
FROM payments p
WHERE NOT EXISTS (SELECT 1 FROM purchase_register r WHERE r.vendor_id = p.vendor_id AND r.invoice_no = p.invoice_no)
UNION ALL
-- professional fees and rent need 10% TDS deducted before paying
SELECT p.payment_id, 'TDS_NOT_DEDUCTED', v.default_category
FROM payments p JOIN vendor_master v USING (vendor_id)
JOIN category_rates c ON c.expense_category = v.default_category
WHERE c.tds_rate > 0 AND p.tds_deducted = 0
  AND EXISTS (SELECT 1 FROM purchase_register r WHERE r.vendor_id = p.vendor_id AND r.invoice_no = p.invoice_no);

SELECT check_name, COUNT(*) FROM payment_checks GROUP BY 1 ORDER BY 1;
