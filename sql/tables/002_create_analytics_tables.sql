-- Conformed dimensions for local calendar, local hour, and technology.
CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key INTEGER PRIMARY KEY,
    calendar_date DATE NOT NULL UNIQUE,
    calendar_year SMALLINT NOT NULL,
    calendar_quarter SMALLINT NOT NULL,
    month_number SMALLINT NOT NULL,
    month_name TEXT NOT NULL,
    iso_week SMALLINT NOT NULL,
    day_of_month SMALLINT NOT NULL,
    weekday_number SMALLINT NOT NULL,
    weekday_name TEXT NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    CONSTRAINT dim_date_key_ck CHECK (
        date_key = EXTRACT(YEAR FROM calendar_date)::INTEGER * 10000
            + EXTRACT(MONTH FROM calendar_date)::INTEGER * 100
            + EXTRACT(DAY FROM calendar_date)::INTEGER
    ),
    CONSTRAINT dim_date_domains_ck CHECK (
        calendar_quarter BETWEEN 1 AND 4
        AND month_number BETWEEN 1 AND 12
        AND iso_week BETWEEN 1 AND 53
        AND day_of_month BETWEEN 1 AND 31
        AND weekday_number BETWEEN 1 AND 7
    )
);

CREATE TABLE IF NOT EXISTS analytics.dim_hour (
    hour_key SMALLINT PRIMARY KEY,
    hour_start TIME NOT NULL UNIQUE,
    hour_label CHAR(5) NOT NULL UNIQUE,
    CONSTRAINT dim_hour_domain_ck CHECK (hour_key BETWEEN 0 AND 23),
    CONSTRAINT dim_hour_value_ck CHECK (
        hour_start = make_time(hour_key, 0, 0)
        AND hour_label = to_char(make_time(hour_key, 0, 0), 'HH24:MI')
    )
);

CREATE TABLE IF NOT EXISTS analytics.dim_generation_technology (
    technology_key SMALLINT PRIMARY KEY,
    technology_id TEXT NOT NULL UNIQUE,
    technology_name TEXT NOT NULL,
    technology_group TEXT NOT NULL,
    is_renewable BOOLEAN NOT NULL,
    technology_order SMALLINT NOT NULL UNIQUE,
    CONSTRAINT dim_technology_key_ck CHECK (
        technology_key BETWEEN 1 AND 12
        AND technology_order BETWEEN 1 AND 12
    ),
    CONSTRAINT dim_technology_group_ck CHECK (
        technology_group IN ('renewable', 'conventional', 'storage')
        AND is_renewable = (technology_group = 'renewable')
    )
);

-- One row per UTC hour combines measures that share the same hourly grain.
CREATE TABLE IF NOT EXISTS analytics.fact_electricity_hourly (
    interval_start_utc TIMESTAMPTZ PRIMARY KEY,
    interval_end_utc TIMESTAMPTZ NOT NULL,
    date_key INTEGER NOT NULL REFERENCES analytics.dim_date (date_key),
    hour_key SMALLINT NOT NULL REFERENCES analytics.dim_hour (hour_key),
    utc_offset_minutes SMALLINT NOT NULL,
    is_dst BOOLEAN NOT NULL,
    local_fold SMALLINT NOT NULL,
    load_area TEXT NOT NULL,
    grid_load_mwh NUMERIC(14, 2) NOT NULL,
    grid_load_mw NUMERIC(14, 2) NOT NULL,
    grid_load_including_pumped_storage_mwh NUMERIC(14, 2) NOT NULL,
    hydro_pumped_storage_mwh NUMERIC(14, 2) NOT NULL,
    residual_load_mwh NUMERIC(14, 2) NOT NULL,
    price_market_area TEXT NOT NULL,
    day_ahead_price_eur_per_mwh NUMERIC(12, 2) NOT NULL,
    consumption_source_export_id TEXT NOT NULL,
    consumption_source_sha256 CHAR(64) NOT NULL,
    price_source_export_id TEXT NOT NULL,
    price_source_sha256 CHAR(64) NOT NULL,
    CONSTRAINT fact_electricity_interval_ck CHECK (
        interval_end_utc = interval_start_utc + INTERVAL '1 hour'
    ),
    CONSTRAINT fact_electricity_time_ck CHECK (
        utc_offset_minutes IN (60, 120) AND local_fold IN (0, 1)
    ),
    CONSTRAINT fact_electricity_identity_ck CHECK (
        load_area = 'DE'
        AND price_market_area = 'DE-LU'
        AND grid_load_mwh >= 0
        AND grid_load_mw = grid_load_mwh
        AND grid_load_including_pumped_storage_mwh >= 0
        AND hydro_pumped_storage_mwh >= 0
        AND ABS(
            grid_load_including_pumped_storage_mwh
            - grid_load_mwh
            - hydro_pumped_storage_mwh
        ) <= 0.011
        AND consumption_source_sha256 ~ '^[0-9a-f]{64}$'
        AND price_source_sha256 ~ '^[0-9a-f]{64}$'
    )
);

-- One row per UTC hour and generation technology.
CREATE TABLE IF NOT EXISTS analytics.fact_generation_hourly (
    interval_start_utc TIMESTAMPTZ NOT NULL,
    interval_end_utc TIMESTAMPTZ NOT NULL,
    date_key INTEGER NOT NULL REFERENCES analytics.dim_date (date_key),
    hour_key SMALLINT NOT NULL REFERENCES analytics.dim_hour (hour_key),
    technology_key SMALLINT NOT NULL REFERENCES
        analytics.dim_generation_technology (technology_key),
    utc_offset_minutes SMALLINT NOT NULL,
    is_dst BOOLEAN NOT NULL,
    local_fold SMALLINT NOT NULL,
    generation_mwh NUMERIC(14, 2),
    generation_mw NUMERIC(14, 2),
    value_status TEXT NOT NULL,
    source_export_id TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    CONSTRAINT fact_generation_hourly_pk PRIMARY KEY (
        interval_start_utc,
        technology_key
    ),
    CONSTRAINT fact_generation_interval_ck CHECK (
        interval_end_utc = interval_start_utc + INTERVAL '1 hour'
    ),
    CONSTRAINT fact_generation_time_ck CHECK (
        utc_offset_minutes IN (60, 120) AND local_fold IN (0, 1)
    ),
    CONSTRAINT fact_generation_value_ck CHECK (
        source_sha256 ~ '^[0-9a-f]{64}$'
        AND (
            (
                value_status = 'reported'
                AND generation_mwh IS NOT NULL
                AND generation_mw = generation_mwh
                AND generation_mwh >= 0
            )
            OR (
                value_status = 'unavailable'
                AND generation_mwh IS NULL
                AND generation_mw IS NULL
            )
        )
    )
);

CREATE INDEX IF NOT EXISTS fact_electricity_date_hour_ix
    ON analytics.fact_electricity_hourly (date_key, hour_key);

CREATE INDEX IF NOT EXISTS fact_generation_date_hour_ix
    ON analytics.fact_generation_hourly (date_key, hour_key);

CREATE INDEX IF NOT EXISTS fact_generation_technology_ix
    ON analytics.fact_generation_hourly (technology_key);
