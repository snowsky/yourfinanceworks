"""Tests for the new cross-portfolio and document-scan formatters."""

from __future__ import annotations

from cli.finance_agent_cli.render import (
    print_cross_summary,
    print_document_scan,
    print_exposure_report,
    print_overlap_analysis,
)


def test_print_cross_summary_includes_scalars_and_top_holdings(capsys):
    payload = {
        "portfolio_count": 3,
        "total_unique_securities": 42,
        "total_combined_value": 125300.0,
        "total_combined_cost": 110000.0,
        "total_gain_loss": 15300.0,
        "total_gain_loss_pct": 13.909090909090910,
        "overlapping_securities_count": 5,
        "overlap_percentage": 11.9,
        "top_holdings": [
            {
                "security_symbol": "AAPL",
                "total_quantity": 50,
                "total_current_value": 9500.0,
                "gain_loss_pct": 18.5,
                "portfolio_count": 2,
            }
        ],
        "concentration_warnings": [
            {
                "security_symbol": "TSLA",
                "total_value": 22000.0,
                "pct_of_total": 17.56,
                "portfolio_count": 2,
            }
        ],
    }

    print_cross_summary(payload)
    out = capsys.readouterr().out

    assert "Cross-Portfolio Summary" in out
    assert "Portfolios: 3" in out
    assert "125,300.00" in out
    assert "13.91%" in out
    assert "Top Holdings" in out
    assert "AAPL" in out
    assert "Concentration Warnings" in out
    assert "TSLA" in out


def test_print_overlap_analysis_emits_no_overlap_message(capsys):
    print_overlap_analysis(
        {
            "portfolio_count": 2,
            "total_unique_securities": 10,
            "overlapping_securities_count": 0,
            "overlap_percentage": 0.0,
            "overlap_details": [],
        }
    )
    out = capsys.readouterr().out

    assert "No overlap between portfolios." in out


def test_print_exposure_report_renders_concentration_and_exposures(capsys):
    print_exposure_report(
        {
            "total_combined_value": 100000.0,
            "securities_count": 12,
            "concentration_warnings_count": 1,
            "concentration_warnings": [
                {
                    "security_symbol": "NVDA",
                    "total_value": 32000.0,
                    "pct_of_total": 32.0,
                    "portfolio_count": 1,
                }
            ],
            "exposures": [
                {
                    "security_symbol": "VTI",
                    "total_value": 18000.0,
                    "pct_of_total": 18.0,
                    "portfolio_count": 3,
                }
            ],
        }
    )
    out = capsys.readouterr().out

    assert "Cross-Portfolio Exposure Report" in out
    assert "NVDA" in out
    assert "32.00%" in out
    assert "Top Exposures" in out
    assert "VTI" in out


def test_print_document_scan_lists_classified_and_sent(capsys):
    print_document_scan(
        {
            "documents": [
                {
                    "filename": "receipt-001.pdf",
                    "document_type": "expense",
                    "confidence": 0.88,
                    "reason": "filename/content keyword match",
                }
            ],
            "sent": [
                {
                    "filename": "receipt-001.pdf",
                    "document_type": "expense",
                    "destination": "batch-processing",
                }
            ],
        }
    )
    out = capsys.readouterr().out

    assert "Scanned 1 document(s)" in out
    assert "receipt-001.pdf" in out
    assert "expense" in out
    assert "0.88" in out
    assert "Sent 1 document(s) to YFW" in out
    assert "batch-processing" in out
