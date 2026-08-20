-- One row per Europe/Berlin calendar year, calculated from hourly observations.
SELECT
    calendar_year,
    COUNT(*) AS observed_hour_count,
    ROUND(SUM(grid_load_mwh) / 1000000, 3) AS grid_load_twh,
    ROUND(AVG(grid_load_mw) / 1000, 3) AS average_grid_load_gw,
    ROUND(MAX(grid_load_mw) / 1000, 3) AS peak_grid_load_gw,
    ROUND(SUM(reported_generation_mwh) / 1000000, 3)
        AS reported_generation_twh,
    ROUND(SUM(renewable_generation_mwh) / 1000000, 3)
        AS renewable_generation_twh,
    ROUND(
        100 * SUM(renewable_generation_mwh)
            / NULLIF(SUM(reported_generation_mwh), 0),
        2
    ) AS renewable_share_of_reported_generation_percent,
    ROUND(AVG(day_ahead_price_eur_per_mwh), 2)
        AS average_day_ahead_price_eur_per_mwh,
    MIN(day_ahead_price_eur_per_mwh)
        AS minimum_day_ahead_price_eur_per_mwh,
    MAX(day_ahead_price_eur_per_mwh)
        AS maximum_day_ahead_price_eur_per_mwh,
    COUNT(*) FILTER (
        WHERE day_ahead_price_eur_per_mwh < 0
    ) AS negative_price_hour_count,
    SUM(unavailable_technology_count)::BIGINT
        AS unavailable_generation_value_count
FROM reporting.hourly_energy
GROUP BY calendar_year
ORDER BY calendar_year;
