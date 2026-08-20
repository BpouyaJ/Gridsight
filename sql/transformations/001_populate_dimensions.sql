-- Derive conformed local reporting dates from the canonical UTC spine.
INSERT INTO analytics.dim_date (
    date_key,
    calendar_date,
    calendar_year,
    calendar_quarter,
    month_number,
    month_name,
    iso_week,
    day_of_month,
    weekday_number,
    weekday_name,
    is_weekend
)
SELECT
    TO_CHAR(local_date, 'YYYYMMDD')::INTEGER,
    local_date,
    EXTRACT(YEAR FROM local_date)::SMALLINT,
    EXTRACT(QUARTER FROM local_date)::SMALLINT,
    EXTRACT(MONTH FROM local_date)::SMALLINT,
    TO_CHAR(local_date, 'FMMonth'),
    EXTRACT(WEEK FROM local_date)::SMALLINT,
    EXTRACT(DAY FROM local_date)::SMALLINT,
    EXTRACT(ISODOW FROM local_date)::SMALLINT,
    TO_CHAR(local_date, 'FMDay'),
    EXTRACT(ISODOW FROM local_date) IN (6, 7)
FROM (
    SELECT DISTINCT
        (interval_start_utc AT TIME ZONE 'Europe/Berlin')::DATE AS local_date
    FROM staging.actual_consumption_hourly
) AS dates
ORDER BY local_date;

-- Create the 24 local clock-hour members used by BI filtering.
INSERT INTO analytics.dim_hour (
    hour_key,
    hour_start,
    hour_label
)
SELECT
    hour_number::SMALLINT,
    MAKE_TIME(hour_number, 0, 0),
    TO_CHAR(MAKE_TIME(hour_number, 0, 0), 'HH24:MI')
FROM GENERATE_SERIES(0, 23) AS hours (hour_number)
ORDER BY hour_number;

-- Promote the 12 source-controlled technology members to a dimension.
INSERT INTO analytics.dim_generation_technology (
    technology_key,
    technology_id,
    technology_name,
    technology_group,
    is_renewable,
    technology_order
)
SELECT DISTINCT
    technology_order AS technology_key,
    technology_id,
    technology_name,
    technology_group,
    is_renewable,
    technology_order
FROM staging.actual_generation_hourly
ORDER BY technology_order;
