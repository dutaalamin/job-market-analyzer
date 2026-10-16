-- Skills that most often appear together with a given skill (co-occurrence).
-- :skill is bound by analyze.py. Useful for seeing natural skill clusters.
SELECT
    other.skill AS companion,
    COUNT(DISTINCT other.job_id) AS together
FROM job_skills me
JOIN job_skills other
    ON other.job_id = me.job_id AND other.skill <> me.skill
WHERE me.skill = :skill
GROUP BY other.skill
ORDER BY together DESC, companion ASC
LIMIT 10;
