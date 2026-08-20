"""CLI for training candidates and selecting by chronological validation."""

from gridsight.forecasting.contract import sha256_file
from gridsight.forecasting.model_validation import (
    DEFAULT_MODEL_VALIDATION_SNAPSHOT,
    build_model_validation_snapshot,
    evaluate_model_candidates,
    load_frozen_feature_matrix,
    load_verified_baseline_snapshot,
    write_model_validation_snapshot,
)


def main() -> int:
    """Fit fixed candidates on train and publish validation-only evidence."""
    try:
        features, feature_contract = load_frozen_feature_matrix()
        baseline_snapshot = load_verified_baseline_snapshot(feature_contract)
        results = evaluate_model_candidates(features)
        snapshot = build_model_validation_snapshot(results, baseline_snapshot)
        write_model_validation_snapshot(
            snapshot,
            DEFAULT_MODEL_VALIDATION_SNAPSHOT,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
        print(f"Model validation: FAILED ({error})")
        return 1

    print("Model validation: OK")
    for result in results:
        train = result["train"]["overall"]
        validation = result["validation"]["overall"]
        print(
            f"{result['name']}: "
            f"train_MAE={train['mae_mw']:.3f} MW, "
            f"validation_MAE={validation['mae_mw']:.3f} MW, "
            f"validation_RMSE={validation['rmse_mw']:.3f} MW, "
            f"validation_MAPE={validation['mape_percent']:.3f}%"
        )
    selection = snapshot["selection"]
    print(f"Selected candidate: {selection['selected_candidate']}")
    print(
        "Improvement over weekly baseline: "
        f"{selection['improvement_over_weekly_baseline_percent']:.3f}%"
    )
    print(f"Beats weekly baseline: {selection['beats_weekly_baseline']}")
    print("Test forecast rows scored: 0")
    relative_output = DEFAULT_MODEL_VALIDATION_SNAPSHOT.relative_to(
        DEFAULT_MODEL_VALIDATION_SNAPSHOT.parents[1]
    )
    print(f"Output: {relative_output}")
    print(f"SHA-256: {sha256_file(DEFAULT_MODEL_VALIDATION_SNAPSHOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
