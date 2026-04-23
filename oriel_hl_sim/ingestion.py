from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import os
import pandas as pd

from .common import VenueQuote, OrielFrontEndPoint, DislocationRow
from .config.markets import HarnessConfig
from venues.kalshi.live_data import build_live_cpi_feed
from venues.polymarket.client import PolymarketClient
from venues.polymarket.config import PolymarketConfig


def _sample_quotes(path: Path) -> list[VenueQuote]:
    df = pd.read_csv(path)
    out = []
    for _, r in df.iterrows():
        out.append(VenueQuote(
            venue=str(r['venue']),
            release_month=str(r['release_month']),
            threshold=float(r['threshold']),
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


def _ingest_kalshi_front_end(config: HarnessConfig) -> list[VenueQuote]:
    os.environ.setdefault("KALSHI_TIMEOUT_SECONDS", "3")
    os.environ.setdefault("KALSHI_MAX_RETRIES", "1")
    methodology, snapshots, contracts_table, runtime_meta = build_live_cpi_feed()
    df = contracts_table.copy()
    if df.empty:
        return []
    # Normalize to first few months and threshold-style rows only
    month_col = 'Maturity' if 'Maturity' in df.columns else 'maturity'
    value_col = 'Value' if 'Value' in df.columns else 'value'
    bid_col = 'Bid' if 'Bid' in df.columns else 'bid'
    ask_col = 'Ask' if 'Ask' in df.columns else 'ask'
    mid_col = 'Chosen Price' if 'Chosen Price' in df.columns else ('mid' if 'mid' in df.columns else None)
    spread_col = 'Spread' if 'Spread' in df.columns else ('spread' if 'spread' in df.columns else None)
    vol_col = 'Volume' if 'Volume' in df.columns else 'volume'
    oi_col = 'Open Interest' if 'Open Interest' in df.columns else 'open_interest'
    age_col = 'Quote Age (s)' if 'Quote Age (s)' in df.columns else ('quote_age_seconds' if 'quote_age_seconds' in df.columns else None)
    id_col = 'Ticker' if 'Ticker' in df.columns else ('contract_ticker' if 'contract_ticker' in df.columns else None)
    q_col = 'Label' if 'Label' in df.columns else 'label'

    df = df.sort_values(month_col).head(config.max_front_months * max(1, len(df) // max(len(df[month_col].unique()),1)))
    out: list[VenueQuote] = []
    for _, r in df.iterrows():
        mid = float(r[mid_col]) if mid_col and pd.notna(r[mid_col]) else None
        bid = float(r[bid_col]) if bid_col and pd.notna(r[bid_col]) else None
        ask = float(r[ask_col]) if ask_col and pd.notna(r[ask_col]) else None
        spread = float(r[spread_col]) if spread_col and pd.notna(r[spread_col]) else ((ask - bid) if ask is not None and bid is not None else None)
        oi = float(r[oi_col]) if oi_col in r and pd.notna(r[oi_col]) else 0.0
        vol = float(r[vol_col]) if vol_col in r and pd.notna(r[vol_col]) else 0.0
        confidence = 1.0 / (1.0 + (spread or 0.0) * 10.0)
        liquidity = min(1.0, (oi + vol) / 500.0)
        out.append(VenueQuote(
            venue='Kalshi',
            release_month=str(r[month_col]),
            threshold=float(r[value_col]) if value_col in r and pd.notna(r[value_col]) else 0.0,
            bid=bid, ask=ask, mid=mid, spread=spread,
            volume=vol, open_interest=oi,
            quote_age_seconds=int(r[age_col]) if age_col and pd.notna(r[age_col]) else None,
            liquidity_score=liquidity,
            confidence_score=confidence,
            market_id=str(r[id_col]) if id_col and pd.notna(r[id_col]) else f"kalshi-{r.name}",
            question=str(r[q_col]) if q_col in r else f"Kalshi {r[month_col]} {value_col}",
            source_status=runtime_meta.get('feed_status', 'LIVE') if isinstance(runtime_meta, dict) else 'LIVE',
        ))
    return out


def _ingest_polymarket_front_end(config: HarnessConfig) -> list[VenueQuote]:
    os.environ.setdefault("POLYMARKET_REQUEST_TIMEOUT_SECONDS", "3")
    client = PolymarketClient(PolymarketConfig(request_timeout_seconds=int(os.getenv("POLYMARKET_REQUEST_TIMEOUT_SECONDS", "3"))))
    contracts, status = client.fetch_contracts()
    out: list[VenueQuote] = []
    for c in contracts:
        out.append(VenueQuote(
            venue='Polymarket',
            release_month=str(c.release_month),
            threshold=float(c.threshold),
            bid=c.bid, ask=c.ask, mid=c.mid, spread=c.spread,
            volume=c.volume, open_interest=c.open_interest,
            quote_age_seconds=c.quote_age_seconds,
            liquidity_score=float(c.liquidity_score or 0.0),
            confidence_score=float(c.confidence_score or 0.0),
            market_id=str(c.market_id),
            question=str(c.question),
            source_status=status,
        ))
    return out


def _threshold_to_implied_yoy(threshold: float, probability: float | None) -> float:
    # Lightweight bridge for the FalconX harness: convert threshold probabilities
    # into an implied front-end point anchored around the threshold.
    p = 0.5 if probability is None else max(0.01, min(0.99, probability))
    return threshold + (p - 0.5) * 0.8


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
            'threshold': q.threshold,
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
    # Keep first N months across both venues
    ordered_months = list(dict.fromkeys(df['release_month'].tolist()))[:config.max_front_months]
    return df[df['release_month'].isin(ordered_months)].copy()


def compute_oriel_reference(front_df: pd.DataFrame) -> pd.DataFrame:
    if front_df.empty:
        return pd.DataFrame(columns=['release_month', 'oriel_reference_yoy'])
    tmp = front_df.copy()
    tmp['oriel_weight'] = (0.6 * tmp['confidence_score'] + 0.4 * tmp['liquidity_score']).clip(lower=0.01)
    agg = tmp.groupby('release_month', as_index=False).agg(
        weighted_sum=('implied_yoy', lambda s: float((s * tmp.loc[s.index, 'oriel_weight']).sum())),
        total_weight=('oriel_weight', 'sum'),
    )
    agg['oriel_reference_yoy'] = agg['weighted_sum'] / agg['total_weight'].replace(0, pd.NA)
    return agg[['release_month', 'oriel_reference_yoy']]


def compute_dislocations(front_df: pd.DataFrame, ref_df: pd.DataFrame) -> pd.DataFrame:
    if front_df.empty:
        return pd.DataFrame(columns=['release_month','venue','implied_yoy','oriel_reference_yoy','dislocation_bps'])
    out = front_df.merge(ref_df, on='release_month', how='left')
    out['dislocation_bps'] = (out['implied_yoy'] - out['oriel_reference_yoy']) * 100.0
    return out.sort_values(['release_month', 'venue', 'dislocation_bps'])


def load_front_end_market_snapshot(config: HarnessConfig | None = None) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    config = config or HarnessConfig()
    all_quotes: list[VenueQuote] = []
    status_parts = []
    try:
        kquotes = _ingest_kalshi_front_end(config)
        all_quotes.extend(kquotes)
        status_parts.append('Kalshi:LIVE')
    except Exception as exc:
        status_parts.append(f'Kalshi:FALLBACK({type(exc).__name__})')
    try:
        pquotes = _ingest_polymarket_front_end(config)
        all_quotes.extend(pquotes)
        status_parts.append('Polymarket:LIVE')
    except Exception as exc:
        status_parts.append(f'Polymarket:FALLBACK({type(exc).__name__})')
    sample_path = Path(config.fallback_sample_csv)
    sample_quotes = _sample_quotes(sample_path if sample_path.is_absolute() else Path.cwd()/sample_path)
    venues_present = {q.venue for q in all_quotes}
    if not all_quotes:
        all_quotes = sample_quotes
        status_parts.append('Sample:ON')
    elif len(venues_present) < 2:
        for sq in sample_quotes:
            if sq.venue not in venues_present:
                all_quotes.append(sq)
        status_parts.append('Sample:AUGMENTED')
    front_df = build_front_end_points(all_quotes, config)
    ref_df = compute_oriel_reference(front_df)
    dislocations = compute_dislocations(front_df, ref_df)
    return front_df, dislocations, ' | '.join(status_parts)
