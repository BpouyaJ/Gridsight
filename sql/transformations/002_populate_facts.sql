-- Combine the aligned one-row-per-hour load and price staging datasets.
INSERT INTO analytics.fact_electricity_hourly (
    interval_start_utc,
    interval_end_utc,
    date_key,
    hour_key,
    utc_offset_minutes,
    is_dst,
    local_fold,
    load_area,
    grid_load_mwh,
    grid_load_mw,
    grid_load_including_pumped_storage_mwh,
    hydro_pumped_storage_mwh,
    residual_load_mwh,
    price_market_area,
    day_ahead_price_eur_per_mwh,
    consumption_source_export_id,
    consumption_source_sha256,
    price_source_export_id,
    price_source_sha256
)
SELECT
    consumption.interval_start_utc,
    consumption.interval_end_utc,
    TO_CHAR(
        consumption.interval_start_utc AT TIME ZONE 'Europe/Berlin',
        'YYYYMMDD'
    )::INTEGER,
    EXTRACT(
        HOUR FROM consumption.interval_start_utc AT TIME ZONE 'Europe/Berlin'
    )::SMALLINT,
    consumption.utc_offset_minutes,
    consumption.is_dst,
    consumption.local_fold,
    consumption.source_geography,
    consumption.grid_load_mwh,
    consumption.grid_load_mw,
    consumption.grid_load_including_pumped_storage_mwh,
    consumption.hydro_pumped_storage_mwh,
    consumption.residual_load_mwh,
    price.market_area,
    price.day_ahead_price_eur_per_mwh,
    consumption.source_export_id,
    consumption.source_sha256,
    price.source_export_id,
    price.source_sha256
FROM staging.actual_consumption_hourly AS consumption
INNER JOIN staging.day_ahead_price_hourly AS price
    USING (interval_start_utc)
ORDER BY consumption.interval_start_utc;

-- Retain generation's one-row-per-hour-and-technology grain.
INSERT INTO analytics.fact_generation_hourly (
    interval_start_utc,
    interval_end_utc,
    date_key,
    hour_key,
    technology_key,
    utc_offset_minutes,
    is_dst,
    local_fold,
    generation_mwh,
    generation_mw,
    value_status,
    source_export_id,
    source_sha256
)
SELECT
    generation.interval_start_utc,
    generation.interval_end_utc,
    TO_CHAR(
        generation.interval_start_utc AT TIME ZONE 'Europe/Berlin',
        'YYYYMMDD'
    )::INTEGER,
    EXTRACT(
        HOUR FROM generation.interval_start_utc AT TIME ZONE 'Europe/Berlin'
    )::SMALLINT,
    technology.technology_key,
    generation.utc_offset_minutes,
    generation.is_dst,
    generation.local_fold,
    generation.generation_mwh,
    generation.generation_mw,
    generation.value_status,
    generation.source_export_id,
    generation.source_sha256
FROM staging.actual_generation_hourly AS generation
INNER JOIN analytics.dim_generation_technology AS technology
    USING (technology_id)
ORDER BY generation.interval_start_utc, technology.technology_key;
