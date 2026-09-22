"""Build the publishable dashboard.

Metrics are written twice: inlined into index.html (so the page still works
opened directly as a file, with no server) and as a standalone metrics.json
next to it (so the live page can fetch fresh data without a full rebuild of
the HTML). The guard runs over BOTH the final rendered HTML and the standalone
JSON, so anything introduced by templating is still caught either way.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nerdjoy_pipeline.guard import (  # noqa: E402
    GuardViolation,
    build_denylist,
    guard_text,
)

PLACEHOLDER = "__METRICS_JSON__"
STATIC_FILES = ("style.css", "app.js")
DEFAULT_TRACKER = os.environ.get("TRACKER_PATH", ".local/tracker/job_tracker.csv")


def build_dashboard(
    metrics_path: str | Path,
    template_dir: str | Path,
    output_dir: str | Path,
    tracker_path: str | Path,
) -> Path:
    template_dir = Path(template_dir)
    output_dir = Path(output_dir)

    raw_metrics_text = Path(metrics_path).read_text(encoding="utf-8").strip()
    # Re-serialize pretty-printed so the standalone metrics.json has a
    # predictable, readable shape regardless of the input file's formatting.
    metrics_obj = json.loads(raw_metrics_text)
    metrics_json = json.dumps(metrics_obj, indent=2, ensure_ascii=False)

    html = (template_dir / "index.html").read_text(encoding="utf-8")
    rendered = html.replace(PLACEHOLDER, metrics_json)

    # Guard every final artifact, before anything touches disk.
    denylist = build_denylist(tracker_path)
    guard_text(rendered, denylist, label="dashboard/index.html")
    guard_text(metrics_json, denylist, label="dashboard/metrics.json")
    for name in STATIC_FILES:
        guard_text(
            (template_dir / name).read_text(encoding="utf-8"),
            denylist,
            label=f"dashboard/{name}",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "index.html"
    out.write_text(rendered, encoding="utf-8")
    (output_dir / "metrics.json").write_text(metrics_json + "\n", encoding="utf-8")
    for name in STATIC_FILES:
        shutil.copy2(template_dir / name, output_dir / name)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the dashboard")
    parser.add_argument("--metrics", default="metrics.json")
    parser.add_argument("--templates", default="dashboard")
    parser.add_argument("--output", default="dashboard/dist")
    parser.add_argument("--tracker", default=DEFAULT_TRACKER)
    args = parser.parse_args(argv)

    try:
        out = build_dashboard(args.metrics, args.templates, args.output, args.tracker)
    except GuardViolation as exc:
        print(f"GUARD FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"Built {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
