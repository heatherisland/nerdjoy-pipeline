"""End-to-end refresh: tracker export -> Postgres -> BigQuery -> dbt -> publish.

Local twin of dags/gtm_pipeline_dag.py. It runs on this machine because the
tracker lives only here. Any failing step, including either privacy gate,
stops the run before anything is published. Logs carry counts only.

Usage: .venv/bin/python scripts/refresh.py [--force] [--no-deploy]
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from nerdjoy_pipeline.pg_loader import (  # noqa: E402
    CREATE_TABLE_SQL,
    UPSERT_SQL,
    application_key,
    to_row,
)
from nerdjoy_pipeline.tracker import in_pipeline_window, read_tracker  # noqa: E402

LOCAL = REPO / ".local"
TRACKER = Path(os.environ.get("TRACKER_PATH", LOCAL / "tracker" / "job_tracker.csv"))
STATE = LOCAL / "refresh_state.json"
LOG = LOCAL / "refresh.log"
PY = str(REPO / ".venv" / "bin" / "python")
DBT = str(REPO / ".venv" / "bin" / "dbt")
DIST_FILES = ("index.html", "metrics.json", "app.js", "style.css")

# A dedupe that renames a few keys is normal; a large drop is more likely a bad
# export, so stop and let a human look rather than delete production rows.
MAX_STALE_DELETES = 25
KEEP_SERVER_BACKUPS = 5


class Abort(Exception):
    pass


def log(msg: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def notify(title: str, msg: str) -> None:
    subprocess.run(
        ["osascript", "-e", f'display notification "{msg}" with title "{title}"'],
        check=False,
    )


def load_env() -> None:
    for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())


def run(cmd: list[str], cwd: Path = REPO, label: str = "") -> str:
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if out.returncode != 0:
        # Tool output can quote tracker content, so only the tail goes to the log.
        tail = (out.stdout + out.stderr).strip().splitlines()[-3:]
        raise Abort(f"{label or cmd[0]} failed: {' | '.join(tail)[:300]}")
    return out.stdout


def http(method: str, url: str, headers: dict, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read() or b"{}")


# --- steps -------------------------------------------------------------------


def load_postgres() -> int:
    import psycopg

    apps = in_pipeline_window(read_tracker(TRACKER))
    keep = {application_key(a) for a in apps}
    dsn = os.environ.get("DATABASE_URL") or os.environ["PG_CONNECTION_STRING"]
    with psycopg.connect(dsn) as conn:
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        existing = {r[0] for r in cur.execute("select application_key from applications")}
        stale = sorted(existing - keep)
        if len(stale) > MAX_STALE_DELETES:
            raise Abort(
                f"{len(stale)} Postgres rows would be deleted (limit {MAX_STALE_DELETES}); "
                "check the export, then rerun with a higher limit if intended"
            )
        cur.executemany(UPSERT_SQL, [to_row(a) for a in apps])
        if stale:
            cur.execute("delete from applications where application_key = any(%s)", (stale,))
        conn.commit()
        total = cur.execute("select count(*) from applications").fetchone()[0]
    if total != len(keep):
        raise Abort(f"Postgres has {total} rows, expected {len(keep)}")
    log(f"postgres: {total} rows, {len(keep - existing)} new, {len(stale)} deleted")
    return total


def fivetran_sync(expected: int) -> None:
    cid = os.environ["FIVETRAN_CONNECTOR_ID_POSTGRES"]
    token = b64encode(
        f"{os.environ['FIVETRAN_API_KEY']}:{os.environ['FIVETRAN_API_SECRET']}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
    base = f"https://api.fivetran.com/v1/connections/{cid}"
    started = datetime.now(timezone.utc)
    http("POST", f"{base}/sync", headers, {"force": True})
    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        time.sleep(30)
        data = http("GET", base, headers).get("data", {})
        failed = data.get("failed_at")
        if failed and datetime.fromisoformat(failed.replace("Z", "+00:00")) > started:
            raise Abort("Fivetran sync failed")
        done = data.get("succeeded_at")
        if done and datetime.fromisoformat(done.replace("Z", "+00:00")) > started:
            break
    else:
        raise Abort("Fivetran sync did not finish within 30 minutes")

    from google.cloud import bigquery

    project = os.environ["BIGQUERY_PROJECT"]
    q = (
        "select countif(not coalesce(_fivetran_deleted, false)) as live "
        f"from `{project}.supabase_postgres_public.applications`"
    )
    live = list(bigquery.Client(project=project).query(q).result())[0].live
    if live != expected:
        raise Abort(f"BigQuery has {live} live rows, expected {expected}")
    log(f"fivetran: synced, bigquery live rows {live}")


def dbt() -> None:
    for sub in ("run", "test"):
        out = run([DBT, sub], cwd=REPO / "dbt", label=f"dbt {sub}")
        summary = [l for l in out.splitlines() if "Done." in l]
        log(f"dbt {sub}: {summary[-1].split('Done.')[-1].strip() if summary else 'ok'}")


def hightouch_sync() -> None:
    sync_id = os.environ["HIGHTOUCH_SYNC_ID_SHEET"]
    headers = {"Authorization": f"Bearer {os.environ['HIGHTOUCH_API_KEY']}"}
    base = f"https://api.hightouch.com/api/v1/syncs/{sync_id}"
    run_id = str(http("POST", f"{base}/trigger", headers, {"fullResync": False})["id"])
    deadline = time.time() + 15 * 60
    while time.time() < deadline:
        time.sleep(20)
        runs = http("GET", f"{base}/runs?runId={run_id}", headers).get("data", [])
        status = runs[0].get("status") if runs else None
        if status == "success":
            log(f"hightouch: success, {runs[0].get('querySize')} rows")
            return
        if status in ("failed", "cancelled", "warning", "interrupted"):
            raise Abort(f"Hightouch sync {status}")
    raise Abort("Hightouch sync did not finish within 15 minutes")


def build_and_gate() -> None:
    run([PY, "-m", "nerdjoy_pipeline.metrics_extract", "--source", "bigquery",
         "--output", "metrics.json"], label="metrics_extract")
    run([PY, "dashboard/build.py"], label="dashboard build (guard)")
    run([PY, "scripts/verify_public.py"], label="verify_public")
    run([PY, "scripts/repo_privacy_scan.py"], label="repo_privacy_scan")
    totals = json.loads((REPO / "metrics.json").read_text())["totals"]
    log(f"build: {totals['applications']} applications, {totals['companies']} companies, gates clean")


def deploy() -> None:
    host, port = os.environ["DEPLOY_SSH_HOST"], os.environ.get("DEPLOY_SSH_PORT", "22")
    user, key = os.environ["DEPLOY_SSH_USER"], os.environ["DEPLOY_SSH_KEY"]
    path, url = os.environ["DEPLOY_PATH"].rstrip("/"), os.environ["DEPLOY_URL"].rstrip("/")
    target = f"{user}@{host}"
    ssh = ["ssh", "-p", port, "-i", key, "-o", "ConnectTimeout=20", "-o", "BatchMode=yes", target]
    backup = f"~/{path.replace('/', '_')}_backup_$(date +%Y%m%d%H%M%S)"
    prune = (
        f"ls -dt ~/{path.replace('/', '_')}_backup_* | tail -n +{KEEP_SERVER_BACKUPS + 1} "
        "| xargs -r rm -rf"
    )
    run(ssh + [f"cp -a ~/{path} {backup} && {prune}"], label="server backup")
    dist = REPO / "dashboard" / "dist"
    run(["scp", "-q", "-P", port, "-i", key, "-o", "BatchMode=yes",
         *[str(dist / f) for f in DIST_FILES], f"{target}:{path}/"], label="upload")
    for name in DIST_FILES:
        with urllib.request.urlopen(f"{url}/{name}?v={int(time.time())}", timeout=30) as r:
            if r.read() != (dist / name).read_bytes():
                raise Abort(f"live {name} differs from the build after upload")
    log("deploy: live files identical to build")


# --- driver ------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="run even if the tracker is unchanged")
    parser.add_argument("--no-deploy", action="store_true", help="stop after the gates")
    args = parser.parse_args()

    LOCAL.mkdir(exist_ok=True)
    lock = open(LOCAL / "refresh.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another refresh is running; exiting")
        return 0

    if not TRACKER.exists():
        log(f"skip: no tracker at {TRACKER}")
        return 0
    digest = hashlib.sha256(TRACKER.read_bytes()).hexdigest()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    if not args.force and state.get("tracker_sha256") == digest:
        log("skip: tracker unchanged since last successful refresh")
        return 0

    load_env()
    log("refresh: start")
    try:
        expected = load_postgres()
        fivetran_sync(expected)
        dbt()
        hightouch_sync()
        build_and_gate()
        if not args.no_deploy:
            deploy()
    except Abort as exc:
        log(f"FAILED: {exc}")
        notify("nerdjoy refresh failed", str(exc)[:120].replace('"', "'"))
        return 1
    except Exception as exc:  # network, auth, driver errors: still stop and say so
        log(f"FAILED: {type(exc).__name__}: {str(exc)[:200]}")
        notify("nerdjoy refresh failed", type(exc).__name__)
        return 1

    if not args.no_deploy:
        STATE.write_text(json.dumps({"tracker_sha256": digest,
                                     "succeeded_at": datetime.now().isoformat()}))
    log("refresh: done")
    notify("nerdjoy refresh", f"Dashboard updated: {expected} applications")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
