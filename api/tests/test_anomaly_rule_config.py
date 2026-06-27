import pytest

from core.services.anomaly_rule_config import (
    DEFAULT_ANOMALY_RULE_CONFIG,
    RULE_IDS,
    validate_anomaly_rule_config,
)


def test_defaults_cover_all_seven_rules():
    assert set(DEFAULT_ANOMALY_RULE_CONFIG["rules"].keys()) == set(RULE_IDS)
    assert len(RULE_IDS) == 7
    assert DEFAULT_ANOMALY_RULE_CONFIG["min_risk_score"] == 0
    # Defaults encode today's hardcoded constants.
    rules = DEFAULT_ANOMALY_RULE_CONFIG["rules"]
    assert rules["rounding_anomaly"]["min_amount"] == 250
    assert rules["threshold_splitting"]["min_count"] == 3
    assert rules["threshold_splitting"]["proximity_pct"] == 0.8
    assert rules["temporal_anomaly"]["start_hour"] == 7
    assert rules["temporal_anomaly"]["end_hour"] == 20
    assert rules["temporal_anomaly"]["flag_weekend"] is True
    assert all(r["enabled"] is True for r in rules.values())


def test_validate_drops_unknown_keys():
    cleaned = validate_anomaly_rule_config(
        {"bogus": 1, "rules": {"not_a_rule": {"enabled": False},
                               "rounding_anomaly": {"enabled": False, "junk": 9}}}
    )
    assert "bogus" not in cleaned
    assert "not_a_rule" not in cleaned["rules"]
    assert cleaned["rules"]["rounding_anomaly"] == {"enabled": False}


def test_validate_coerces_bools():
    cleaned = validate_anomaly_rule_config(
        {"rules": {"temporal_anomaly": {"enabled": 1, "flag_weekend": 0}}}
    )
    assert cleaned["rules"]["temporal_anomaly"]["enabled"] is True
    assert cleaned["rules"]["temporal_anomaly"]["flag_weekend"] is False


@pytest.mark.parametrize("payload", [
    {"min_risk_score": 150},
    {"min_risk_score": -1},
    {"rules": {"rounding_anomaly": {"min_amount": -5}}},
    {"rules": {"threshold_splitting": {"min_count": 1}}},
    {"rules": {"threshold_splitting": {"proximity_pct": 0.2}}},
    {"rules": {"threshold_splitting": {"proximity_pct": 1.5}}},
    {"rules": {"temporal_anomaly": {"start_hour": -1}}},
    {"rules": {"temporal_anomaly": {"end_hour": 24}}},
    {"rules": {"temporal_anomaly": {"start_hour": 20, "end_hour": 7}}},
])
def test_validate_rejects_out_of_range(payload):
    with pytest.raises(ValueError):
        validate_anomaly_rule_config(payload)


def test_validate_rejects_non_dict():
    with pytest.raises(ValueError):
        validate_anomaly_rule_config([1, 2, 3])


def test_validate_partial_update_keeps_only_provided():
    cleaned = validate_anomaly_rule_config({"rules": {"phantom_vendor": {"enabled": False}}})
    assert cleaned == {"rules": {"phantom_vendor": {"enabled": False}}}


from core.models.models_per_tenant import Settings
from core.services.anomaly_rule_config import (
    ANOMALY_RULE_CONFIG_KEY,
    get_anomaly_rule_config,
)


def _set_row(db, value):
    db.add(Settings(key=ANOMALY_RULE_CONFIG_KEY, value=value))
    db.commit()


def test_get_returns_defaults_when_unset(db_session):
    assert get_anomaly_rule_config(db_session) == DEFAULT_ANOMALY_RULE_CONFIG


def test_get_deep_merges_partial_row(db_session):
    _set_row(db_session, {"rules": {"rounding_anomaly": {"enabled": False}}})
    cfg = get_anomaly_rule_config(db_session)
    # Overridden field applied...
    assert cfg["rules"]["rounding_anomaly"]["enabled"] is False
    # ...sibling default within the same rule preserved...
    assert cfg["rules"]["rounding_anomaly"]["min_amount"] == 250
    # ...other rules untouched.
    assert cfg["rules"]["phantom_vendor"]["enabled"] is True


def test_get_clamps_poisoned_values(db_session):
    _set_row(db_session, {
        "min_risk_score": 999,
        "rules": {
            "temporal_anomaly": {"start_hour": "nonsense", "end_hour": 50},
            "threshold_splitting": {"min_count": 0, "proximity_pct": 5.0},
        },
    })
    cfg = get_anomaly_rule_config(db_session)
    assert cfg["min_risk_score"] == 100            # clamped to max
    assert cfg["rules"]["temporal_anomaly"]["start_hour"] == 7   # bad type -> default
    assert cfg["rules"]["temporal_anomaly"]["end_hour"] == 23    # clamped to max
    assert cfg["rules"]["threshold_splitting"]["min_count"] == 2  # clamped to min
    assert cfg["rules"]["threshold_splitting"]["proximity_pct"] == 1.0  # clamped to max
