"""
Smoke tests for the committed sample dataset.

These tests run in a fresh Codespace against src/data/demo_metrics.csv.
They do not require VPS access or Prometheus credentials.
"""
import pandas as pd
import pytest

DEMO_CSV = "src/data/demo_metrics.csv"

REQUIRED_COLUMNS = [
    "request_rate",
    "php_cpu_cores",
    "php_memory_bytes",
    "replicas",
    "p95_latency_seconds",
]


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(DEMO_CSV, index_col="timestamp", parse_dates=True)


def test_file_loads(df):
    """Dataset file can be loaded without errors."""
    assert df is not None


def test_has_required_columns(df):
    """Dataset contains all required metric columns."""
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"Missing column: {col}"


def test_has_rows(df):
    """Dataset is not empty."""
    assert len(df) > 0, "Dataset has no rows"


def test_index_is_datetime(df):
    """Timestamp index has datetime dtype."""
    assert pd.api.types.is_datetime64_any_dtype(df.index), (
        "Index is not datetime"
    )


def test_index_is_sorted(df):
    """Timestamps are in ascending order."""
    assert df.index.is_monotonic_increasing, "Timestamps are not sorted"


def test_request_rate_non_negative(df):
    """Request rate must never be negative."""
    assert (df["request_rate"].dropna() >= 0).all()


def test_replicas_in_valid_range(df):
    """Replica count should be between 1 and 10."""
    replicas = df["replicas"].dropna()
    assert (replicas >= 1).all(), "Replicas below 1"
    assert (replicas <= 10).all(), "Replicas above 10"


def test_no_duplicate_timestamps(df):
    """No two rows should share the same timestamp."""
    duplicates = df.index.duplicated().sum()
    assert duplicates == 0, f"Found {duplicates} duplicate timestamps"
