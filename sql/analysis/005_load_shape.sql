-- One row per local clock hour and weekday/weekend class.
SELECT
    hour_key,
    hour_label,
    CASE
        WHEN is_weekend THEN 'weekend'
        ELSE 'weekday'
    END AS day_type,
    COUNT(*)::INTEGER AS observed_hour_count,
    ROUND(AVG(grid_load_mw) / 1000, 3) AS average_grid_load_gw,
    ROUND(
        PERCENTILE_CONT(0.1) WITHIN GROUP (
            ORDER BY grid_load_mw
        )::NUMERIC / 1000,
        3
    ) AS p10_grid_load_gw,
    ROUND(
        PERCENTILE_CONT(0.9) WITHIN GROUP (
            ORDER BY grid_load_mw
        )::NUMERIC / 1000,
        3
    ) AS p90_grid_load_gw
FROM reporting.hourly_energy
GROUP BY
    hour_key,
    hour_label,
    is_weekend
ORDER BY
    is_weekend,
    hour_key;
