"""
Cross-Portfolio Analyzer

This module implements calculation algorithms for cross-portfolio analysis.
It provides methods to consolidate holdings across multiple portfolios,
detect overlapping securities, compare per-stock performance, and calculate
total exposure / concentration risk.

The calculator is stateless and works with lists of holdings and transactions
passed in from the service layer.
"""

from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import date, timedelta
from collections import defaultdict

from ..models import InvestmentHolding, InvestmentPortfolio, InvestmentTransaction, TransactionType


class CrossPortfolioAnalyzer:
    """
    Calculator for cross-portfolio analysis.

    All methods accept pre-loaded model instances and return plain
    dictionaries suitable for serialisation by the service layer.
    """

    # ------------------------------------------------------------------ #
    # Consolidated Holdings
    # ------------------------------------------------------------------ #
    def consolidate_holdings(
        self,
        portfolios_with_holdings: List[Tuple[InvestmentPortfolio, List[InvestmentHolding]]],
    ) -> List[dict]:
        """
        Group identical securities across portfolios and compute aggregated
        metrics (combined quantity, weighted average cost, total value,
        total unrealised gain/loss).

        Args:
            portfolios_with_holdings: List of (portfolio, holdings) tuples

        Returns:
            List of consolidated holding dicts sorted by total value descending
        """
        symbol_map: Dict[str, dict] = {}

        for portfolio, holdings in portfolios_with_holdings:
            for h in holdings:
                if h.is_closed:
                    continue
                sym = h.security_symbol.upper()
                if sym not in symbol_map:
                    symbol_map[sym] = {
                        "security_symbol": sym,
                        "security_name": h.security_name or sym,
                        "security_type": h.security_type.value if h.security_type else None,
                        "asset_class": h.asset_class.value if h.asset_class else None,
                        "total_quantity": Decimal("0"),
                        "total_cost_basis": Decimal("0"),
                        "total_current_value": Decimal("0"),
                        "total_unrealized_gain_loss": Decimal("0"),
                        "portfolios": [],
                    }

                qty = Decimal(str(h.quantity or 0))
                cost = Decimal(str(h.cost_basis or 0))
                value = h.current_value
                gl = h.unrealized_gain_loss

                symbol_map[sym]["total_quantity"] += qty
                symbol_map[sym]["total_cost_basis"] += cost
                symbol_map[sym]["total_current_value"] += value
                symbol_map[sym]["total_unrealized_gain_loss"] += gl

                gain_loss_pct = (
                    (gl / cost * 100) if cost > 0 else Decimal("0")
                )
                symbol_map[sym]["portfolios"].append({
                    "portfolio_id": portfolio.id,
                    "portfolio_name": portfolio.name,
                    "portfolio_type": portfolio.portfolio_type.value if portfolio.portfolio_type else None,
                    "quantity": float(qty),
                    "cost_basis": float(cost),
                    "current_value": float(value),
                    "unrealized_gain_loss": float(gl),
                    "gain_loss_pct": float(gain_loss_pct),
                })

        # Compute aggregate gain/loss pct and convert to serialisable types
        results = []
        for data in symbol_map.values():
            tq = data["total_quantity"]
            tc = data["total_cost_basis"]
            tv = data["total_current_value"]
            tgl = data["total_unrealized_gain_loss"]
            weighted_avg_cost = (tc / tq) if tq > 0 else Decimal("0")
            gl_pct = (tgl / tc * 100) if tc > 0 else Decimal("0")

            results.append({
                "security_symbol": data["security_symbol"],
                "security_name": data["security_name"],
                "security_type": data["security_type"],
                "asset_class": data["asset_class"],
                "total_quantity": float(tq),
                "weighted_avg_cost": float(weighted_avg_cost),
                "total_cost_basis": float(tc),
                "total_current_value": float(tv),
                "total_unrealized_gain_loss": float(tgl),
                "gain_loss_pct": float(gl_pct),
                "portfolio_count": len(data["portfolios"]),
                "portfolios": data["portfolios"],
            })

        results.sort(key=lambda r: r["total_current_value"], reverse=True)
        return results

    # ------------------------------------------------------------------ #
    # Overlap Analysis
    # ------------------------------------------------------------------ #
    def find_overlapping_securities(
        self,
        portfolios_with_holdings: List[Tuple[InvestmentPortfolio, List[InvestmentHolding]]],
    ) -> dict:
        """
        Identify securities that appear in more than one portfolio.

        Returns:
            Dict with total counts, overlap list, and overlap percentage
        """
        symbol_portfolio_map: Dict[str, dict] = defaultdict(lambda: {
            "portfolio_ids": [],
            "portfolio_names": [],
            "security_name": None,
            "total_quantity": Decimal("0"),
            "total_value": Decimal("0"),
        })
        all_symbols: set = set()

        for portfolio, holdings in portfolios_with_holdings:
            portfolio_symbols: set = set()
            for h in holdings:
                if h.is_closed:
                    continue
                sym = h.security_symbol.upper()
                all_symbols.add(sym)
                portfolio_symbols.add(sym)
                entry = symbol_portfolio_map[sym]
                if not entry["security_name"]:
                    entry["security_name"] = h.security_name or sym
                entry["total_quantity"] += Decimal(str(h.quantity or 0))
                entry["total_value"] += h.current_value

            # Record portfolio presence per symbol
            for sym in portfolio_symbols:
                symbol_portfolio_map[sym]["portfolio_ids"].append(portfolio.id)
                symbol_portfolio_map[sym]["portfolio_names"].append(portfolio.name)

        overlaps = []
        for sym, data in symbol_portfolio_map.items():
            if len(data["portfolio_ids"]) > 1:
                overlaps.append({
                    "security_symbol": sym,
                    "security_name": data["security_name"],
                    "portfolio_ids": data["portfolio_ids"],
                    "portfolio_names": data["portfolio_names"],
                    "portfolio_count": len(data["portfolio_ids"]),
                    "total_quantity": float(data["total_quantity"]),
                    "total_value": float(data["total_value"]),
                })

        overlaps.sort(key=lambda o: o["total_value"], reverse=True)
        total_unique = len(all_symbols)
        overlap_count = len(overlaps)
        overlap_pct = (overlap_count / total_unique * 100) if total_unique > 0 else 0.0

        return {
            "total_unique_securities": total_unique,
            "overlapping_securities_count": overlap_count,
            "overlap_percentage": round(overlap_pct, 2),
            "portfolio_count": len(portfolios_with_holdings),
            "overlap_details": overlaps,
        }

    # ------------------------------------------------------------------ #
    # Per-Stock Comparison
    # ------------------------------------------------------------------ #
    def compare_stock_across_portfolios(
        self,
        symbol: str,
        portfolios_with_holdings: List[Tuple[InvestmentPortfolio, List[InvestmentHolding]]],
    ) -> dict:
        """
        For a given security symbol, compare its metrics across every portfolio
        that holds it.

        Returns:
            Dict with symbol, aggregated totals and per-portfolio breakdown
        """
        symbol_upper = symbol.upper()
        per_portfolio = []
        total_qty = Decimal("0")
        total_cost = Decimal("0")
        total_value = Decimal("0")
        security_name = symbol_upper

        for portfolio, holdings in portfolios_with_holdings:
            for h in holdings:
                if h.is_closed:
                    continue
                if h.security_symbol.upper() != symbol_upper:
                    continue

                qty = Decimal(str(h.quantity or 0))
                cost = Decimal(str(h.cost_basis or 0))
                value = h.current_value
                gl = h.unrealized_gain_loss
                gl_pct = (gl / cost * 100) if cost > 0 else Decimal("0")
                avg_cost = (cost / qty) if qty > 0 else Decimal("0")
                security_name = h.security_name or symbol_upper

                total_qty += qty
                total_cost += cost
                total_value += value

                per_portfolio.append({
                    "portfolio_id": portfolio.id,
                    "portfolio_name": portfolio.name,
                    "portfolio_type": portfolio.portfolio_type.value if portfolio.portfolio_type else None,
                    "quantity": float(qty),
                    "avg_cost_per_share": float(avg_cost),
                    "cost_basis": float(cost),
                    "current_value": float(value),
                    "current_price": float(h.effective_price) if h.effective_price else None,
                    "unrealized_gain_loss": float(gl),
                    "gain_loss_pct": float(gl_pct),
                })

        total_gl = total_value - total_cost
        total_gl_pct = (total_gl / total_cost * 100) if total_cost > 0 else Decimal("0")

        return {
            "security_symbol": symbol_upper,
            "security_name": security_name,
            "found_in_portfolios": len(per_portfolio),
            "total_quantity": float(total_qty),
            "total_cost_basis": float(total_cost),
            "total_current_value": float(total_value),
            "total_unrealized_gain_loss": float(total_gl),
            "total_gain_loss_pct": float(total_gl_pct),
            "portfolios": per_portfolio,
        }

    # ------------------------------------------------------------------ #
    # Exposure / Concentration Report
    # ------------------------------------------------------------------ #
    def calculate_total_exposure(
        self,
        portfolios_with_holdings: List[Tuple[InvestmentPortfolio, List[InvestmentHolding]]],
    ) -> dict:
        """
        Calculate each security's total exposure as a percentage of the
        combined portfolio value. This highlights concentration risk.

        Returns:
            Dict with total combined value and per-security exposures
        """
        symbol_values: Dict[str, dict] = {}
        combined_value = Decimal("0")

        for portfolio, holdings in portfolios_with_holdings:
            for h in holdings:
                if h.is_closed:
                    continue
                sym = h.security_symbol.upper()
                value = h.current_value
                combined_value += value

                if sym not in symbol_values:
                    symbol_values[sym] = {
                        "security_symbol": sym,
                        "security_name": h.security_name or sym,
                        "total_value": Decimal("0"),
                        "portfolio_ids": set(),
                    }
                symbol_values[sym]["total_value"] += value
                symbol_values[sym]["portfolio_ids"].add(portfolio.id)

        exposures = []
        for data in symbol_values.values():
            pct = (data["total_value"] / combined_value * 100) if combined_value > 0 else Decimal("0")
            exposures.append({
                "security_symbol": data["security_symbol"],
                "security_name": data["security_name"],
                "total_value": float(data["total_value"]),
                "pct_of_total": float(pct),
                "portfolio_count": len(data["portfolio_ids"]),
            })

        exposures.sort(key=lambda e: e["pct_of_total"], reverse=True)

        # Identify concentration warnings (> 20% in a single security)
        concentration_warnings = [e for e in exposures if e["pct_of_total"] > 20]

        return {
            "total_combined_value": float(combined_value),
            "securities_count": len(exposures),
            "concentration_warnings_count": len(concentration_warnings),
            "concentration_warnings": concentration_warnings,
            "exposures": exposures,
        }

    # ------------------------------------------------------------------ #
    # Monthly Performance Comparison
    # ------------------------------------------------------------------ #
    def generate_monthly_comparison(
        self,
        portfolios_with_data: List[Tuple[InvestmentPortfolio, List[InvestmentHolding], List[InvestmentTransaction]]],
        months: int = 6,
    ) -> dict:
        """
        Compare month-over-month activity and current snapshot across portfolios.

        Uses transaction data to compute monthly buy/sell/dividend totals,
        then combines with current holding values for comparison.

        Args:
            portfolios_with_data: List of (portfolio, holdings, transactions) tuples
            months: How many months of history to include

        Returns:
            Dict with per-portfolio monthly breakdown and aggregate totals
        """
        today = date.today()
        # Build month boundaries
        month_keys = []
        for i in range(months - 1, -1, -1):
            y = today.year
            m = today.month - i
            while m <= 0:
                m += 12
                y -= 1
            month_keys.append(f"{y}-{m:02d}")

        cutoff_date = date(
            int(month_keys[0][:4]),
            int(month_keys[0][5:7]),
            1,
        )

        portfolio_results = []
        aggregate_months: Dict[str, dict] = {mk: {
            "buys": Decimal("0"), "sells": Decimal("0"),
            "dividends": Decimal("0"), "fees": Decimal("0"),
        } for mk in month_keys}

        for portfolio, holdings, transactions in portfolios_with_data:
            # Current snapshot
            current_value = sum(
                (h.current_value for h in holdings if not h.is_closed), Decimal("0")
            )
            current_cost = sum(
                (Decimal(str(h.cost_basis or 0)) for h in holdings if not h.is_closed), Decimal("0")
            )
            current_gl = current_value - current_cost

            # Monthly transaction breakdown
            monthly_data: Dict[str, dict] = {}
            for mk in month_keys:
                monthly_data[mk] = {
                    "buys": Decimal("0"),
                    "sells": Decimal("0"),
                    "dividends": Decimal("0"),
                    "fees": Decimal("0"),
                    "net_flow": Decimal("0"),
                }

            for t in transactions:
                if t.transaction_date < cutoff_date:
                    continue
                mk = f"{t.transaction_date.year}-{t.transaction_date.month:02d}"
                if mk not in monthly_data:
                    continue
                amt = Decimal(str(t.total_amount or 0))
                if t.transaction_type == TransactionType.BUY:
                    monthly_data[mk]["buys"] += amt
                    aggregate_months[mk]["buys"] += amt
                elif t.transaction_type == TransactionType.SELL:
                    monthly_data[mk]["sells"] += amt
                    aggregate_months[mk]["sells"] += amt
                elif t.transaction_type == TransactionType.DIVIDEND:
                    monthly_data[mk]["dividends"] += amt
                    aggregate_months[mk]["dividends"] += amt
                elif t.transaction_type == TransactionType.FEE:
                    monthly_data[mk]["fees"] += amt
                    aggregate_months[mk]["fees"] += amt

            # Calculate net flow
            for mk in month_keys:
                d = monthly_data[mk]
                d["net_flow"] = d["sells"] + d["dividends"] - d["buys"] - d["fees"]

            # Serialise
            months_list = []
            for mk in month_keys:
                d = monthly_data[mk]
                months_list.append({
                    "month": mk,
                    "buys": float(d["buys"]),
                    "sells": float(d["sells"]),
                    "dividends": float(d["dividends"]),
                    "fees": float(d["fees"]),
                    "net_flow": float(d["net_flow"]),
                })

            portfolio_results.append({
                "portfolio_id": portfolio.id,
                "portfolio_name": portfolio.name,
                "portfolio_type": portfolio.portfolio_type.value if portfolio.portfolio_type else None,
                "current_value": float(current_value),
                "current_cost_basis": float(current_cost),
                "current_gain_loss": float(current_gl),
                "months": months_list,
            })

        # Build aggregate months list
        agg_months_list = []
        for mk in month_keys:
            d = aggregate_months[mk]
            agg_months_list.append({
                "month": mk,
                "buys": float(d["buys"]),
                "sells": float(d["sells"]),
                "dividends": float(d["dividends"]),
                "fees": float(d["fees"]),
                "net_flow": float(d["sells"] + d["dividends"] - d["buys"] - d["fees"]),
            })

        total_combined = sum(p["current_value"] for p in portfolio_results)

        return {
            "months_analyzed": months,
            "month_keys": month_keys,
            "portfolio_count": len(portfolio_results),
            "total_combined_value": total_combined,
            "portfolios": portfolio_results,
            "aggregate_months": agg_months_list,
        }
