-- Canonical clean-data contracts, including row-level source lineage.
CREATE TABLE IF NOT EXISTS staging.actual_consumption_hourly (
    interval_start_utc TIMESTAMPTZ PRIMARY KEY,
    interval_end_utc TIMESTAMPTZ NOT NULL,
    interval_start_local TIMESTAMPTZ NOT NULL,
    interval_end_local TIMESTAMPTZ NOT NULL,
    utc_offset_minutes SMALLINT NOT NULL,
    is_dst BOOLEAN NOT NULL,
    local_fold SMALLINT NOT NULL,
    source_start_text TEXT NOT NULL,
    source_end_text TEXT NOT NULL,
    source_export_id TEXT NOT NULL,
    source_category TEXT NOT NULL,
    source_geography TEXT NOT NULL,
    source_resolution TEXT NOT NULL,
    source_period_start DATE NOT NULL,
    source_period_end DATE NOT NULL,
    source_original_filename TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    interval_duration_hours NUMERIC(4, 2) NOT NULL,
    grid_load_mwh NUMERIC(14, 2) NOT NULL,
    grid_load_mw NUMERIC(14, 2) NOT NULL,
    grid_load_including_pumped_storage_mwh NUMERIC(14, 2) NOT NULL,
    hydro_pumped_storage_mwh NUMERIC(14, 2) NOT NULL,
    residual_load_mwh NUMERIC(14, 2) NOT NULL,
    CONSTRAINT consumption_utc_interval_ck CHECK (
        interval_end_utc = interval_start_utc + INTERVAL '1 hour'
    ),
    CONSTRAINT consumption_time_context_ck CHECK (
        utc_offset_minutes IN (60, 120) AND local_fold IN (0, 1)
    ),
    CONSTRAINT consumption_lineage_ck CHECK (
        source_category = 'actual_consumption'
        AND source_geography = 'DE'
        AND source_resolution = 'hour'
        AND source_period_start <= source_period_end
        AND source_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT consumption_measure_domain_ck CHECK (
        interval_duration_hours = 1.00
        AND grid_load_mwh >= 0
        AND grid_load_mw >= 0
        AND grid_load_including_pumped_storage_mwh >= 0
        AND hydro_pumped_storage_mwh >= 0
    ),
    CONSTRAINT consumption_power_identity_ck CHECK (
        grid_load_mw = grid_load_mwh
    ),
    CONSTRAINT consumption_grid_load_identity_ck CHECK (
        ABS(
            grid_load_including_pumped_storage_mwh
            - grid_load_mwh
            - hydro_pumped_storage_mwh
        ) <= 0.011
    )
);

CREATE TABLE IF NOT EXISTS staging.actual_generation_hourly (
    interval_start_utc TIMESTAMPTZ NOT NULL,
    interval_end_utc TIMESTAMPTZ NOT NULL,
    interval_start_local TIMESTAMPTZ NOT NULL,
    interval_end_local TIMESTAMPTZ NOT NULL,
    utc_offset_minutes SMALLINT NOT NULL,
    is_dst BOOLEAN NOT NULL,
    local_fold SMALLINT NOT NULL,
    source_start_text TEXT NOT NULL,
    source_end_text TEXT NOT NULL,
    source_export_id TEXT NOT NULL,
    source_category TEXT NOT NULL,
    source_geography TEXT NOT NULL,
    source_resolution TEXT NOT NULL,
    source_period_start DATE NOT NULL,
    source_period_end DATE NOT NULL,
    source_original_filename TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    interval_duration_hours NUMERIC(4, 2) NOT NULL,
    technology_id TEXT NOT NULL,
    technology_name TEXT NOT NULL,
    technology_group TEXT NOT NULL,
    is_renewable BOOLEAN NOT NULL,
    technology_order SMALLINT NOT NULL,
    source_measure_column TEXT NOT NULL,
    source_value_text TEXT NOT NULL,
    value_status TEXT NOT NULL,
    generation_mwh NUMERIC(14, 2),
    generation_mw NUMERIC(14, 2),
    CONSTRAINT generation_hourly_pk PRIMARY KEY (
        interval_start_utc,
        technology_id
    ),
    CONSTRAINT generation_utc_interval_ck CHECK (
        interval_end_utc = interval_start_utc + INTERVAL '1 hour'
    ),
    CONSTRAINT generation_time_context_ck CHECK (
        utc_offset_minutes IN (60, 120) AND local_fold IN (0, 1)
    ),
    CONSTRAINT generation_lineage_ck CHECK (
        source_category = 'actual_generation'
        AND source_geography = 'DE'
        AND source_resolution = 'hour'
        AND source_period_start <= source_period_end
        AND source_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT generation_technology_ck CHECK (
        technology_group IN ('renewable', 'conventional', 'storage')
        AND is_renewable = (technology_group = 'renewable')
        AND technology_order BETWEEN 1 AND 12
    ),
    CONSTRAINT generation_value_semantics_ck CHECK (
        interval_duration_hours = 1.00
        AND (
            (
                value_status = 'reported'
                AND generation_mwh IS NOT NULL
                AND generation_mw IS NOT NULL
                AND generation_mwh >= 0
                AND generation_mw = generation_mwh
            )
            OR (
                value_status = 'unavailable'
                AND technology_id = 'nuclear'
                AND source_value_text = '-'
                AND generation_mwh IS NULL
                AND generation_mw IS NULL
            )
        )
    )
);

CREATE TABLE IF NOT EXISTS staging.day_ahead_price_hourly (
    interval_start_utc TIMESTAMPTZ PRIMARY KEY,
    interval_end_utc TIMESTAMPTZ NOT NULL,
    interval_start_local TIMESTAMPTZ NOT NULL,
    interval_end_local TIMESTAMPTZ NOT NULL,
    utc_offset_minutes SMALLINT NOT NULL,
    is_dst BOOLEAN NOT NULL,
    local_fold SMALLINT NOT NULL,
    source_start_text TEXT NOT NULL,
    source_end_text TEXT NOT NULL,
    source_export_id TEXT NOT NULL,
    source_category TEXT NOT NULL,
    source_geography TEXT NOT NULL,
    source_resolution TEXT NOT NULL,
    source_period_start DATE NOT NULL,
    source_period_end DATE NOT NULL,
    source_original_filename TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    interval_duration_hours NUMERIC(4, 2) NOT NULL,
    market_area TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    price_unit TEXT NOT NULL,
    source_measure_column TEXT NOT NULL,
    source_value_text TEXT NOT NULL,
    day_ahead_price_eur_per_mwh NUMERIC(12, 2) NOT NULL,
    CONSTRAINT price_utc_interval_ck CHECK (
        interval_end_utc = interval_start_utc + INTERVAL '1 hour'
    ),
    CONSTRAINT price_time_context_ck CHECK (
        utc_offset_minutes IN (60, 120) AND local_fold IN (0, 1)
    ),
    CONSTRAINT price_lineage_ck CHECK (
        source_category = 'day_ahead_price'
        AND source_geography = 'DE-LU'
        AND source_resolution = 'hour'
        AND source_period_start <= source_period_end
        AND source_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT price_measure_contract_ck CHECK (
        interval_duration_hours = 1.00
        AND market_area = 'DE-LU'
        AND currency = 'EUR'
        AND price_unit = 'EUR/MWh'
    )
);
