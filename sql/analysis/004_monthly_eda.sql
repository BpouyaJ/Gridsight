-- One row per Europe/Berlin calendar month for focused trend analysis.
SELECT
    month_start,
    calendar_year,
    month_number,
    month_name,
    observed_day_count,
    observed_hour_count,
    ROUND(grid_load_mwh / 1000000, 3) AS grid_load_twh,
    ROUND(average_grid_load_mw / 1000, 3) AS average_grid_load_gw,
    ROUND(peak_grid_load_mw / 1000, 3) AS peak_grid_load_gw,
    ROUND(reported_generation_mwh / 1000000, 3)
        AS reported_generation_twh,
    ROUND(renewable_generation_mwh / 1000000, 3)
        AS renewable_generation_twh,
    renewable_share_of_reported_generation_percent,
    average_day_ahead_price_eur_per_mwh,
    minimum_day_ahead_price_eur_per_mwh,
    maximum_day_ahead_price_eur_per_mwh,
    negative_price_hour_count,
    unavailable_generation_value_count
FROM reporting.monthly_energy
ORDER BY month_start;
