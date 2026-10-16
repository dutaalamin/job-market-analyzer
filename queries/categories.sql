-- How many postings fall into each category.
SELECT
    category,
    COUNT(*) AS postings
FROM jobs
GROUP BY category
ORDER BY postings DESC;
