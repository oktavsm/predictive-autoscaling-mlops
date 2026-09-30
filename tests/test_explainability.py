import json

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestRegressor

from src.monitoring.explainability import (
    FEATURE_COLUMNS,
    ModelExplainer,
    generate_ai_governance_model_card,
)


@pytest.fixture
def sample_features_df():
    np.random.seed(42)
    n = 50
    data = {
        col: np.random.uniform(1.0, 50.0, size=n)
        for col in FEATURE_COLUMNS
    }
    data["target_rps_60s"] = data["request_rate"] * 1.2 + np.random.normal(0, 0.5, size=n)
    return pd.DataFrame(data)


@pytest.fixture
def trained_toy_model(sample_features_df):
    X = sample_features_df[FEATURE_COLUMNS]
    y = sample_features_df["target_rps_60s"]
    model = RandomForestRegressor(n_estimators=10, max_depth=3, random_state=42)
    model.fit(X, y)
    return model


def test_model_explainer_computes_shap_values(trained_toy_model, sample_features_df):
    X = sample_features_df[FEATURE_COLUMNS]
    explainer = ModelExplainer(trained_toy_model, FEATURE_COLUMNS)
    shap_vals = explainer.compute_shap_values(X)

    assert shap_vals is not None
    assert shap_vals.shape == (len(X), len(FEATURE_COLUMNS))
    assert not np.isnan(shap_vals).any()


def test_feature_importance_summary_structure(trained_toy_model, sample_features_df):
    X = sample_features_df[FEATURE_COLUMNS]
    explainer = ModelExplainer(trained_toy_model, FEATURE_COLUMNS)
    summary = explainer.get_feature_importance_summary(X)

    assert len(summary) == len(FEATURE_COLUMNS)
    assert summary[0]["mean_abs_shap"] >= summary[-1]["mean_abs_shap"]
    total_pct = sum(item["relative_importance_pct"] for item in summary)
    assert pytest.approx(total_pct, abs=0.5) == 100.0


def test_plot_summary_and_importance(trained_toy_model, sample_features_df, tmp_path):
    X = sample_features_df[FEATURE_COLUMNS]
    explainer = ModelExplainer(trained_toy_model, FEATURE_COLUMNS)

    summary_png = tmp_path / "summary.png"
    importance_png = tmp_path / "importance.png"

    explainer.plot_summary_and_importance(X, summary_png, importance_png)

    assert summary_png.exists()
    assert summary_png.stat().st_size > 1000
    assert importance_png.exists()
    assert importance_png.stat().st_size > 1000


def test_generate_ai_governance_model_card(trained_toy_model, sample_features_df, tmp_path):
    X = sample_features_df[FEATURE_COLUMNS]
    explainer = ModelExplainer(trained_toy_model, FEATURE_COLUMNS)
    summary = explainer.get_feature_importance_summary(X)

    output_card = tmp_path / "xai_model_card.json"
    card = generate_ai_governance_model_card(summary, output_card)

    assert output_card.exists()
    assert card["governance_status"] == "APPROVED_FOR_PRODUCTION"
    assert "explainability_audit" in card
    assert "ethical_considerations" in card
    assert "container_security_compliance" in card

    # Verify JSON serializability
    with open(output_card, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["model_name"] == "predictive-autoscaler"
