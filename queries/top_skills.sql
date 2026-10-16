-- Top skills: how many postings mention each skill, most demanded first.
SELECT
    skill,
    COUNT(DISTINCT job_id) AS postings
FROM job_skills
GROUP BY skill
ORDER BY postings DESC, skill ASC
LIMIT 25;
