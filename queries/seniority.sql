-- Seniority mix across all postings.
SELECT
    seniority,
    COUNT(*) AS postings
FROM jobs
GROUP BY seniority
ORDER BY postings DESC;
