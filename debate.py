#!/usr/bin/env python3
"""multi-analyst-debate: three analysts argue about one price series, a judge decides.

Original code, stdlib only, no network, no API keys, no real-money advice.
Pattern (patterns only): multi-agent debate before a decision — the idea behind
today's multi-agent trading frameworks — shrunk to one file with rules any
human can audit: a momentum analyst, a mean-reversion analyst, and a risk
manager with veto power. The judge only aggregates; it never invents data.

Usage:
    python3 debate.py --csv prices.csv            # human-readable verdict
    python3 debate.py --csv prices.csv --json     # machine-readable verdict

CSV format: one close per line, optionally preceded by a date column
("2026-10-01,123.4" or just "123.4"). A header row is skipped.

Exit codes: 0 verdict produced, 2 bad input.
"""

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass


@dataclass
class Indicators:
    last: float
    sma20: float
    sma50: float
    rsi14: float
    momentum10: float  # % change over last 10 closes
    volatility: float  # std dev of daily % returns
    max_drawdown: float  # % peak-to-trough decline


def _sma(closes, n):
    window = closes[-n:]
    return sum(window) / len(window)


def _rsi(closes, period=14):
    changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = changes[-period:]
    gains = [c for c in recent if c > 0]
    losses = [-c for c in recent if c < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _volatility(closes):
    rets = [(closes[i] / closes[i - 1] - 1.0) * 100.0
            for i in range(1, len(closes))]
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))


def _max_drawdown(closes):
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        worst = min(worst, (price / peak - 1.0) * 100.0)
    return abs(worst)


def compute_indicators(closes):
    return Indicators(
        last=closes[-1],
        sma20=_sma(closes, 20),
        sma50=_sma(closes, 50),
        rsi14=_rsi(closes) if len(closes) >= 15 else 50.0,
        momentum10=((closes[-1] / closes[-11] - 1.0) * 100.0
                    if len(closes) >= 11 else 0.0),
        volatility=_volatility(closes),
        max_drawdown=_max_drawdown(closes),
    )


@dataclass
class Opinion:
    analyst: str
    stance: int  # +1 long, -1 short, 0 abstain
    score: float  # 0..1 conviction
    reason: str


def momentum_analyst(ind):
    up = ind.last > ind.sma20 > ind.sma50
    down = ind.last < ind.sma20 < ind.sma50
    strength = min(abs(ind.momentum10) / 10.0, 1.0)
    if up and ind.momentum10 > 2:
        return Opinion("momentum", 1, strength,
                       f"uptrend: last {ind.last:.2f} > SMA20 {ind.sma20:.2f} "
                       f"> SMA50 {ind.sma50:.2f}, 10d momentum +{ind.momentum10:.1f}%")
    if down and ind.momentum10 < -2:
        return Opinion("momentum", -1, strength,
                       f"downtrend: last {ind.last:.2f} < SMA20 {ind.sma20:.2f} "
                       f"< SMA50 {ind.sma50:.2f}, 10d momentum {ind.momentum10:.1f}%")
    return Opinion("momentum", 0, 0.0,
                   f"no trend: momentum {ind.momentum10:.1f}%, price vs SMA20 "
                   f"{ind.last - ind.sma20:+.2f}")


def mean_reversion_analyst(ind):
    # Never fade a strong trend: fading is for ranges, not freight trains.
    if abs(ind.momentum10) >= 5:
        return Opinion("mean-reversion", 0, 0.0,
                       f"abstains: 10d momentum {ind.momentum10:.1f}% too "
                       f"strong to fade")
    if ind.rsi14 < 30:
        return Opinion("mean-reversion", 1, (30 - ind.rsi14) / 30.0,
                       f"oversold: RSI14 {ind.rsi14:.1f} < 30, bounce candidate")
    if ind.rsi14 > 70:
        return Opinion("mean-reversion", -1, (ind.rsi14 - 70) / 30.0,
                       f"overbought: RSI14 {ind.rsi14:.1f} > 70, fade candidate")
    return Opinion("mean-reversion", 0, 0.0,
                   f"RSI14 {ind.rsi14:.1f} neutral, no reversion edge")


def risk_analyst(ind):
    # Veto only on wildness (volatility). A deep drawdown alone does not veto:
    # a smooth, steady downtrend has a huge drawdown yet is perfectly
    # tradeable as a SHORT — vetoing it was a bug caught by the test suite.
    # Drawdown instead shrinks the suggested size.
    veto = ind.volatility > 5.0
    if ind.volatility > 4.0:
        size = 1.0
    elif ind.volatility > 2.0:
        size = 1.5
    elif ind.max_drawdown > 25.0:
        size = 1.0
    else:
        size = 2.0
    reason = (f"volatility {ind.volatility:.2f}%/day, max drawdown "
              f"{ind.max_drawdown:.1f}%, suggested risk {size}%"
              + (" — VETO: too wild to trade" if veto else "")
              + (" — deep drawdown, size cut" if not veto and size < 2.0
                 and ind.max_drawdown > 25.0 else ""))
    return Opinion("risk", 0, 0.0, reason), veto, size


def judge(opinions, veto):
    weights = {"momentum": 0.6, "mean-reversion": 0.4}
    total = sum(weights[o.analyst] * o.stance * o.score for o in opinions)
    if veto:
        verdict, confidence = "FLAT", 60
    elif total >= 0.15:
        verdict, confidence = "LONG", 50 + 50 * min(total, 1.0)
    elif total <= -0.15:
        verdict, confidence = "SHORT", 50 + 50 * min(abs(total), 1.0)
    else:
        verdict, confidence = "FLAT", 50
    signs = {o.stance for o in opinions if o.stance != 0}
    if len(signs) > 1:  # analysts disagree: trust the verdict less
        confidence = round(confidence * 0.7)
    return verdict, int(round(confidence))


def debate(closes):
    if len(closes) < 5:
        raise ValueError("need at least 5 closes")
    if any(c <= 0 for c in closes):
        raise ValueError("closes must be positive")
    ind = compute_indicators(closes)
    mom = momentum_analyst(ind)
    rev = mean_reversion_analyst(ind)
    risk_op, veto, size = risk_analyst(ind)
    verdict, confidence = judge([mom, rev], veto)
    return {
        "verdict": verdict,
        "confidence": confidence,
        "veto": veto,
        "suggested_risk_pct": size,
        "indicators": {
            "last": round(ind.last, 2),
            "sma20": round(ind.sma20, 2),
            "sma50": round(ind.sma50, 2),
            "rsi14": round(ind.rsi14, 1),
            "momentum10_pct": round(ind.momentum10, 2),
            "volatility_pct": round(ind.volatility, 2),
            "max_drawdown_pct": round(ind.max_drawdown, 1),
        },
        "opinions": [
            {"analyst": o.analyst, "stance": o.stance,
             "score": round(o.score, 2), "reason": o.reason}
            for o in (mom, rev, risk_op)
        ],
    }


def read_closes(path):
    closes = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if not row:
                continue
            cell = row[-1].strip()
            try:
                closes.append(float(cell))
            except ValueError:
                continue  # header or date-only row
    return closes


def main(argv=None):
    parser = argparse.ArgumentParser(description="Multi-analyst debate on a price series")
    parser.add_argument("--csv", required=True, help="CSV file of closes")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        closes = read_closes(args.csv)
        result = debate(closes)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        ind = result["indicators"]
        print(f"VERDICT: {result['verdict']} (confidence {result['confidence']}%)")
        if result["veto"]:
            print("RISK VETO active — no trade regardless of the other analysts.")
        print(f"Last {ind['last']} | SMA20 {ind['sma20']} | SMA50 {ind['sma50']} | "
              f"RSI14 {ind['rsi14']} | 10d {ind['momentum10_pct']}% | "
              f"vol {ind['volatility_pct']}%/day | DD {ind['max_drawdown_pct']}%")
        print(f"Suggested risk: {result['suggested_risk_pct']}% of account")
        for op in result["opinions"]:
            arrow = {1: "LONG", -1: "SHORT", 0: "—"}[op["stance"]]
            print(f"- {op['analyst']} [{arrow} {op['score']}]: {op['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
