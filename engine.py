"""
engine.py — Oriel Prediction Index Engine
Transformation layer: prediction prices → discrete distribution → expected value → index print.

Structure:
  PredictionForwardCurve   — lower-level curve builder
  IndexMethodology         — methodology metadata dataclass
  IndexPrint               — published index snapshot dataclass
  PredictionIndexAdmin     — orchestrator / admin console layer
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from math import sqrt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Contract primitives
# ---------------------------------------------------------------------------

@dataclass
class PriceSelection:
    chosen_price: float
    chosen_price_reason: str
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    is_stale: bool = False
    is_excluded: bool = False


@dataclass
class ContractObservation:
    contract_ticker: Optional[str] = None
    source_venue: Optional[str] = None
    snapshot_timestamp: Optional[datetime] = None
    settlement_label: Optional[str] = None
    contract_type: Optional[str] = None
    open_interest: Optional[float] = None
    volume: Optional[float] = None
    price_selection: Optional[PriceSelection] = None


@dataclass
class BucketContract:
    label: str
    lower: float
    upper: float
    price: float
    observation: Optional[ContractObservation] = None

    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0


@dataclass
class BinaryThresholdContract:
    label: str
    threshold: float
    price: float
    observation: Optional[ContractObservation] = None


@dataclass
class ExactOutcomeContract:
    label: str
    value: float
    price: float
    observation: Optional[ContractObservation] = None


@dataclass
class MaturitySnapshot:
    maturity: date
    scalar_buckets: List[BucketContract] = field(default_factory=list)
    binary_thresholds: List[BinaryThresholdContract] = field(default_factory=list)
    exact_outcomes: List[ExactOutcomeContract] = field(default_factory=list)


@dataclass
class ForwardPoint:
    maturity: date
    ttm_years: float
    expected_value: float
    variance: Optional[float] = None
    std_dev: Optional[float] = None
    source: str = "scalar"


# ---------------------------------------------------------------------------
# Index methodology + print
# ---------------------------------------------------------------------------

@dataclass
class IndexMethodology:
    index_name: str
    methodology_version: str
    price_basis: str = "probability_midpoint"
    interpolation_method: str = "linear"
    weighting_rule: str = "front_anchor_base_100"
    smoothing_rule: str = "isotonic_monotone_survival"
    stale_market_rule: str = "flag_only"
    fallback_rule: str = "raise_on_empty_curve"
    publication_frequency: str = "on_demand"
    unit_label: str = "%"


@dataclass
class IndexConstituent:
    maturity: date
    expected_value: float
    index_level: float
    source: str
    weight: float = 1.0
    std_dev: Optional[float] = None
    flagged: bool = False


@dataclass
class IndexPrint:
    index_name: str
    methodology_version: str
    valuation_time: datetime
    base_value: float
    anchor_expected_value: float
    index_level: float
    publishable: bool
    constituents: List[IndexConstituent]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index_name": self.index_name,
            "methodology_version": self.methodology_version,
            "valuation_time": self.valuation_time.isoformat(),
            "base_value": self.base_value,
            "anchor_expected_value": self.anchor_expected_value,
            "index_level": round(self.index_level, 4),
            "publishable": self.publishable,
            "constituents": [
                {
                    "maturity": c.maturity.isoformat(),
                    "expected_value": round(c.expected_value, 6),
                    "index_level": round(c.index_level, 4),
                    "source": c.source,
                    "weight": c.weight,
                    "std_dev": round(c.std_dev, 6) if c.std_dev is not None else None,
                    "flagged": c.flagged,
                }
                for c in self.constituents
            ],
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Core curve engine
# ---------------------------------------------------------------------------

class CurveError(ValueError):
    pass


class PredictionForwardCurve:
    def __init__(self, valuation_date: date, methodology: Optional[IndexMethodology] = None):
        self.valuation_date = valuation_date
        self.methodology = methodology or IndexMethodology(
            index_name="Prediction Forward Index",
            methodology_version="0.1.0",
        )
        self.points: List[ForwardPoint] = []

    @staticmethod
    def _year_fraction(start: date, end: date) -> float:
        return max((end - start).days / 365.25, 0.0)

    @staticmethod
    def _normalize_probabilities(weights: Sequence[float]) -> List[float]:
        total = sum(max(w, 0.0) for w in weights)
        if total <= 0:
            raise CurveError("Probabilities sum to zero; cannot normalize.")
        return [max(w, 0.0) / total for w in weights]

    @staticmethod
    def _expected_from_scalar_buckets(buckets: Sequence[BucketContract]) -> Tuple[float, float]:
        if not buckets:
            raise CurveError("No scalar buckets provided.")
        probs = PredictionForwardCurve._normalize_probabilities([b.price for b in buckets])
        mids = [b.midpoint() for b in buckets]
        mean = sum(p * x for p, x in zip(probs, mids))
        variance = sum(p * (x - mean) ** 2 for p, x in zip(probs, mids))
        return mean, variance

    @staticmethod
    def _isotonic_decreasing(
        x: Sequence[float],
        y: Sequence[float],
        weights: Optional[Sequence[float]] = None,
    ) -> List[float]:
        """
        Weighted pool-adjacent-violators algorithm (PAVA) for a non-increasing fit.

        This fits a monotone survival curve to noisy binary threshold prices while
        preserving the original threshold grid. If the raw inputs are already
        monotone, the fit returns them unchanged apart from clipping to [0, 1].
        """
        if len(x) != len(y):
            raise CurveError("x and y must have the same length for isotonic fit.")
        if len(x) < 2:
            raise CurveError("Need at least two points for isotonic fit.")

        pairs = sorted(
            zip(x, y, weights or [1.0] * len(y)),
            key=lambda row: row[0],
        )
        blocks: List[Dict[str, Any]] = []

        for xi, yi, wi in pairs:
            wi = max(float(wi), 1e-12)
            yi = min(max(float(yi), 0.0), 1.0)
            block = {
                "weight": wi,
                "sum": yi * wi,
                "mean": yi,
                "count": 1,
            }
            blocks.append(block)

            while len(blocks) >= 2 and blocks[-2]["mean"] < blocks[-1]["mean"]:
                right = blocks.pop()
                left = blocks.pop()
                merged_weight = left["weight"] + right["weight"]
                merged_sum = left["sum"] + right["sum"]
                blocks.append({
                    "weight": merged_weight,
                    "sum": merged_sum,
                    "mean": merged_sum / merged_weight,
                    "count": left["count"] + right["count"],
                })

        fitted_sorted: List[float] = []
        for block in blocks:
            fitted_sorted.extend([block["mean"]] * block["count"])

        x_sorted = [xi for xi, _, _ in pairs]
        fitted_lookup = {xi: fi for xi, fi in zip(x_sorted, fitted_sorted)}
        return [fitted_lookup[xi] for xi in x]

    @staticmethod
    def _smooth_monotone_survival(
        thresholds: Sequence[BinaryThresholdContract],
    ) -> List[Tuple[float, float]]:
        """
        Fit a non-increasing survival curve using isotonic regression and then
        lightly smooth pooled plateaus for presentation without breaking monotonicity.
        """
        sorted_thresholds = sorted(thresholds, key=lambda t: t.threshold)
        xs = [t.threshold for t in sorted_thresholds]
        ys = [min(max(t.price, 0.0), 1.0) for t in sorted_thresholds]

        weights: List[float] = []
        for t in sorted_thresholds:
            oi = max(float(t.observation.open_interest), 0.0) if t.observation and t.observation.open_interest is not None else 0.0
            vol = max(float(t.observation.volume), 0.0) if t.observation and t.observation.volume is not None else 0.0
            spread_penalty = 1.0
            if t.observation and t.observation.price_selection:
                bid = t.observation.price_selection.bid
                ask = t.observation.price_selection.ask
                if bid is not None and ask is not None and ask >= bid:
                    spread_penalty = 1.0 / max((ask - bid) * 100.0, 1.0)
            weights.append(max(1.0 + sqrt(oi) + 0.25 * sqrt(vol), 1e-6) * spread_penalty)

        fitted = PredictionForwardCurve._isotonic_decreasing(xs, ys, weights)

        smoothed = fitted[:]
        n = len(smoothed)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and abs(smoothed[j + 1] - smoothed[i]) < 1e-12:
                j += 1
            if i > 0 and j < n - 1 and j > i:
                left = smoothed[i - 1]
                right = smoothed[j + 1]
                if left > right:
                    step = (left - right) / (j - i + 2)
                    for k in range(i, j + 1):
                        candidate = left - step * (k - i + 1)
                        smoothed[k] = min(max(candidate, right), left)
            i = j + 1

        final_fit = PredictionForwardCurve._isotonic_decreasing(xs, smoothed, [1.0] * len(smoothed))
        return list(zip(xs, final_fit))

    @staticmethod
    def _expected_from_binary_thresholds(thresholds: Sequence[BinaryThresholdContract]) -> Tuple[float, float]:
        if len(thresholds) < 2:
            raise CurveError("Need at least two binary thresholds to infer a distribution.")

        monotonic_survival = PredictionForwardCurve._smooth_monotone_survival(thresholds)

        bucket_probs: List[float] = []
        bucket_mids: List[float] = []

        first_k, first_s = monotonic_survival[0]
        floor_width = max(monotonic_survival[1][0] - monotonic_survival[0][0], 0.1)
        bucket_probs.append(max(1.0 - first_s, 0.0))
        bucket_mids.append(first_k - floor_width / 2.0)

        for i in range(len(monotonic_survival) - 1):
            k0, s0 = monotonic_survival[i]
            k1, s1 = monotonic_survival[i + 1]
            bucket_probs.append(max(s0 - s1, 0.0))
            bucket_mids.append((k0 + k1) / 2.0)

        tail_width = max(monotonic_survival[-1][0] - monotonic_survival[-2][0], 0.1)
        bucket_probs.append(max(monotonic_survival[-1][1], 0.0))
        bucket_mids.append(monotonic_survival[-1][0] + tail_width / 2.0)

        probs = PredictionForwardCurve._normalize_probabilities(bucket_probs)
        mean = sum(p * x for p, x in zip(probs, bucket_mids))
        variance = sum(p * (x - mean) ** 2 for p, x in zip(probs, bucket_mids))
        return mean, variance

    COVERAGE_THRESHOLD: float = 0.90  # if observed prices sum below this, add residual tails

    @staticmethod
    def _expected_from_exact_outcomes(outcomes: Sequence[ExactOutcomeContract]) -> Tuple[float, float]:
        if not outcomes:
            raise CurveError("No exact outcomes provided.")

        raw_total = sum(max(o.price, 0.0) for o in outcomes)
        values = [o.value for o in outcomes]
        prices = [max(o.price, 0.0) for o in outcomes]

        # If coverage is materially below 1.0, add explicit residual tail buckets
        # so the missing probability mass is visible rather than silently absorbed
        if raw_total < PredictionForwardCurve.COVERAGE_THRESHOLD:
            residual = max(1.0 - raw_total, 0.0)
            sorted_vals = sorted(values)
            # Infer grid spacing from observed values
            if len(sorted_vals) >= 2:
                step = (sorted_vals[-1] - sorted_vals[0]) / max(len(sorted_vals) - 1, 1)
            else:
                step = 0.1
            step = max(step, 0.1)
            left_tail_value = sorted_vals[0] - step
            right_tail_value = sorted_vals[-1] + step
            # Split residual evenly across left and right tails
            half = residual / 2.0
            values = [left_tail_value] + values + [right_tail_value]
            prices = [half] + prices + [half]

        probs = PredictionForwardCurve._normalize_probabilities(prices)
        mean = sum(p * x for p, x in zip(probs, values))
        variance = sum(p * (x - mean) ** 2 for p, x in zip(probs, values))
        return mean, variance

    def add_snapshot(self, snapshot: MaturitySnapshot) -> ForwardPoint:
        ttm = self._year_fraction(self.valuation_date, snapshot.maturity)
        if snapshot.scalar_buckets:
            mean, variance = self._expected_from_scalar_buckets(snapshot.scalar_buckets)
            source = "scalar"
        elif snapshot.binary_thresholds:
            mean, variance = self._expected_from_binary_thresholds(snapshot.binary_thresholds)
            source = "binary"
        elif snapshot.exact_outcomes:
            mean, variance = self._expected_from_exact_outcomes(snapshot.exact_outcomes)
            source = "exact"
        else:
            raise CurveError("Snapshot must contain scalar buckets, binary thresholds, or exact outcomes.")
        point = ForwardPoint(
            maturity=snapshot.maturity,
            ttm_years=ttm,
            expected_value=mean,
            variance=variance,
            std_dev=sqrt(variance),
            source=source,
        )
        self.points.append(point)
        self.points.sort(key=lambda p: p.maturity)
        return point

    def add_snapshots(self, snapshots: Iterable[MaturitySnapshot]) -> List[ForwardPoint]:
        return [self.add_snapshot(s) for s in snapshots]

    def curve(self) -> List[ForwardPoint]:
        return list(self.points)

    def interpolate(self, target_date: date) -> float:
        if not self.points:
            raise CurveError("Curve is empty.")
        pts = sorted(self.points, key=lambda p: p.maturity)
        if target_date <= pts[0].maturity:
            return pts[0].expected_value
        if target_date >= pts[-1].maturity:
            return pts[-1].expected_value
        for left, right in zip(pts[:-1], pts[1:]):
            if left.maturity <= target_date <= right.maturity:
                total_days = (right.maturity - left.maturity).days
                elapsed_days = (target_date - left.maturity).days
                weight = elapsed_days / total_days if total_days > 0 else 0.0
                return left.expected_value + weight * (right.expected_value - left.expected_value)
        raise CurveError("Interpolation failed unexpectedly.")

    def to_index(self, base_value: float = 100.0, anchor_expected_value: Optional[float] = None) -> List[Dict]:
        if not self.points:
            raise CurveError("Curve is empty.")
        anchor = anchor_expected_value if anchor_expected_value is not None else self.points[0].expected_value
        if anchor == 0:
            raise CurveError("Anchor expected value cannot be zero.")
        rows = []
        for p in self.points:
            rows.append({
                "maturity": p.maturity.isoformat(),
                "ttm_years": round(p.ttm_years, 4),
                "expected_value": round(p.expected_value, 6),
                "index_level": round(base_value * (p.expected_value / anchor), 4),
                "std_dev": round(p.std_dev, 6) if p.std_dev is not None else None,
                "source": p.source,
            })
        return rows

    def publish_index(
        self,
        base_value: float = 100.0,
        anchor_expected_value: Optional[float] = None,
        valuation_time: Optional[datetime] = None,
    ) -> IndexPrint:
        if not self.points:
            raise CurveError("Curve is empty.")
        valuation_time = valuation_time or datetime.combine(self.valuation_date, datetime.min.time())
        anchor = anchor_expected_value if anchor_expected_value is not None else self.points[0].expected_value
        if anchor == 0:
            raise CurveError("Anchor expected value cannot be zero.")
        constituents: List[IndexConstituent] = []
        notes: List[str] = []
        for p in self.points:
            level = base_value * (p.expected_value / anchor)
            constituents.append(IndexConstituent(
                maturity=p.maturity,
                expected_value=p.expected_value,
                index_level=level,
                source=p.source,
                std_dev=p.std_dev,
            ))
        return IndexPrint(
            index_name=self.methodology.index_name,
            methodology_version=self.methodology.methodology_version,
            valuation_time=valuation_time,
            base_value=base_value,
            anchor_expected_value=anchor,
            index_level=constituents[0].index_level if constituents else base_value,
            publishable=len(constituents) > 0,
            constituents=constituents,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Index Admin orchestrator
# ---------------------------------------------------------------------------

class PredictionIndexAdmin:
    """
    High-level admin layer above PredictionForwardCurve.
    Responsible for: running the methodology, publishing the index print,
    and returning structured outputs for the UI.
    """

    def __init__(self, methodology: IndexMethodology, valuation_date: date):
        self.methodology = methodology
        self.valuation_date = valuation_date
        self._curve: Optional[PredictionForwardCurve] = None

    def run(self, snapshots: List[MaturitySnapshot]) -> IndexPrint:
        self._curve = PredictionForwardCurve(
            valuation_date=self.valuation_date,
            methodology=self.methodology,
        )
        self._curve.add_snapshots(snapshots)
        return self._curve.publish_index(
            base_value=100.0,
            valuation_time=datetime.combine(self.valuation_date, datetime.min.time()),
        )

    def curve(self) -> List[ForwardPoint]:
        if self._curve is None:
            return []
        return self._curve.curve()

    def to_dataframe_rows(self) -> List[Dict]:
        if self._curve is None:
            return []
        return self._curve.to_index(base_value=100.0)
