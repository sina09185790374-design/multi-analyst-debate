# multi-analyst-debate

Three analysts argue about one price series, a judge decides. One Python file, stdlib only, no network, no API keys.

Pattern (patterns only, original code): multi-agent debate before a decision — the idea behind today's multi-agent trading frameworks — shrunk to auditable rules: a **momentum** analyst (trend), a **mean-reversion** analyst (RSI extremes, never fading a strong trend), and a **risk** manager with veto power (high volatility or deep drawdown → FLAT, no matter what the others say). The judge only aggregates weighted scores; it never invents data.

This is a research/learning tool, not trading advice and not a live-trading bot. No real money, no leverage, no exchange connection.

## Why it exists

A single indicator always lies sometimes. A trend-follower buys every top, a mean-reversion trader fades every freight train, and neither asks whether the series is too wild to trade at all. Putting the three in one room — with the risk manager able to overrule both — produces verdicts a human can read, disagree with, and audit line by line.

## Usage

```bash
python3 debate.py --csv example-prices.csv
python3 debate.py --csv example-prices.csv --json
```

CSV format: one close per line, optionally preceded by a date column (`2026-10-01,123.4` or just `123.4`). A header row is skipped.

Example output:

```
VERDICT: LONG (confidence 80%)
Last 216.47 | SMA20 180.52 | SMA50 151.0 | RSI14 100.0 | 10d 21.9% | vol 0.0%/day | DD 0.0%
Suggested risk: 2.0% of account
- momentum [LONG 1.0]: uptrend: last 216.47 > SMA20 180.52 > SMA50 151.00, 10d momentum +21.9%
- mean-reversion [— 0.0]: abstains: 10d momentum 21.9% too strong to fade
- risk [— 0.0]: volatility 0.00%/day, max drawdown 0.0%, suggested risk 2.0%
```

## Rules (all of them)

- Momentum: LONG when last > SMA20 > SMA50 and 10-day momentum > +2%; SHORT on the mirror; otherwise abstains.
- Mean-reversion: LONG when RSI14 < 30, SHORT when RSI14 > 70 — but abstains when |10-day momentum| ≥ 5%, because fading a strong trend is how accounts die.
- Risk: veto when daily volatility > 5% (wildness, not direction — a smooth downtrend's deep drawdown must not veto a clean SHORT); suggested risk scales 2% → 1.5% → 1% as volatility rises, and a drawdown > 25% cuts size to 1%.
- Judge: momentum 0.6, mean-reversion 0.4; |weighted score| ≥ 0.15 decides, otherwise FLAT; analyst disagreement cuts confidence by 30%.

Exit codes: 0 verdict produced, 2 bad input.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

9 tests: uptrend → LONG, downtrend → SHORT, flat → FLAT, wild series → risk veto → FLAT, mean-reversion votes/abstains, bad input rejected, CLI JSON round-trip, missing file exits 2.

---

# بحث چندتحلیلگر

سه تحلیلگر درباره یک سری قیمت بحث می‌کنند و یک داور تصمیم می‌گیرد. یک فایل پایتون، فقط کتابخانه استاندارد، بدون شبکه و بدون کلید API.

الگو (فقط الگو، کد اوریجینال): بحث چندعامله قبل از تصمیم — ایده پشت فریم‌ورک‌های معاملاتی چندعامله امروزی — در قالب قواعدی که هر انسانی می‌تواند بازبینی کند: تحلیلگر **مومنتوم** (روند)، تحلیلگر **میانگین‌بازگشتی** (کف و سقف RSI، بدون مقابله با روند قوی)، و مدیر **ریسک** با حق وتو (نوسان بالا یا افت عمیق یعنی FLAT، هرچه بقیه بگویند). داور فقط امتیازها را جمع می‌کند و داده نمی‌سازد.

این ابزار پژوهش و یادگیری است، نه توصیه معاملاتی و نه ربات معامله زنده. بدون پول واقعی، بدون اهرم، بدون اتصال به صرافی.

## چرا ساخته شد

یک اندیکاتور همیشه گاهی دروغ می‌گوید. رونددنبال‌کننده هر سقفی را می‌خرد، میانگین‌بازگشتی با هر قطار سریعی مقابله می‌کند، و هیچ‌کدام نمی‌پرسند آیا این سری آن‌قدر وحشی هست که اصلاً معامله‌اش نکنیم. وقتی هر سه در یک اتاق باشند — و مدیر ریسک بتواند هر دو را وتو کند — حکمی بیرون می‌آید که انسان می‌تواند بخواند، با آن مخالفت کند و خط‌به‌خط بازبینی‌اش کند.

## استفاده

```bash
python3 debate.py --csv example-prices.csv
python3 debate.py --csv example-prices.csv --json
```

فرمت CSV: هر خط یک قیمت پایانی، با یا بدون ستون تاریخ. سطر سرستون نادیده گرفته می‌شود.

## تست‌ها

```bash
python3 -m unittest discover -s tests -v
```
