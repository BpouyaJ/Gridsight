-- One deterministic headline KPI row for the complete approved period.
WITH aggregates AS (
    SELECT
        MIN(interval_start_utc) AS period_start_utc,
        MAX(interval_end_utc) AS period_end_utc,
        COUNT(*) AS observed_hour_count,
        ROUND(SUM(grid_load_mwh) / 1000000, 3) AS total_grid_load_twh,
        ROUND(AVG(grid_load_mw) / 1000, 3) AS average_grid_load_gw,
        ROUND(SUM(reported_generation_mwh) / 1000000, 3)
            AS reported_generation_twh,
        ROUND(SUM(renewable_generation_mwh) / 1000000, 3)
            AS renewable_generation_twh,
        ROUND(SUM(conventional_generation_mwh) / 1000000, 3)
            AS conventional_generation_twh,
        ROUND(SUM(storage_generation_mwh) / 1000000, 3)
            AS storage_generation_twh,
        ROUND(
            100 * SUM(renewable_generation_mwh)
                / NULLIF(SUM(reported_generation_mwh), 0),
            2
        ) AS renewable_share_of_reported_generation_percent,
        ROUND(AVG(day_ahead_price_eur_per_mwh), 2)
            AS average_day_ahead_price_eur_per_mwh,
        ROUND(
            PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY day_ahead_price_eur_per_mwh
            )::NUMERIC,
            2
        ) AS median_day_ahead_price_eur_per_mwh,
        COUNT(*) FILTER (
            WHERE day_ahead_price_eur_per_mwh < 0
        ) AS negative_price_hour_count,
        ROUND(
            100 * COUNT(*) FILTER (
                WHERE day_ahead_price_eur_per_mwh < 0
            ) / COUNT(*)::NUMERIC,
            2
        ) AS negative_price_hour_share_percent,
        SUM(unavailable_technology_count)::BIGINT
            AS unavailable_generation_value_count
    FROM reporting.hourly_energy
),
minimum_load AS (
    SELECT
        ROUND(grid_load_mw / 1000, 3) AS minimum_grid_load_gw,
        interval_start_utc AS minimum_grid_load_utc
    FROM reporting.hourly_energy
    ORDER BY grid_load_mw, interval_start_utc
    LIMIT 1
),
peak_load AS (
    SELECT
        ROUND(grid_load_mw / 1000, 3) AS peak_grid_load_gw,
        interval_start_utc AS peak_grid_load_utc
    FROM reporting.hourly_energy
    ORDER BY grid_load_mw DESC, interval_start_utc
    LIMIT 1
),
minimum_price AS (
    SELECT
        day_ahead_price_eur_per_mwh
            AS minimum_day_ahead_price_eur_per_mwh,
        interval_start_utc AS minimum_day_ahead_price_utc
    FROM reporting.hourly_energy
    ORDER BY day_ahead_price_eur_per_mwh, interval_start_utc
    LIMIT 1
),
maximum_price AS (
    SELECT
        day_ahead_price_eur_per_mwh
            AS maximum_day_ahead_price_eur_per_mwh,
        interval_start_utc AS maximum_day_ahead_price_utc
    FROM reporting.hourly_energy
    ORDER BY day_ahead_price_eur_per_mwh DESC, interval_start_utc
    LIMIT 1
)
SELECT
    aggregates.period_start_utc,
    aggregates.period_end_utc,
    aggregates.observed_hour_count,
    aggregates.total_grid_load_twh,
    aggregates.average_grid_load_gw,
    minimum_load.minimum_grid_load_gw,
    minimum_load.minimum_grid_load_utc,
    peak_load.peak_grid_load_gw,
    peak_load.peak_grid_load_utc,
    aggregates.reported_generation_twh,
    aggregates.renewable_generation_twh,
    aggregates.conventional_generation_twh,
    aggregates.storage_generation_twh,
    aggregates.renewable_share_of_reported_generation_percent,
    aggregates.average_day_ahead_price_eur_per_mwh,
    aggregates.median_day_ahead_price_eur_per_mwh,
    minimum_price.minimum_day_ahead_price_eur_per_mwh,
    minimum_price.minimum_day_ahead_price_utc,
    maximum_price.maximum_day_ahead_price_eur_per_mwh,
    maximum_price.maximum_day_ahead_price_utc,
    aggregates.negative_price_hour_count,
    aggregates.negative_price_hour_share_percent,
    aggregates.unavailable_generation_value_count
FROM aggregates
CROSS JOIN minimum_load
CROSS JOIN peak_load
CROSS JOIN minimum_price
CROSS JOIN maximum_price;
