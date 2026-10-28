"""Tests for debate.py: real verdicts on synthetic series, no mocks of the core."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import debate

PY = sys.executable
SCRIPT = str(Path(__file__).resolve().parent.parent / "debate.py")


def uptrend(n=40):
    price, out = 100.0, []
    for _ in range(n):
        out.append(price)
        price *= 1.02
    return out


def downtrend(n=40):
    price, out = 100.0, []
    for _ in range(n):
        out.append(price)
        price *= 0.98
    return out


def run_cli(closes):
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("date,close\n")
        for i, c in enumerate(closes):
            f.write(f"2026-10-{i % 28 + 1:02d},{c:.4f}\n")
        path = f.name
    proc = subprocess.run([PY, SCRIPT, "--csv", path, "--json"],
                          capture_output=True, text=True, timeout=30)
    return proc


class TestVerdicts(unittest.TestCase):
    def test_uptrend_is_long(self):
        r = debate.debate(uptrend())
        self.assertEqual(r["verdict"], "LONG")
        self.assertGreaterEqual(r["confidence"], 50)

    def test_downtrend_is_short(self):
        r = debate.debate(downtrend())
        self.assertEqual(r["verdict"], "SHORT")

    def test_flat_is_flat(self):
        flat = [100.0 + (0.1 if i % 2 else -0.1) for i in range(40)]
        self.assertEqual(debate.debate(flat)["verdict"], "FLAT")

    def test_wild_series_gets_risk_veto(self):
        wild, price = [], 100.0
        for i in range(40):
            wild.append(price)
            price *= 1.08 if i % 2 == 0 else 0.92
        r = debate.debate(wild)
        self.assertTrue(r["veto"])
        self.assertEqual(r["verdict"], "FLAT")

    def test_mean_reversion_votes_on_weak_trend(self):
        ind = debate.Indicators(last=70, sma20=72, sma50=75, rsi14=22,
                                momentum10=-1.0, volatility=1.0,
                                max_drawdown=10.0)
        op = debate.mean_reversion_analyst(ind)
        self.assertEqual(op.stance, 1)

    def test_mean_reversion_abstains_in_strong_trend(self):
        ind = debate.Indicators(last=200, sma20=180, sma50=150, rsi14=100,
                                momentum10=22.0, volatility=1.0,
                                max_drawdown=0.0)
        self.assertEqual(debate.mean_reversion_analyst(ind).stance, 0)

    def test_bad_input_rejected(self):
        with self.assertRaises(ValueError):
            debate.debate([100.0, 101.0])
        with self.assertRaises(ValueError):
            debate.debate([100.0, -5.0, 101.0, 102.0, 103.0])

    def test_cli_json_round_trip(self):
        proc = run_cli(uptrend())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["verdict"], "LONG")
        self.assertIn("opinions", result)

    def test_cli_bad_file_exits_2(self):
        proc = subprocess.run([PY, SCRIPT, "--csv", "/nonexistent/x.csv"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
