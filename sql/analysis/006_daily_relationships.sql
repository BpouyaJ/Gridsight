-- One row per local calendar day for associations and unusual-day ranking.
SELECT
    calendar_date,
    calendar_year,
    month_number,
    weekday_name,
    is_weekend,
    observed_hour_count,
    ROUND(grid_load_mwh / 1000, 3) AS grid_load_gwh,
    ROUND(average_grid_load_mw / 1000, 3) AS average_grid_load_gw,
    ROUND(peak_grid_load_mw / 1000, 3) AS peak_grid_load_gw,
    ROUND(renewable_generation_mwh / 1000, 3)
        AS renewable_generation_gwh,
    renewable_share_of_reported_generation_percent,
    average_day_ahead_price_eur_per_mwh,
    minimum_day_ahead_price_eur_per_mwh,
    maximum_day_ahead_price_eur_per_mwh,
    negative_price_hour_count,
    unavailable_generation_value_count
FROM reporting.daily_energy
ORDER BY calendar_date;
