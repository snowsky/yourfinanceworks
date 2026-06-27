"""Per-tenant anomaly detection rule configuration.

Stored as a single tenant-DB ``Settings`` row under the ``anomaly_rule_config``
key. Mirrors ``invoice_branding.py``: defaults encode today's hardcoded engine
behavior, reads merge over the defaults with clamp-on-read, writes validate with
bounded ranges. An absent/empty row therefore means exactly the current
behavior. Config changes are future-only — the engine consults this at audit
time and never mutates existing ``Anomaly`` rows.
"""

from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

ANOMALY_RULE_CONFIG_KEY = "anomaly_rule_config"

RULE_IDS: Tuple[str, ...] = (
    "duplicate_billing",
    "rounding_anomaly",
    "phantom_vendor",
    "threshold_splitting",
    "temporal_anomaly",
    "description_mismatch",
    "attachment_audit",
)

DEFAULT_ANOMALY_RULE_CONFIG: Dict[str, Any] = {
    "min_risk_score": 0,
    "rules": {
        "duplicate_billing": {"enabled": True},
        "rounding_anomaly": {"enabled": True, "min_amount": 250},
        "phantom_vendor": {"enabled": True},
        "threshold_splitting": {"enabled": True, "min_count": 3, "proximity_pct": 0.8},
        "temporal_anomaly": {
            "enabled": True,
            "start_hour": 7,
            "end_hour": 20,
            "flag_weekend": True,
        },
        "description_mismatch": {"enabled": True},
        "attachment_audit": {"enabled": True},
    },
}


def _as_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def validate_anomaly_rule_config(value: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an incoming (possibly partial) config payload.

    Unknown top-level keys, unknown rule ids, and unknown per-rule sub-keys are
    dropped. Numeric fields are bounded (raise ``ValueError`` out of range).
    Returns a cleaned dict containing only the provided, valid keys so callers
    can merge it over the existing stored value.
    """
    if not isinstance(value, dict):
        raise ValueError("anomaly_rule_config must be an object")

    cleaned: Dict[str, Any] = {}

    if value.get("min_risk_score") is not None:
        score = _as_number(value["min_risk_score"], "min_risk_score")
        if not (0 <= score <= 100):
            raise ValueError("min_risk_score must be between 0 and 100")
        cleaned["min_risk_score"] = score

    rules_in = value.get("rules")
    if rules_in is not None:
        if not isinstance(rules_in, dict):
            raise ValueError("rules must be an object")
        cleaned_rules: Dict[str, Any] = {}
        for rule_id, rule_cfg in rules_in.items():
            if rule_id not in RULE_IDS:
                continue
            if not isinstance(rule_cfg, dict):
                raise ValueError(f"rules.{rule_id} must be an object")
            cleaned_rule = _validate_rule(rule_id, rule_cfg)
            if cleaned_rule:
                cleaned_rules[rule_id] = cleaned_rule
        if cleaned_rules:
            cleaned["rules"] = cleaned_rules

    return cleaned


def _validate_rule(rule_id: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    if cfg.get("enabled") is not None:
        out["enabled"] = bool(cfg["enabled"])

    if rule_id == "rounding_anomaly" and cfg.get("min_amount") is not None:
        amount = _as_number(cfg["min_amount"], "rounding_anomaly.min_amount")
        if amount < 0:
            raise ValueError("rounding_anomaly.min_amount must be >= 0")
        out["min_amount"] = amount

    if rule_id == "threshold_splitting":
        if cfg.get("min_count") is not None:
            count = cfg["min_count"]
            if isinstance(count, bool) or not isinstance(count, int):
                raise ValueError("threshold_splitting.min_count must be an integer")
            if count < 2:
                raise ValueError("threshold_splitting.min_count must be >= 2")
            out["min_count"] = count
        if cfg.get("proximity_pct") is not None:
            pct = _as_number(cfg["proximity_pct"], "threshold_splitting.proximity_pct")
            if not (0.5 <= pct <= 1.0):
                raise ValueError("threshold_splitting.proximity_pct must be between 0.5 and 1.0")
            out["proximity_pct"] = pct

    if rule_id == "temporal_anomaly":
        start = cfg.get("start_hour")
        end = cfg.get("end_hour")
        if start is not None:
            if isinstance(start, bool) or not isinstance(start, int) or not (0 <= start <= 23):
                raise ValueError("temporal_anomaly.start_hour must be an integer 0-23")
            out["start_hour"] = start
        if end is not None:
            if isinstance(end, bool) or not isinstance(end, int) or not (0 <= end <= 23):
                raise ValueError("temporal_anomaly.end_hour must be an integer 0-23")
            out["end_hour"] = end
        # When both are provided in the same payload they must be ordered.
        if start is not None and end is not None and start >= end:
            raise ValueError("temporal_anomaly.start_hour must be < end_hour")
        if cfg.get("flag_weekend") is not None:
            out["flag_weekend"] = bool(cfg["flag_weekend"])

    return out
