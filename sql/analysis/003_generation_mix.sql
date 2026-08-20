-- One row per technology for the complete period, preserving availability.
WITH technology_totals AS (
    SELECT
        technology_order,
        technology_id,
        technology_name,
        technology_group,
        is_renewable,
        COUNT(*) FILTER (
            WHERE value_status = 'reported'
        ) AS reported_hour_count,
        COUNT(*) FILTER (
            WHERE value_status = 'unavailable'
        ) AS unavailable_hour_count,
        ROUND(SUM(generation_mwh) / 1000000, 3) AS generation_twh,
        SUM(generation_mwh) AS generation_mwh
    FROM reporting.hourly_generation_by_technology
    GROUP BY
        technology_order,
        technology_id,
        technology_name,
        technology_group,
        is_renewable
),
all_reported_generation AS (
    SELECT SUM(generation_mwh) AS generation_mwh
    FROM technology_totals
)
SELECT
    technology.technology_order,
    technology.technology_id,
    technology.technology_name,
    technology.technology_group,
    technology.is_renewable,
    technology.reported_hour_count,
    technology.unavailable_hour_count,
    ROUND(
        100 * technology.reported_hour_count
            / NULLIF(
                technology.reported_hour_count
                    + technology.unavailable_hour_count,
                0
            )::NUMERIC,
        2
    ) AS reported_value_coverage_percent,
    technology.generation_twh,
    ROUND(
        100 * technology.generation_mwh
            / NULLIF(total.generation_mwh, 0),
        2
    ) AS share_of_reported_generation_percent
FROM technology_totals AS technology
CROSS JOIN all_reported_generation AS total
ORDER BY technology.technology_order;
