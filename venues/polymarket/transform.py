from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import pstdev
from typing import Iterable

from .client import PolymarketClient
from .config import PolymarketConfig
from .models import PolyCurvePackage, PolyCurvePoint, PolymarketContract

UTC = timezone.utc
MONTH_ORDER = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


@dataclass
class VenueEligibilitySummary:
    venue_status: str
    reference_status: str
    publishable: bool
    reason: str
    eligible_render_count: int
    eligible_publish_count: int
    maturity_count_render: int
    maturity_count_publish: int


def _release_month_label_sort_key(label: str) -> tuple[int, int]:
    parts = label.split()
    if len(parts) == 2 and parts[0][:3].title() in MONTH_ORDER:
        return (int(parts[1]), MONTH_ORDER[parts[0][:3].title()])
    return (9999, 99)


def release_month_sort_key(contract: PolymarketContract) -> tuple[int, int]:
    return _release_month_label_sort_key(contract.release_month)


def _distinct_maturities(contracts: Iterable[PolymarketContract]) -> list[str]:
    return sorted({c.release_month for c in contracts if getattr(c, "release_month", None)}, key=_release_month_label_sort_key)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def spread_score(spread_bp: float | None, config: PolymarketConfig) -> float:
    if spread_bp is None:
        return 0.0
    if spread_bp <= 50:
        return 1.00
    if spread_bp <= 150:
        return 0.85
    if spread_bp <= config.preferred_spread_bp:
        return 0.65
    if spread_bp <= 300:
        return 0.45
    if spread_bp <= config.max_spread_bp_render:
        return 0.20
    return 0.0


def depth_score(has_depth: bool, depth_usd: float | None = None) -> float:
    if has_depth is False:
        return 0.25
    if depth_usd is None:
        return 0.60
    if depth_usd >= 5000:
        return 1.0
    if depth_usd >= 2000:
        return 0.8
    if depth_usd >= 500:
        return 0.55
    return 0.30


def freshness_score(age_seconds: int | None, config: PolymarketConfig) -> float:
    if age_seconds is None:
        return 0.40
    return _clamp(1.0 - (age_seconds / max(config.max_quote_age_seconds, 1)))


def maturity_score(total_distinct_maturities: int) -> float:
    if total_distinct_maturities >= 6:
        return 1.0
    if total_distinct_maturities >= 4:
        return 0.8
    if total_distinct_maturities >= 2:
        return 0.5
    return 0.0


def compute_contract_confidence(contract: PolymarketContract, total_distinct_maturities: int, config: PolymarketConfig) -> float:
    spread_bp = (contract.spread * 10000.0) if contract.spread is not None else None
    s = spread_score(spread_bp, config)
    d = depth_score(getattr(contract, "has_depth", False), getattr(contract, "depth_usd", None))
    f = freshness_score(getattr(contract, "quote_age_seconds", None), config)
    m = maturity_score(total_distinct_maturities)
    score = (
        config.weight_spread * s
        + config.weight_depth * d
        + config.weight_freshness * f
        + config.weight_maturity * m
    )
    return round(100.0 * _clamp(score), 1)


def _passes_render_gate(contract: PolymarketContract, config: PolymarketConfig) -> bool:
    if contract.expected_value is None:
        return False
    if contract.spread is None:
        return False
    if contract.spread * 10000.0 > config.max_spread_bp_render:
        return False
    if getattr(contract, "is_stale", False):
        return False
    if getattr(contract, "has_valid_quote", True) is False:
        return False
    if (contract.volume or 0) < config.min_volume:
        return False
    if (contract.open_interest or 0) < config.min_open_interest:
        return False
    return True


def _passes_publish_gate(contract: PolymarketContract, config: PolymarketConfig) -> bool:
    if not _passes_render_gate(contract, config):
        return False
    if contract.spread is None:
        return False
    if contract.spread * 10000.0 > config.max_spread_bp_publish:
        return False
    if config.min_depth_required and not getattr(contract, "has_depth", False):
        return False
    return True


def summarize_venue_eligibility(contracts: list[PolymarketContract], config: PolymarketConfig) -> VenueEligibilitySummary:
    render_eligible = [c for c in contracts if _passes_render_gate(c, config)]
    publish_eligible = [c for c in contracts if _passes_publish_gate(c, config)]
    render_maturities = _distinct_maturities(render_eligible)
    publish_maturities = _distinct_maturities(publish_eligible)

    if len(render_maturities) < config.min_maturities_render:
        return VenueEligibilitySummary(
            venue_status="insufficient",
            reference_status="not_eligible",
            publishable=False,
            reason="Insufficient maturity coverage for venue rendering",
            eligible_render_count=len(render_eligible),
            eligible_publish_count=len(publish_eligible),
            maturity_count_render=len(render_maturities),
            maturity_count_publish=len(publish_maturities),
        )

    if len(publish_maturities) < config.min_maturities_publish:
        return VenueEligibilitySummary(
            venue_status="partial",
            reference_status="not_eligible",
            publishable=False,
            reason="Venue curve available, but insufficient maturity coverage for official publication",
            eligible_render_count=len(render_eligible),
            eligible_publish_count=len(publish_eligible),
            maturity_count_render=len(render_maturities),
            maturity_count_publish=len(publish_maturities),
        )

    return VenueEligibilitySummary(
        venue_status="live",
        reference_status="eligible" if config.counts_toward_oriel_blend else "not_eligible",
        publishable=True,
        reason="Satisfies venue publication thresholds",
        eligible_render_count=len(render_eligible),
        eligible_publish_count=len(publish_eligible),
        maturity_count_render=len(render_maturities),
        maturity_count_publish=len(publish_maturities),
    )


def score_and_package(
    contracts: list[PolymarketContract],
    source_status: str,
    config: PolymarketConfig,
    prior_curve: list[float] | None = None,
) -> PolyCurvePackage:
    valuation_timestamp = datetime.now(UTC)

    for contract in contracts:
        contract.expected_value = normalize_expected_value(contract)

    total_distinct_maturities = len(_distinct_maturities([c for c in contracts if c.expected_value is not None]))
    for contract in contracts:
        contract.confidence_score = compute_contract_confidence(contract, total_distinct_maturities, config)
        contract.publishable = _passes_publish_gate(contract, config)
        contract.publishability_reason = publishability_reason(contract, config)

    render_eligible = [contract for contract in contracts if _passes_render_gate(contract, config) and contract.expected_value is not None]
    best_by_month: dict[str, PolymarketContract] = {}
    for contract in render_eligible:
        month = contract.release_month
        incumbent = best_by_month.get(month)
        contract_rank = (contract.confidence_score, -(contract.spread or 999), contract.volume or 0, contract.open_interest or 0)
        incumbent_rank = None if incumbent is None else (incumbent.confidence_score, -(incumbent.spread or 999), incumbent.volume or 0, incumbent.open_interest or 0)
        if incumbent is None or contract_rank > incumbent_rank:
            best_by_month[month] = contract
    render_eligible = sorted(best_by_month.values(), key=release_month_sort_key)[: config.max_curve_points]

    eligibility = summarize_venue_eligibility(contracts, config)

    if not render_eligible:
        return PolyCurvePackage(
            valuation_timestamp=valuation_timestamp,
            points=[],
            contracts=contracts,
            source_status=source_status,
            publishable=False,
            publishability_reason=eligibility.reason,
            sample_mode=source_status == "FALLBACK",
            venue_status=eligibility.venue_status,
            reference_status=eligibility.reference_status,
            counts_toward_oriel_blend=config.counts_toward_oriel_blend,
        )

    expected_values = [contract.expected_value for contract in render_eligible if contract.expected_value is not None]
    sigma = pstdev(expected_values) if len(expected_values) > 1 else 0.08
    if prior_curve is None:
        prior_curve = [round(max(value + 0.015, 0.0), 4) for value in expected_values]

    points: list[PolyCurvePoint] = []
    publishable_months = set(_distinct_maturities([c for c in contracts if _passes_publish_gate(c, config)]))
    for index, contract in enumerate(render_eligible):
        implied = contract.expected_value or 0.0
        points.append(
            PolyCurvePoint(
                label=contract.release_month,
                release_month=contract.release_month,
                implied_yoy=round(implied, 4),
                lower_band=round(max(implied - sigma, -0.25), 4),
                upper_band=round(implied + sigma, 4),
                prior_curve_yoy=prior_curve[index] if index < len(prior_curve) else None,
                volume=float(contract.volume or 0),
                open_interest=float(contract.open_interest or 0),
                spread_bp=round((contract.spread or 0.0) * 10000.0, 1) if contract.spread is not None else None,
                confidence_score=round(contract.confidence_score, 1),
                publishable=contract.release_month in publishable_months,
                market_id=contract.market_id,
            )
        )

    return PolyCurvePackage(
        valuation_timestamp=valuation_timestamp,
        points=points,
        contracts=contracts,
        source_status=source_status,
        publishable=eligibility.publishable,
        publishability_reason=eligibility.reason,
        sample_mode=source_status == "FALLBACK",
        venue_status=eligibility.venue_status,
        reference_status=eligibility.reference_status,
        counts_toward_oriel_blend=config.counts_toward_oriel_blend,
    )


def normalize_expected_value(contract: PolymarketContract) -> float | None:
    if contract.threshold is None or contract.mid is None:
        return None
    probability = float(contract.mid)
    direction = PolymarketClient.extract_threshold_direction(contract.question or contract.slug)
    if direction == "below":
        probability = 1.0 - probability
    outcome_label = (contract.outcome or "").strip().lower()
    if outcome_label in {"no"}:
        probability = 1.0 - probability
    probability = max(0.0, min(1.0, probability))
    return round(float(contract.threshold) + (probability - 0.5) * 0.5, 4)


def is_publishable(contract: PolymarketContract, config: PolymarketConfig) -> bool:
    return _passes_publish_gate(contract, config)


def publishability_reason(contract: PolymarketContract, config: PolymarketConfig) -> str:
    if contract.expected_value is None:
        return "missing expected value"
    if (contract.volume or 0) < config.min_volume:
        return "low volume"
    if (contract.open_interest or 0) < config.min_open_interest:
        return "low open interest"
    if contract.spread is None:
        return "missing spread"
    spread_bp = contract.spread * 10000.0
    if spread_bp > config.max_spread_bp_render:
        return "wide spread"
    if getattr(contract, "is_stale", False) or (
        contract.last_updated is not None and contract.last_updated < datetime.now(UTC) - timedelta(hours=config.stale_after_hours)
    ):
        return "stale quote"
    if spread_bp > config.max_spread_bp_publish:
        return "diagnostic only"
    if config.min_depth_required and not getattr(contract, "has_depth", False):
        return "insufficient depth"
    return "eligible"
