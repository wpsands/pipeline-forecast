"""Shared helpers: dates, numbers, JSON files, quantiles."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path


def read_json(path: Path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def write_json(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    Path(path).write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))


_DATE_FORMATS_US = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%d-%b-%Y", "%b %d, %Y", "%d %b %Y")
_DATE_FORMATS_DAY_FIRST = ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y/%m/%d", "%d-%b-%Y", "%b %d, %Y", "%d %b %Y")


def parse_date(value, day_first: bool = False) -> date | None:
    """Parses common CRM export date formats. Returns None for blanks or unparseable values."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Drop a time part: "2026-03-04 13:22", "2026-03-04T13:22:00Z", "3/4/2026 1:22 PM"
    s = re.split(r"[T ](?=\d{1,2}:)", s)[0].strip()
    for fmt in (_DATE_FORMATS_DAY_FIRST if day_first else _DATE_FORMATS_US):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def from_iso(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def parse_amount(value) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d.\-]", "", s)
    if s in ("", "-", ".", "-."):
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    return -x if neg else x


def parse_probability(value) -> float | None:
    x = parse_amount(value)
    if x is None:
        return None
    if x > 1:
        x = x / 100
    return max(0.0, min(1.0, x))


def quantile(values, q: float) -> float | None:
    xs = sorted(values)
    if not xs:
        return None
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def median(values) -> float | None:
    return quantile(values, 0.5)


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, last))


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def quarter_start(d: date, fy_start_month: int = 1) -> date:
    """First day of the fiscal quarter containing d."""
    offset = (d.month - fy_start_month) % 3
    return add_months(date(d.year, d.month, 1), -offset)


def quarter_label(start: date, fy_start_month: int = 1) -> str:
    months_into_fy = (start.month - fy_start_month) % 12
    q = months_into_fy // 3 + 1
    fy = start.year + (1 if fy_start_month != 1 and start.month >= fy_start_month else 0)
    return f"FY{fy} Q{q}" if fy_start_month != 1 else f"{start.year} Q{q}"


def days(a: date, b: date) -> int:
    return (b - a).days


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def fmt_money(x: float | None) -> str:
    if x is None:
        return "n/a"
    a = abs(x)
    if a >= 1_000_000:
        s = f"${a / 1_000_000:.1f}M"
    elif a >= 10_000:
        s = f"${a / 1000:.0f}K"
    elif a >= 1000:
        s = f"${a / 1000:.1f}K"
    else:
        s = f"${a:,.0f}"
    return ("-" if x < 0 else "") + s


def fmt_pct(r: float | None, digits: int = 0) -> str:
    if r is None:
        return "n/a"
    return f"{r * 100:.{digits}f}%"


__all__ = [n for n in dir() if not n.startswith("_")] + ["timedelta"]
