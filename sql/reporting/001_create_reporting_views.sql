-- One row per canonical UTC hour with load, price, and generation totals.
CREATE OR REPLACE VIEW reporting.hourly_energy AS
WITH generation AS (
    SELECT
        fact.interval_start_utc,
        SUM(fact.generation_mwh) FILTER (
            WHERE fact.value_status = 'reported'
        ) AS reported_generation_mwh,
        SUM(fact.generation_mw) FILTER (
            WHERE fact.value_status = 'reported'
        ) AS reported_generation_mw,
        SUM(fact.generation_mwh) FILTER (
            WHERE technology.technology_group = 'renewable'
                AND fact.value_status = 'reported'
        ) AS renewable_generation_mwh,
        SUM(fact.generation_mw) FILTER (
            WHERE technology.technology_group = 'renewable'
                AND fact.value_status = 'reported'
        ) AS renewable_generation_mw,
        SUM(fact.generation_mwh) FILTER (
            WHERE technology.technology_group = 'conventional'
                AND fact.value_status = 'reported'
        ) AS conventional_generation_mwh,
        SUM(fact.generation_mw) FILTER (
            WHERE technology.technology_group = 'conventional'
                AND fact.value_status = 'reported'
        ) AS conventional_generation_mw,
        SUM(fact.generation_mwh) FILTER (
            WHERE technology.technology_group = 'storage'
                AND fact.value_status = 'reported'
        ) AS storage_generation_mwh,
        SUM(fact.generation_mw) FILTER (
            WHERE technology.technology_group = 'storage'
                AND fact.value_status = 'reported'
        ) AS storage_generation_mw,
        COUNT(*) FILTER (
            WHERE fact.value_status = 'unavailable'
        )::SMALLINT AS unavailable_technology_count,
        COUNT(*) FILTER (
            WHERE fact.value_status = 'reported'
        )::SMALLINT AS reported_technology_count
    FROM analytics.fact_generation_hourly AS fact
    INNER JOIN analytics.dim_generation_technology AS technology
        USING (technology_key)
    GROUP BY fact.interval_start_utc
)
SELECT
    electricity.interval_start_utc,
    electricity.interval_end_utc,
    date.date_key,
    date.calendar_date,
    date.calendar_year,
    date.calendar_quarter,
    date.month_number,
    date.month_name,
    date.iso_week,
    date.weekday_number,
    date.weekday_name,
    date.is_weekend,
    hour.hour_key,
    hour.hour_label,
    electricity.utc_offset_minutes,
    electricity.is_dst,
    electricity.local_fold,
    electricity.load_area,
    electricity.grid_load_mwh,
    electricity.grid_load_mw,
    electricity.grid_load_including_pumped_storage_mwh,
    electricity.hydro_pumped_storage_mwh,
    electricity.residual_load_mwh,
    electricity.price_market_area,
    electricity.day_ahead_price_eur_per_mwh,
    generation.reported_generation_mwh,
    generation.reported_generation_mw,
    generation.renewable_generation_mwh,
    generation.renewable_generation_mw,
    generation.conventional_generation_mwh,
    generation.conventional_generation_mw,
    generation.storage_generation_mwh,
    generation.storage_generation_mw,
    generation.unavailable_technology_count,
    generation.reported_technology_count
FROM analytics.fact_electricity_hourly AS electricity
INNER JOIN analytics.dim_date AS date USING (date_key)
INNER JOIN analytics.dim_hour AS hour USING (hour_key)
INNER JOIN generation USING (interval_start_utc);

-- One row per canonical UTC hour and technology for detailed reporting.
CREATE OR REPLACE VIEW reporting.hourly_generation_by_technology AS
SELECT
    fact.interval_start_utc,
    fact.interval_end_utc,
    date.date_key,
    date.calendar_date,
    date.calendar_year,
    date.calendar_quarter,
    date.month_number,
    date.month_name,
    date.iso_week,
    date.weekday_number,
    date.weekday_name,
    date.is_weekend,
    hour.hour_key,
    hour.hour_label,
    fact.utc_offset_minutes,
    fact.is_dst,
    fact.local_fold,
    technology.technology_key,
    technology.technology_id,
    technology.technology_name,
    technology.technology_group,
    technology.is_renewable,
    technology.technology_order,
    fact.generation_mwh,
    fact.generation_mw,
    fact.value_status,
    fact.source_export_id,
    fact.source_sha256
FROM analytics.fact_generation_hourly AS fact
INNER JOIN analytics.dim_date AS date USING (date_key)
INNER JOIN analytics.dim_hour AS hour USING (hour_key)
INNER JOIN analytics.dim_generation_technology AS technology
    USING (technology_key);

-- One row per Europe/Berlin calendar date, retaining 23/24/25-hour days.
CREATE OR REPLACE VIEW reporting.daily_energy AS
SELECT
    date_key,
    calendar_date,
    calendar_year,
    calendar_quarter,
    month_number,
    month_name,
    iso_week,
    weekday_number,
    weekday_name,
    is_weekend,
    COUNT(*)::SMALLINT AS observed_hour_count,
    SUM(grid_load_mwh) AS grid_load_mwh,
    ROUND(AVG(grid_load_mw), 2) AS average_grid_load_mw,
    MAX(grid_load_mw) AS peak_grid_load_mw,
    SUM(reported_generation_mwh) AS reported_generation_mwh,
    SUM(renewable_generation_mwh) AS renewable_generation_mwh,
    SUM(conventional_generation_mwh) AS conventional_generation_mwh,
    SUM(storage_generation_mwh) AS storage_generation_mwh,
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
    )::SMALLINT AS negative_price_hour_count,
    SUM(unavailable_technology_count)::INTEGER
        AS unavailable_generation_value_count
FROM reporting.hourly_energy
GROUP BY
    date_key,
    calendar_date,
    calendar_year,
    calendar_quarter,
    month_number,
    month_name,
    iso_week,
    weekday_number,
    weekday_name,
    is_weekend;

-- One row per Europe/Berlin calendar month, aggregated from hourly facts.
CREATE OR REPLACE VIEW reporting.monthly_energy AS
SELECT
    (calendar_year * 100 + month_number)::INTEGER AS month_key,
    MAKE_DATE(calendar_year, month_number, 1) AS month_start,
    calendar_year,
    month_number,
    month_name,
    COUNT(DISTINCT calendar_date)::SMALLINT AS observed_day_count,
    COUNT(*)::SMALLINT AS observed_hour_count,
    SUM(grid_load_mwh) AS grid_load_mwh,
    ROUND(AVG(grid_load_mw), 2) AS average_grid_load_mw,
    MAX(grid_load_mw) AS peak_grid_load_mw,
    SUM(reported_generation_mwh) AS reported_generation_mwh,
    SUM(renewable_generation_mwh) AS renewable_generation_mwh,
    SUM(conventional_generation_mwh) AS conventional_generation_mwh,
    SUM(storage_generation_mwh) AS storage_generation_mwh,
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
    )::SMALLINT AS negative_price_hour_count,
    SUM(unavailable_technology_count)::INTEGER
        AS unavailable_generation_value_count
FROM reporting.hourly_energy
GROUP BY
    calendar_year,
    month_number,
    month_name;
