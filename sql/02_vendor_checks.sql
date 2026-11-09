-- InvoiceDesk 02: vendor master checks
-- A GSTIN is 15 characters: 2-digit state code (01-38) + the 10-character PAN + entity number + 'Z' + check character.
DROP VIEW IF EXISTS vendor_checks CASCADE;
CREATE VIEW vendor_checks AS
WITH v AS (
  SELECT vm.*,
         COUNT(*) OVER (PARTITION BY pan) AS pan_count,
         (gstin IS NOT NULL AND (LENGTH(gstin) <> 15
            OR LEFT(gstin, 2) !~ '^[0-9]{2}$'
            OR LEFT(gstin, 2)::int NOT BETWEEN 1 AND 38
            OR SUBSTRING(gstin, 14, 1) <> 'Z')) AS gstin_invalid
  FROM vendor_master vm)
SELECT vendor_id, 'GSTIN_MISSING' AS check_name, NULL AS detail FROM v WHERE gstin IS NULL
UNION ALL
SELECT vendor_id, 'GSTIN_INVALID', gstin FROM v WHERE gstin_invalid
UNION ALL
SELECT vendor_id, 'PAN_MISMATCH', 'GSTIN has ' || SUBSTRING(gstin, 3, 10) || ', PAN column ' || pan
FROM v WHERE gstin IS NOT NULL AND NOT gstin_invalid AND SUBSTRING(gstin, 3, 10) <> pan
UNION ALL
SELECT vendor_id, 'DUPLICATE_VENDOR', 'PAN ' || pan || ' used by ' || pan_count || ' vendor records' FROM v WHERE pan_count > 1;

SELECT check_name, COUNT(*) FROM vendor_checks GROUP BY 1 ORDER BY 1;
-- the duplicate vendor pairs side by side
SELECT pan, STRING_AGG(vendor_id || ' ' || vendor_name, '  |  ' ORDER BY vendor_id) AS records
FROM vendor_master GROUP BY pan HAVING COUNT(*) > 1;
