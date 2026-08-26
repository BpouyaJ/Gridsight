-- Row-level final forecast predictions copied from the verified ignored CSV.
CREATE TABLE IF NOT EXISTS staging.final_forecast_predictions (
    forecast_origin_utc TIMESTAMPTZ NOT NULL,
    origin_local_date DATE NOT NULL,
    split TEXT NOT NULL,
    horizon_step SMALLINT NOT NULL,
    information_cutoff_utc TIMESTAMPTZ NOT NULL,
    target_start_utc TIMESTAMPTZ NOT NULL,
    target_start_local TEXT NOT NULL,
    actual_grid_load_mw NUMERIC(16, 6) NOT NULL,
    daily_naive_source_utc TIMESTAMPTZ NOT NULL,
    daily_naive_prediction_mw NUMERIC(16, 6) NOT NULL,
    weekly_naive_source_utc TIMESTAMPTZ NOT NULL,
    weekly_naive_prediction_mw NUMERIC(16, 6) NOT NULL,
    model_name TEXT NOT NULL,
    model_prediction_mw NUMERIC(16, 6) NOT NULL,
    model_error_mw NUMERIC(16, 6) NOT NULL,
    model_absolute_error_mw NUMERIC(16, 6) NOT NULL,
    CONSTRAINT final_forecast_predictions_pk PRIMARY KEY (
        forecast_origin_utc,
        horizon_step
    ),
    CONSTRAINT final_forecast_scope_ck CHECK (
        split = 'test'
        AND horizon_step BETWEEN 1 AND 24
        AND origin_local_date = (
            forecast_origin_utc AT TIME ZONE 'Europe/Berlin'
        )::DATE
    ),
    CONSTRAINT final_forecast_target_time_ck CHECK (
        information_cutoff_utc = forecast_origin_utc
        AND target_start_utc = forecast_origin_utc
            + (horizon_step - 1) * INTERVAL '1 hour'
    ),
    CONSTRAINT final_forecast_source_time_ck CHECK (
        daily_naive_source_utc = target_start_utc - INTERVAL '24 hours'
        AND weekly_naive_source_utc = target_start_utc - INTERVAL '168 hours'
        AND daily_naive_source_utc + INTERVAL '1 hour'
            <= forecast_origin_utc
        AND weekly_naive_source_utc + INTERVAL '1 hour'
            <= forecast_origin_utc
    ),
    CONSTRAINT final_forecast_value_ck CHECK (
        actual_grid_load_mw > 0
        AND daily_naive_prediction_mw > 0
        AND weekly_naive_prediction_mw > 0
        AND model_prediction_mw > 0
        AND model_name = 'hist_gradient_boosting_31_leaves'
    ),
    CONSTRAINT final_forecast_error_ck CHECK (
        model_error_mw = model_prediction_mw - actual_grid_load_mw
        AND model_absolute_error_mw = ABS(model_error_mw)
    )
);

-- BI-facing analytical fact with conformed target and origin dimensions.
CREATE TABLE IF NOT EXISTS analytics.fact_load_forecast_evaluation (
    forecast_origin_utc TIMESTAMPTZ NOT NULL,
    origin_date_key INTEGER NOT NULL REFERENCES analytics.dim_date (date_key),
    horizon_step SMALLINT NOT NULL,
    information_cutoff_utc TIMESTAMPTZ NOT NULL,
    target_start_utc TIMESTAMPTZ NOT NULL,
    target_date_key INTEGER NOT NULL REFERENCES analytics.dim_date (date_key),
    target_hour_key SMALLINT NOT NULL REFERENCES analytics.dim_hour (hour_key),
    actual_grid_load_mw NUMERIC(16, 6) NOT NULL,
    daily_naive_source_utc TIMESTAMPTZ NOT NULL,
    daily_naive_prediction_mw NUMERIC(16, 6) NOT NULL,
    weekly_naive_source_utc TIMESTAMPTZ NOT NULL,
    weekly_naive_prediction_mw NUMERIC(16, 6) NOT NULL,
    model_name TEXT NOT NULL,
    model_prediction_mw NUMERIC(16, 6) NOT NULL,
    model_error_mw NUMERIC(16, 6) NOT NULL,
    model_absolute_error_mw NUMERIC(16, 6) NOT NULL,
    prediction_artifact_sha256 CHAR(64) NOT NULL,
    evaluation_snapshot_sha256 CHAR(64) NOT NULL,
    CONSTRAINT fact_load_forecast_evaluation_pk PRIMARY KEY (
        forecast_origin_utc,
        horizon_step
    ),
    CONSTRAINT fact_load_forecast_target_fk FOREIGN KEY (target_start_utc)
        REFERENCES analytics.fact_electricity_hourly (interval_start_utc),
    CONSTRAINT fact_load_forecast_time_ck CHECK (
        horizon_step BETWEEN 1 AND 24
        AND information_cutoff_utc = forecast_origin_utc
        AND target_start_utc = forecast_origin_utc
            + (horizon_step - 1) * INTERVAL '1 hour'
        AND daily_naive_source_utc = target_start_utc - INTERVAL '24 hours'
        AND weekly_naive_source_utc = target_start_utc - INTERVAL '168 hours'
    ),
    CONSTRAINT fact_load_forecast_value_ck CHECK (
        actual_grid_load_mw > 0
        AND daily_naive_prediction_mw > 0
        AND weekly_naive_prediction_mw > 0
        AND model_prediction_mw > 0
        AND model_name = 'hist_gradient_boosting_31_leaves'
        AND model_error_mw = model_prediction_mw - actual_grid_load_mw
        AND model_absolute_error_mw = ABS(model_error_mw)
    ),
    CONSTRAINT fact_load_forecast_lineage_ck CHECK (
        prediction_artifact_sha256 ~ '^[0-9a-f]{64}$'
        AND evaluation_snapshot_sha256 ~ '^[0-9a-f]{64}$'
    )
);

CREATE INDEX IF NOT EXISTS fact_load_forecast_target_ix
    ON analytics.fact_load_forecast_evaluation (
        target_date_key,
        target_hour_key
    );

CREATE INDEX IF NOT EXISTS fact_load_forecast_model_horizon_ix
    ON analytics.fact_load_forecast_evaluation (model_name, horizon_step);

CREATE INDEX IF NOT EXISTS fact_load_forecast_origin_date_ix
    ON analytics.fact_load_forecast_evaluation (origin_date_key);
