"""Run folder, CRM export ingest, column mapping, stage configuration."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from .util import (from_iso, iso, norm_key, parse_amount, parse_date, parse_probability, read_json, read_jsonl,
                   write_json, write_jsonl, median)

# Canonical field -> header names seen in Salesforce and HubSpot exports (matched case- and punctuation-insensitively).
FIELD_SYNONYMS = {
    "id": ["opportunity id", "opportunity id 18", "record id", "deal id", "id", "opp id"],
    "name": ["opportunity name", "deal name", "name"],
    "account": ["account name", "company", "company name", "associated company", "account"],
    "created": ["created date", "create date", "created", "date created", "createddate"],
    "close": ["close date", "closed date", "close", "expected close date", "closedate"],
    "stage": ["stage", "deal stage", "stage name", "stagename"],
    "amount": ["amount", "amount converted", "deal amount", "amount in company currency", "total contract value", "acv"],
    "source": ["lead source", "original source", "source", "opportunity source", "original traffic source",
               "pipeline source", "leadsource"],
    "owner": ["opportunity owner", "deal owner", "owner", "owner name"],
    "forecast_category": ["forecast category", "forecast category name", "forecastcategory", "forecast_category"],
    "probability": ["probability", "probability %", "deal probability", "deal stage probability"],
    "last_activity": ["last activity", "last activity date", "last activity date hubspot", "last_activity"],
    "type": ["type", "deal type", "opportunity type", "opportunity record type"],
}
REQUIRED = ("id", "created", "close", "stage", "amount", "source")

# Values that mean "no source recorded".
UNTAGGED = {"", "other", "unknown", "none", "n a", "na", "null", "not set", "unattributed", "offline", "-"}

# Field-history export (Salesforce "Opportunity Field History" or equivalent).
HISTORY_SYNONYMS = {
    "id": ["opportunity id", "opportunity id 18", "record id", "deal id", "id"],
    "field": ["field event", "field", "field name", "property"],
    "old": ["old value", "old", "previous value"],
    "new": ["new value", "new", "value"],
    "changed": ["edit date", "date", "changed", "changed at", "timestamp", "modified date"],
}


class Run:
    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def settings(self) -> dict:
        s = read_json(self.root / "run.json")
        if s is None:
            raise SystemExit(f"error: {self.root} is not a run folder (no run.json). Run `init` first.")
        return s

    def save_settings(self, s: dict) -> None:
        write_json(self.root / "run.json", s)

    @property
    def as_of(self) -> date:
        return from_iso(self.settings["as_of"])

    def opps(self) -> list[dict]:
        rows = read_jsonl(self.root / "opps.jsonl")
        if not rows:
            raise SystemExit(f"error: no opportunities in {self.root}. Run `ingest` first.")
        return [_load_opp(r) for r in rows]

    def history(self) -> list[dict]:
        return [dict(r, changed=from_iso(r["changed"])) for r in read_jsonl(self.root / "history.jsonl")]


def _load_opp(r: dict) -> dict:
    o = dict(r)
    for k in ("created", "close", "last_activity"):
        o[k] = from_iso(o.get(k))
    return o


def _dump_opp(o: dict) -> dict:
    d = dict(o)
    for k in ("created", "close", "last_activity"):
        d[k] = iso(d.get(k))
    return d


def detect_mapping(headers: list[str], synonyms: dict = FIELD_SYNONYMS) -> dict:
    """Returns {canonical field: header} for headers that match a known synonym."""
    by_norm = {norm_key(h): h for h in headers}
    mapping = {}
    for field, names in synonyms.items():
        for n in names:
            if norm_key(n) in by_norm:
                mapping[field] = by_norm[norm_key(n)]
                break
    return mapping


def normalize_source(raw) -> str | None:
    if raw is None:
        return None
    k = norm_key(raw)
    return None if k in UNTAGGED else k


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    text = Path(path).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    return list(reader.fieldnames or []), list(reader)


def ingest(run: Run, csv_path: Path, mapping_override: dict | None = None, day_first: bool = False,
           types: list[str] | None = None) -> dict:
    headers, rows = read_csv(csv_path)
    mapping = detect_mapping(headers)
    mapping.update(mapping_override or {})
    missing = [f for f in ("id", "created", "close", "stage") if f not in mapping]
    if missing:
        raise SystemExit(
            f"error: could not find columns for {', '.join(missing)}. Headers seen: {', '.join(headers)}. "
            "Pass a mapping file: {\"created\": \"Your Created Column\", ...}")

    def get(row, field):
        h = mapping.get(field)
        return row.get(h) if h else None

    opps, skipped, seen = [], Counter(), set()
    type_values = Counter()
    for row in rows:
        oid = (get(row, "id") or "").strip()
        if not oid:
            skipped["no id"] += 1
            continue
        if oid in seen:
            skipped["repeated id in file"] += 1
            continue
        created = parse_date(get(row, "created"), day_first)
        if created is None:
            skipped["created date missing or unreadable"] += 1
            continue
        typ = (get(row, "type") or "").strip() or None
        if typ:
            type_values[typ] += 1
        if types and typ not in types:
            skipped["type filtered out"] += 1
            continue
        seen.add(oid)
        src_raw = (get(row, "source") or "").strip() or None
        opps.append({
            "id": oid,
            "name": (get(row, "name") or "").strip() or None,
            "account": (get(row, "account") or "").strip() or None,
            "created": created,
            "close": parse_date(get(row, "close"), day_first),
            "stage": (get(row, "stage") or "").strip() or None,
            "amount": parse_amount(get(row, "amount")),
            "source_raw": src_raw,
            "source": normalize_source(src_raw),
            "owner": (get(row, "owner") or "").strip() or None,
            "forecast_category": (get(row, "forecast_category") or "").strip() or None,
            "probability": parse_probability(get(row, "probability")),
            "last_activity": parse_date(get(row, "last_activity"), day_first),
            "type": typ,
        })
    write_jsonl(run.root / "opps.jsonl", [_dump_opp(o) for o in opps])

    s = run.settings
    s["mapping"] = mapping
    s["source_file"] = Path(csv_path).name
    s["type_values"] = dict(type_values)
    s["type_filter"] = types
    if not s.get("stages"):
        s["stages"] = infer_stages(opps)
    s["source_labels"] = source_labels(opps)
    run.save_settings(s)
    return {"rows": len(rows), "kept": len(opps), "skipped": dict(skipped), "mapping": mapping,
            "unmapped_optional": [f for f in FIELD_SYNONYMS if f not in mapping and f not in REQUIRED],
            "unmapped_required": [f for f in REQUIRED if f not in mapping]}


def ingest_history(run: Run, csv_path: Path, mapping_override: dict | None = None, day_first: bool = False) -> dict:
    headers, rows = read_csv(csv_path)
    mapping = detect_mapping(headers, HISTORY_SYNONYMS)
    mapping.update(mapping_override or {})
    missing = [f for f in ("id", "field", "new", "changed") if f not in mapping]
    if missing:
        raise SystemExit(f"error: history file is missing columns for {', '.join(missing)}. Headers seen: {', '.join(headers)}")
    out, skipped = [], Counter()
    for row in rows:
        field = norm_key(row.get(mapping["field"]) or "")
        kind = "stage" if "stage" in field else "close" if "close" in field else None
        if not kind:
            continue
        changed = parse_date(row.get(mapping["changed"]), day_first)
        if not changed:
            skipped["unreadable date"] += 1
            continue
        new = (row.get(mapping["new"]) or "").strip()
        old = (row.get(mapping["old"]) or "").strip() if "old" in mapping else ""
        rec = {"id": row[mapping["id"]].strip(), "field": kind, "changed": iso(changed), "new": new, "old": old}
        if kind == "close":
            rec["new"] = iso(parse_date(new, day_first))
            rec["old"] = iso(parse_date(old, day_first))
        out.append(rec)
    out.sort(key=lambda r: (r["id"], r["changed"]))
    write_jsonl(run.root / "history.jsonl", out)
    s = run.settings
    s["history_file"] = Path(csv_path).name
    s["stages"] = infer_stages(run.opps(), run.history(), keep=s.get("stages"))
    run.save_settings(s)
    return {"rows": len(rows), "kept": len(out), "skipped": dict(skipped),
            "stage_changes": sum(1 for r in out if r["field"] == "stage"),
            "close_date_changes": sum(1 for r in out if r["field"] == "close")}


def infer_stages(opps: list[dict], history: list[dict] | None = None, keep: dict | None = None) -> dict:
    """Guesses won, lost and the order of open stages. The user confirms with `pf stages`."""
    if keep and keep.get("confirmed"):
        return keep
    names = Counter(o["stage"] for o in opps if o.get("stage"))
    for h in history or []:
        if h["field"] == "stage" and h["new"]:
            names[h["new"]] += 0
    won = sorted(n for n in names if "won" in norm_key(n).split() or norm_key(n) in ("closed won", "won"))
    lost = sorted(n for n in names if n not in won and any(w in norm_key(n).split() for w in ("lost", "dead", "disqualified")))
    open_stages = [n for n in names if n not in won and n not in lost]

    method = "alphabetical"
    rank: dict[str, float] = {}
    probs = defaultdict(list)
    for o in opps:
        if o.get("stage") in open_stages and o.get("probability") is not None:
            probs[o["stage"]].append(o["probability"])
    if history:
        pos = defaultdict(list)
        seq = defaultdict(list)
        for h in history:
            if h["field"] == "stage" and h["new"] in open_stages:
                seq[h["id"]].append(h["new"])
        for stages in seq.values():
            for i, st in enumerate(dict.fromkeys(stages)):
                pos[st].append(i)
        if len(pos) >= max(2, len(open_stages) - 1):
            rank = {st: median(v) for st, v in pos.items()}
            method = "stage history"
    if not rank and len(probs) >= 2:
        rank = {st: median(v) for st, v in probs.items()}
        method = "CRM probability"
    order = sorted(open_stages, key=lambda st: (rank.get(st, float("inf")), st))
    return {"order": order, "won": won, "lost": lost, "method": method, "confirmed": False}


def source_labels(opps: list[dict]) -> dict:
    """Display label per normalized source: its most common spelling."""
    raw = defaultdict(Counter)
    for o in opps:
        if o.get("source"):
            raw[o["source"]][o["source_raw"]] += 1
    return {k: c.most_common(1)[0][0] for k, c in raw.items()}


def status(o: dict, stages: dict) -> str:
    st = o.get("stage")
    if st in stages["won"]:
        return "won"
    if st in stages["lost"]:
        return "lost"
    return "open"


def stage_index(stage: str | None, stages: dict) -> int | None:
    try:
        return stages["order"].index(stage)
    except (ValueError, KeyError):
        return None
