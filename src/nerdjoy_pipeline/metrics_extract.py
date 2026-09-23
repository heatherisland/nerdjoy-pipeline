"""Export anonymized metrics.json from the tracker.

The guard runs against the serialized payload BEFORE anything is written,
so a violation can never leave a leaked file on disk.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from nerdjoy_pipeline.guard import GuardViolation, build_denylist, guard_text
from nerdjoy_pipeline.metrics import FUNNEL_ORDER, summary
from nerdjoy_pipeline.tracker import in_pipeline_window, read_tracker

DEFAULT_TRACKER = os.environ.get(
    "TRACKER_PATH", ".local/tracker/job_tracker.csv"
)
DEFAULT_OUTPUT = "metrics.json"


_FUNNEL_PREFIX = "funnel_"

# Keys published under "crm", mapped from their mart metric names. The
# opportunity rate is computed over known companies only, so coverage travels
# with it: publishing the rate alone would imply it describes every company.
_CRM_METRICS = {
    "crm_known_companies": ("known_companies", int),
    "crm_coverage_pct": ("coverage_pct", float),
    "crm_opportunity_pct": ("opportunity_pct", float),
}


def _status_from_metric(metric_name: str) -> str | None:
    """Map funnel_to_apply back to the canonical "To Apply"."""
    if not metric_name.startswith(_FUNNEL_PREFIX):
        return None
    slug = metric_name[len(_FUNNEL_PREFIX) :]
    for status in FUNNEL_ORDER:
        if status.lower().replace(" ", "_") == slug:
            return status
    return None


def payload_from_bigquery_rows(
    rows: list[dict],
    channel_rows: list[dict] | None = None,
    activity_rows: list[dict] | None = None,
) -> dict:
    """Rebuild the metrics.json shape from the marts.

    channel_rows comes from mart_channel_counts, a separate model because
    mart_public_metrics is a fixed name/value table and channels are a
    variable set of keys. Order is preserved from the query, which sorts by
    count descending, so the dashboard's top-8 slice is the real top eight.
    """
    values = {r["metric_name"]: r["metric_value"] for r in rows}

    funnel = {status: 0 for status in FUNNEL_ORDER}
    for name, value in values.items():
        status = _status_from_metric(name)
        if status is not None:
            funnel[status] = int(value)

    payload = {
        "totals": {
            "applications": int(values.get("applications_total", 0)),
            "companies": int(values.get("companies_total", 0)),
        },
        "funnel": funnel,
        "referrals": {
            "needed": int(values.get("referrals_needed", 0)),
            "outreach_sent": int(values.get("referrals_outreach_sent", 0)),
            "got_referral": int(values.get("referrals_got", 0)),
            "conversion_pct": float(values.get("referral_conversion_pct", 0.0)),
        },
        "channels": {
            r["channel"]: int(r["application_count"]) for r in (channel_rows or [])
        },
        "activity": [
            {"month": r["month"], "applied": int(r["applied_count"])}
            for r in (activity_rows or [])
        ],
    }

    # Omitted entirely rather than zero-filled: the tracker source has no CRM
    # data, and a block of zeroes would read as "HubSpot knows nothing" rather
    # than "this export did not consult HubSpot".
    crm = {
        key: cast(values[name])
        for name, (key, cast) in _CRM_METRICS.items()
        if name in values
    }
    if crm:
        payload["crm"] = crm

    return payload


def _fetch_bigquery_rows() -> list[dict]:
    from google.cloud import bigquery

    project = os.environ["BIGQUERY_PROJECT"]
    dataset = os.environ.get("BIGQUERY_DATASET", "nerdjoy_pipeline")
    client = bigquery.Client(project=project)
    query = f"SELECT metric_name, metric_value FROM `{project}.{dataset}.mart_public_metrics`"
    return [dict(row) for row in client.query(query).result()]


def _fetch_activity_rows() -> list[dict]:
    from google.cloud import bigquery

    project = os.environ["BIGQUERY_PROJECT"]
    dataset = os.environ.get("BIGQUERY_DATASET", "nerdjoy_pipeline")
    client = bigquery.Client(project=project)
    query = (
        f"SELECT month, applied_count "
        f"FROM `{project}.{dataset}.mart_activity_monthly` "
        f"ORDER BY month"
    )
    return [dict(row) for row in client.query(query).result()]


def _fetch_channel_rows() -> list[dict]:
    from google.cloud import bigquery

    project = os.environ["BIGQUERY_PROJECT"]
    dataset = os.environ.get("BIGQUERY_DATASET", "nerdjoy_pipeline")
    client = bigquery.Client(project=project)
    query = (
        f"SELECT channel, application_count "
        f"FROM `{project}.{dataset}.mart_channel_counts` "
        f"ORDER BY application_count DESC, channel"
    )
    return [dict(row) for row in client.query(query).result()]


def export_metrics(
    tracker_path: str | Path, output_path: str | Path, source: str = "tracker"
) -> dict:
    if source == "bigquery":
        body = payload_from_bigquery_rows(
            _fetch_bigquery_rows(),
            channel_rows=_fetch_channel_rows(),
            activity_rows=_fetch_activity_rows(),
        )
    else:
        body = summary(in_pipeline_window(read_tracker(tracker_path)))
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **body}

    serialized = json.dumps(payload, indent=2, sort_keys=False)
    denylist = build_denylist(tracker_path)
    guard_text(serialized, denylist, label="metrics.json")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(serialized + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export anonymized metrics.json")
    parser.add_argument("--tracker", default=DEFAULT_TRACKER)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--source", choices=["tracker", "bigquery"], default="tracker")
    args = parser.parse_args(argv)

    try:
        payload = export_metrics(args.tracker, args.output, source=args.source)
    except GuardViolation as exc:
        print(f"GUARD FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote {args.output}: "
        f"{payload['totals']['applications']} applications, "
        f"{payload['totals']['companies']} companies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
