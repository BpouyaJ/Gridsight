-- One row per final 2025 forecast origin and 24-hour horizon step.
CREATE OR REPLACE VIEW reporting.forecast_performance_hourly AS
SELECT
    fact.forecast_origin_utc,
    origin_date.calendar_date AS origin_local_date,
    fact.information_cutoff_utc,
    fact.target_start_utc,
    fact.target_start_utc AT TIME ZONE 'Europe/Berlin' AS target_start_local,
    fact.target_date_key,
    target_date.calendar_date AS target_calendar_date,
    target_date.calendar_year AS target_calendar_year,
    target_date.calendar_quarter AS target_calendar_quarter,
    target_date.month_number AS target_month_number,
    target_date.month_name AS target_month_name,
    target_date.weekday_number AS target_weekday_number,
    target_date.weekday_name AS target_weekday_name,
    target_date.is_weekend AS target_is_weekend,
    fact.target_hour_key,
    target_hour.hour_label AS target_hour_label,
    fact.horizon_step,
    fact.actual_grid_load_mw,
    fact.model_name,
    fact.model_prediction_mw,
    fact.model_error_mw,
    fact.model_absolute_error_mw,
    fact.daily_naive_prediction_mw,
    fact.weekly_naive_prediction_mw
FROM analytics.fact_load_forecast_evaluation AS fact
INNER JOIN analytics.dim_date AS origin_date
    ON origin_date.date_key = fact.origin_date_key
INNER JOIN analytics.dim_date AS target_date
    ON target_date.date_key = fact.target_date_key
INNER JOIN analytics.dim_hour AS target_hour
    ON target_hour.hour_key = fact.target_hour_key;

-- Three forecast series at overall and 24 horizon-specific scopes.
CREATE OR REPLACE VIEW reporting.forecast_performance_summary AS
WITH prediction_series AS (
    SELECT
        fact.horizon_step,
        fact.actual_grid_load_mw,
        series.forecast_name,
        series.forecast_role,
        series.prediction_mw
    FROM analytics.fact_load_forecast_evaluation AS fact
    CROSS JOIN LATERAL (
        VALUES
            (fact.model_name, 'selected_model', fact.model_prediction_mw),
            (
                'daily_seasonal_naive',
                'baseline',
                fact.daily_naive_prediction_mw
            ),
            (
                'weekly_seasonal_naive',
                'baseline',
                fact.weekly_naive_prediction_mw
            )
    ) AS series (forecast_name, forecast_role, prediction_mw)
), scoped_metrics AS (
    SELECT
        forecast_name,
        forecast_role,
        'overall'::TEXT AS evaluation_scope,
        0::SMALLINT AS horizon_step,
        COUNT(*)::INTEGER AS observations,
        ROUND(AVG(ABS(prediction_mw - actual_grid_load_mw)), 3) AS mae_mw,
        ROUND(
            SQRT(AVG(POWER(prediction_mw - actual_grid_load_mw, 2))),
            3
        ) AS rmse_mw,
        ROUND(
            100 * AVG(
                ABS(prediction_mw - actual_grid_load_mw)
                    / actual_grid_load_mw
            ),
            3
        ) AS mape_percent
    FROM prediction_series
    GROUP BY forecast_name, forecast_role

    UNION ALL

    SELECT
        forecast_name,
        forecast_role,
        'horizon'::TEXT AS evaluation_scope,
        horizon_step,
        COUNT(*)::INTEGER AS observations,
        ROUND(AVG(ABS(prediction_mw - actual_grid_load_mw)), 3) AS mae_mw,
        ROUND(
            SQRT(AVG(POWER(prediction_mw - actual_grid_load_mw, 2))),
            3
        ) AS rmse_mw,
        ROUND(
            100 * AVG(
                ABS(prediction_mw - actual_grid_load_mw)
                    / actual_grid_load_mw
            ),
            3
        ) AS mape_percent
    FROM prediction_series
    GROUP BY forecast_name, forecast_role, horizon_step
), weekly_metrics AS (
    SELECT evaluation_scope, horizon_step, mae_mw AS weekly_mae_mw
    FROM scoped_metrics
    WHERE forecast_name = 'weekly_seasonal_naive'
)
SELECT
    metrics.forecast_name,
    metrics.forecast_role,
    metrics.evaluation_scope,
    metrics.horizon_step,
    metrics.observations,
    metrics.mae_mw,
    metrics.rmse_mw,
    metrics.mape_percent,
    ROUND(
        100 * (weekly.weekly_mae_mw - metrics.mae_mw)
            / NULLIF(weekly.weekly_mae_mw, 0),
        3
    ) AS improvement_over_weekly_percent
FROM scoped_metrics AS metrics
INNER JOIN weekly_metrics AS weekly
    USING (evaluation_scope, horizon_step);
