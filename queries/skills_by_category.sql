-- Top skills within a single category. The :category is bound by analyze.py.
SELECT
    js.skill,
    COUNT(DISTINCT js.job_id) AS postings
FROM job_skills js
JOIN jobs j ON j.id = js.job_id
WHERE j.category = :category
GROUP BY js.skill
ORDER BY postings DESC, js.skill ASC
LIMIT 12;
