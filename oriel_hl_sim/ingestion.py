from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Tuple

import pandas as pd

from .common import VenueQuote
from .config.markets import HarnessConfig
from venues.forecastex.client import ForecastExClient
from venues.forecastex.config import ForecastExConfig
from venues.kalshi.live_data import build_live_cpi_feed
from venues.polymarket.client import PolymarketClient
from venues.polymarket.config import PolymarketConfig


def _sample_quotes(path: Path) -> list[VenueQuote]:
    df = pd.read_csv(path)
    out: list[VenueQuote] = []
    for _, r in df.iterrows():
        threshold = float(r['threshold'])
        out.append(VenueQuote(
            venue=str(r['venue']),
            release_month=_normalize_release_month_label(str(r['release_month'])),
            threshold=threshold,
            raw_threshold=threshold,
            normalized_threshold=threshold,
            threshold_units='yoy_pct',
            normalization_method='sample_pass_through',
            methodology_note='Sample row already expressed on implied YoY CPI basis.',
            bid=float(r['bid']) if pd.notna(r['bid']) else None,
            ask=float(r['ask']) if pd.notna(r['ask']) else None,
            mid=float(r['mid']) if pd.notna(r['mid']) else None,
            spread=float(r['spread']) if pd.notna(r['spread']) else None,
            volume=float(r['volume']) if pd.notna(r['volume']) else None,
            open_interest=float(r['open_interest']) if pd.notna(r['open_interest']) else None,
            quote_age_seconds=int(r['quote_age_seconds']) if pd.notna(r['quote_age_seconds']) else None,
            liquidity_score=float(r['liquidity_score']),
            confidence_score=float(r['confidence_score']),
            market_id=str(r['market_id']),
            question=str(r['question']),
            source_status='SAMPLE',
        ))
    return out


def _normalize_release_month_label(label: str) -> str:
    text = str(label).strip()
    if not text:
        return text
    text = text.replace('_', ' ').replace('/', '-').strip()
    # 2026-04 -> Apr 2026
    m = re.match(r'^(20\d{2})-(\d{2})(?:-\d{2})?$', text)
    if m:
        return pd.to_datetime(f"{m.group(1)}-{m.group(2)}-01").strftime('%b %Y')
    # Apr 2026 or April 2026 -> Apr 2026
    try:
        dt = pd.to_datetime(text, errors='raise')
        if pd.notna(dt):
            return dt.strftime('%b %Y')
    except Exception:
        pass
    return text


def _annualize_monthly_pct_to_yoy(monthly_pct: float) -> float:
    """Convert monthly CPI threshold expressed in percentage points to annualized YoY.

    Example: 0.3 -> ((1 + 0.003) ** 12 - 1) * 100.
    """
    monthly_rate = float(monthly_pct) / 100.0
    return ((1.0 + monthly_rate) ** 12 - 1.0) * 100.0


_MONTHLY_HINTS = (
    'm/m', 'mom', 'month-over-month', 'month over month', 'monthly', 'one-month', '1-month'
)
_YEARLY_HINTS = (
    'yoy', 'year-over-year', 'year over year', 'annual', '12-month', '12 month'
)


def _infer_threshold_units(venue: str, threshold: float | None, question: str | None = None) -> tuple[str, str, str]:
    """Infer contract scale and normalization method for venue-to-venue comparison.

    Returns (units, normalization_method, note).
    units ∈ {'mom_pct', 'yoy_pct'}
    """
    q = (question or '').lower()
    threshold = float(threshold or 0.0)

    if venue == 'Kalshi':
        return (
            'mom_pct',
            'compounded_monthly_to_yoy',
            'Kalshi front-end CPI thresholds are normalized from monthly % to annualized implied YoY CPI using (1+m)^12 - 1.',
        )

    if any(h in q for h in _YEARLY_HINTS):
        return 'yoy_pct', 'pass_through', f'{venue} contract text indicates year-over-year CPI; threshold is passed through on YoY basis.'

    if any(h in q for h in _MONTHLY_HINTS):
        return 'mom_pct', 'compounded_monthly_to_yoy', f'{venue} contract text indicates monthly CPI; threshold is annualized to YoY for cross-venue comparison.'

    # Heuristic fallback: thresholds below ~1.5% are unlikely to be headline YoY CPI prints.
    if threshold <= 1.5:
        return 'mom_pct', 'compounded_monthly_to_yoy', f'{venue} threshold appears sub-2%; treating as monthly CPI for first-pass normalization.'

    return 'yoy_pct', 'pass_through', f'{venue} threshold appears already on YoY CPI basis.'



def _normalize_threshold(venue: str, threshold: float | None, question: str | None = None) -> tuple[float | None, str, str, str]:
    if threshold is None:
        return None, 'unknown', 'missing_threshold', f'{venue} contract has no threshold to normalize.'
    units, method, note = _infer_threshold_units(venue, threshold, question)
    if units == 'mom_pct':
        return _annualize_monthly_pct_to_yoy(float(threshold)), units, method, note
    return float(threshold), units, method, note



def _threshold_to_implied_yoy(threshold: float, probability: float | None) -> float:
    """First-pass bridge from normalized threshold level + market probability to implied YoY CPI.

    This keeps the original FalconX harness logic intact while making venue-specific
    threshold normalization explicit upstream.
    """
    p = 0.5 if probability is None else max(0.01, min(0.99, probability))
    return float(threshold) + (p - 0.5) * 0.8



def _ingest_kalshi_front_end(config: HarnessConfig) -> tuple[list[VenueQuote], str]:
    os.environ.setdefault('KALSHI_TIMEOUT_SECONDS', '3')
    os.environ.setdefault('KALSHI_MAX_RETRIES', '1')
    methodology, snapshots, contracts_table, runtime_meta = build_live_cpi_feed()
    if not snapshots:
        return [], 'EMPTY'
    feed_status = runtime_meta.get('feed_status', 'LIVE') if isinstance(runtime_meta, dict) else 'LIVE'
    out: list[VenueQuote] = []
    for snap in snapshots[:config.max_front_months]:
        mat_label = _normalize_release_month_label(str(getattr(snap, 'maturity', '')))
        for bt in snap.binary_thresholds:
            obs = bt.observation
            bid = obs.price_selection.bid if obs and obs.price_selection else None
            ask = obs.price_selection.ask if obs and obs.price_selection else None
            mid = obs.price_selection.chosen_price if obs and obs.price_selection else bt.price
            spread = (ask - bid) if bid is not None and ask is not None else None
            oi = float(obs.open_interest) if obs and obs.open_interest else 0.0
            vol = float(obs.volume) if obs and obs.volume else 0.0
            ticker = obs.contract_ticker if obs else f'KXCPI-{mat_label}-T{bt.threshold}'
            confidence = 1.0 / (1.0 + (spread or 0.0) * 10.0)
            liquidity = min(1.0, (oi + vol) / 500.0)
            normalized_threshold, units, method, note = _normalize_threshold('Kalshi', float(bt.threshold), getattr(bt, 'label', None))
            out.append(VenueQuote(
                venue='Kalshi',
                release_month=mat_label,
                threshold=float(normalized_threshold),
                raw_threshold=float(bt.threshold),
                normalized_threshold=float(normalized_threshold),
                threshold_units=units,
                normalization_method=method,
                methodology_note=note,
                bid=bid, ask=ask, mid=mid, spread=spread,
                volume=vol, open_interest=oi,
                quote_age_seconds=None,
                liquidity_score=liquidity,
                confidence_score=confidence,
                market_id=ticker,
                question=getattr(bt, 'label', f'CPI {mat_label} > {bt.threshold}%'),
                source_status=feed_status,
            ))
    return out, feed_status



def _ingest_polymarket_front_end(config: HarnessConfig) -> tuple[list[VenueQuote], str]:
    os.environ.setdefault('POLYMARKET_REQUEST_TIMEOUT_SECONDS', '3')
    client = PolymarketClient(PolymarketConfig(request_timeout_seconds=int(os.getenv('POLYMARKET_REQUEST_TIMEOUT_SECONDS', '3'))))
    contracts, status = client.fetch_contracts()
    out: list[VenueQuote] = []
    for c in contracts:
        normalized_threshold, units, method, note = _normalize_threshold('Polymarket', c.threshold, c.question)
        if normalized_threshold is None:
            continue
        out.append(VenueQuote(
            venue='Polymarket',
            release_month=_normalize_release_month_label(str(c.release_month)),
            threshold=float(normalized_threshold),
            raw_threshold=float(c.threshold) if c.threshold is not None else None,
            normalized_threshold=float(normalized_threshold),
            threshold_units=units,
            normalization_method=method,
            methodology_note=note,
            bid=c.bid, ask=c.ask, mid=c.mid, spread=c.spread,
            volume=c.volume, open_interest=c.open_interest,
            quote_age_seconds=c.quote_age_seconds,
            liquidity_score=float(c.liquidity_score or 0.0),
            confidence_score=float(c.confidence_score or 0.0),
            market_id=str(c.market_id),
            question=str(c.question),
            source_status=status,
        ))
    return out, status



def _extract_forecastex_threshold(contract) -> float | None:
    """Extract threshold from ForecastEx product_code (e.g. CPIY_0526_4 → 4.0)."""
    pc = getattr(contract, 'product_code', None) or ''
    parts = str(pc).split('_')
    if len(parts) >= 3:
        try:
            return float(parts[-1])
        except (ValueError, TypeError):
            pass
    return getattr(contract, 'threshold', None)


def _ingest_forecastex_front_end(config: HarnessConfig) -> tuple[list[VenueQuote], str]:
    os.environ.setdefault('FORECASTEX_REQUEST_TIMEOUT_SECONDS', '3')
    fx_cfg = ForecastExConfig(request_timeout_seconds=int(os.getenv('FORECASTEX_REQUEST_TIMEOUT_SECONDS', '3')))
    client = ForecastExClient(fx_cfg)
    contracts, status = client.fetch_contracts()
    out: list[VenueQuote] = []
    for c in contracts:
        raw_thr = _extract_forecastex_threshold(c)
        if raw_thr is None:
            continue
        normalized_threshold, units, method, note = _normalize_threshold('ForecastEx', raw_thr, c.event_question)
        if normalized_threshold is None:
            continue
        spread = (c.ask - c.bid) if c.bid is not None and c.ask is not None else None
        confidence = 1.0 / (1.0 + (spread or 0.0) * 10.0)
        liquidity = min(1.0, ((c.open_interest or 0) + (getattr(c, 'volume', 0) or 0)) / 500.0)
        out.append(VenueQuote(
            venue='ForecastEx',
            release_month=_normalize_release_month_label(str(c.release_month)),
            threshold=float(normalized_threshold),
            raw_threshold=float(raw_thr),
            normalized_threshold=float(normalized_threshold),
            threshold_units=units,
            normalization_method=method,
            methodology_note=note,
            bid=c.bid, ask=c.ask, mid=c.mid, spread=spread,
            volume=float(getattr(c, 'volume', 0) or 0.0),
            open_interest=float(c.open_interest or 0.0),
            quote_age_seconds=None,
            liquidity_score=float(liquidity),
            confidence_score=float(confidence),
            market_id=str(c.contract_id),
            question=str(c.event_question) if c.event_question else f'ForecastEx {c.release_month} > {raw_thr}%',
            source_status=status,
        ))
    return out, status



def build_front_end_points(quotes: list[VenueQuote], config: HarnessConfig) -> pd.DataFrame:
    rows = []
    for q in quotes:
        if q.confidence_score < config.min_confidence:
            continue
        rows.append({
            'release_month': q.release_month,
            'venue': q.venue,
            'market_id': q.market_id,
            'question': q.question,
            'raw_threshold': q.raw_threshold,
            'normalized_threshold': q.normalized_threshold,
            'threshold': q.threshold,
            'threshold_units': q.threshold_units,
            'normalization_method': q.normalization_method,
            'methodology_note': q.methodology_note,
            'bid': q.bid,
            'ask': q.ask,
            'mid': q.mid,
            'spread': q.spread,
            'volume': q.volume,
            'open_interest': q.open_interest,
            'quote_age_seconds': q.quote_age_seconds,
            'liquidity_score': q.liquidity_score,
            'confidence_score': q.confidence_score,
            'implied_yoy': _threshold_to_implied_yoy(q.threshold, q.mid),
            'source_status': q.source_status,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    month_order = list(
        dict.fromkeys(
            df.sort_values('release_month', key=lambda s: pd.to_datetime(s, format='%b %Y', errors='coerce'))['release_month'].tolist()
        )
    )[:config.max_front_months]
    return df[df['release_month'].isin(month_order)].copy()



def compute_oriel_reference(front_df: pd.DataFrame) -> pd.DataFrame:
    if front_df.empty:
        return pd.DataFrame(columns=['release_month', 'oriel_reference_yoy'])
    tmp = front_df.copy()
    tmp['oriel_weight'] = (0.6 * tmp['confidence_score'] + 0.4 * tmp['liquidity_score']).clip(lower=0.01)
    weighted = tmp.assign(weighted_value=tmp['implied_yoy'] * tmp['oriel_weight'])
    agg = weighted.groupby('release_month', as_index=False).agg(
        weighted_sum=('weighted_value', 'sum'),
        total_weight=('oriel_weight', 'sum'),
    )
    agg['oriel_reference_yoy'] = agg['weighted_sum'] / agg['total_weight'].replace(0, pd.NA)
    return agg[['release_month', 'oriel_reference_yoy']]



def compute_dislocations(front_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    if front_df.empty:
        return pd.DataFrame(columns=['release_month', 'venue', 'implied_yoy', 'oriel_reference_yoy', 'dislocation_bps'])
    out = front_df.merge(ref_df, on='release_month', how='left')
    out['dislocation_bps'] = (out['implied_yoy'] - out['oriel_reference_yoy']) * 100.0
    return out.sort_values(['release_month', 'venue', 'dislocation_bps'])



def compute_venue_contribution_summary(front_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    """Summarize how each venue contributes to the Oriel reference by release month.

    One row per (release_month, venue) showing the normalized implied YoY point,
    liquidity / confidence inputs, and the venue's relative weight in the Oriel
    reference construction for that month.
    """
    cols = [
        'release_month', 'venue', 'implied_yoy', 'liquidity_score',
        'confidence_score', 'oriel_weight', 'weight_pct', 'oriel_reference_yoy'
    ]
    if front_df.empty:
        return pd.DataFrame(columns=cols)

    tmp = front_df.copy()
    tmp['oriel_weight'] = (0.6 * tmp['confidence_score'] + 0.4 * tmp['liquidity_score']).clip(lower=0.01)
    tmp['month_total_weight'] = tmp.groupby('release_month')['oriel_weight'].transform('sum').replace(0, pd.NA)
    tmp['weight_pct'] = (tmp['oriel_weight'] / tmp['month_total_weight']) * 100.0

    out = tmp.groupby(['release_month', 'venue'], as_index=False).agg(
        implied_yoy=('implied_yoy', 'mean'),
        liquidity_score=('liquidity_score', 'mean'),
        confidence_score=('confidence_score', 'mean'),
        oriel_weight=('oriel_weight', 'sum'),
        weight_pct=('weight_pct', 'sum'),
    )
    out = out.merge(ref_df, on='release_month', how='left')
    return out.sort_values(['release_month', 'venue']).reset_index(drop=True)


def load_front_end_market_snapshot(config: HarnessConfig | None = None, _ttl_bust: int = 0) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    config = config or HarnessConfig()
    all_quotes: list[VenueQuote] = []
    status_parts: list[str] = []

    for venue_name, loader in [
        ('Kalshi', _ingest_kalshi_front_end),
        ('Polymarket', _ingest_polymarket_front_end),
        ('ForecastEx', _ingest_forecastex_front_end),
    ]:
        try:
            quotes, status = loader(config)
            all_quotes.extend(quotes)
            status_parts.append(f'{venue_name}:{status}')
        except Exception as exc:
            status_parts.append(f'{venue_name}:FALLBACK({type(exc).__name__})')

    sample_path = Path(config.fallback_sample_csv)
    sample_quotes = _sample_quotes(sample_path if sample_path.is_absolute() else Path.cwd() / sample_path)
    venues_present = {q.venue for q in all_quotes}
    if not all_quotes:
        all_quotes = sample_quotes
        status_parts.append('Sample:ON')
    elif len(venues_present) < 3:
        for sq in sample_quotes:
            if sq.venue not in venues_present:
                all_quotes.append(sq)
        status_parts.append('Sample:AUGMENTED')

    front_df = build_front_end_points(all_quotes, config)
    ref_df = compute_oriel_reference(front_df)
    dislocations = compute_dislocations(front_df, ref_df)
    return front_df, dislocations, ' | '.join(status_parts)
