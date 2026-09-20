from pathlib import Path

from nerdjoy_pipeline.pg_loader import (
    CREATE_TABLE_SQL,
    UPSERT_SQL,
    application_key,
    load_applications,
    to_row,
)
from nerdjoy_pipeline.tracker import read_tracker


class FakeCursor:
    def __init__(self):
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def executemany(self, sql, seq):
        for params in seq:
            self.executed.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1


def test_application_key_is_stable(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert application_key(apps[0]) == application_key(apps[0])
    assert len(application_key(apps[0])) == 64


def test_application_key_differs_per_application(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    assert len({application_key(a) for a in apps}) == len(apps)


def test_to_row_matches_upsert_placeholder_count(sample_tracker_path: Path):
    app = read_tracker(sample_tracker_path)[0]
    assert len(to_row(app)) == UPSERT_SQL.count("%s")


def test_upsert_is_idempotent_by_key():
    assert "ON CONFLICT (application_key) DO UPDATE" in UPSERT_SQL


def test_create_table_declares_the_conflict_target():
    assert "application_key" in CREATE_TABLE_SQL
    assert "PRIMARY KEY" in CREATE_TABLE_SQL.upper()


def test_load_creates_the_table_then_upserts_every_row(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    conn = FakeConn()
    count = load_applications(apps, conn)
    assert count == 10
    statements = [sql for sql, _ in conn.cursor_obj.executed]
    assert statements[0] == CREATE_TABLE_SQL
    assert statements.count(UPSERT_SQL) == 10
    assert conn.commits == 1


def test_load_does_not_mutate_the_tracker(sample_tracker_path: Path):
    before = sample_tracker_path.read_bytes()
    load_applications(read_tracker(sample_tracker_path), FakeConn())
    assert sample_tracker_path.read_bytes() == before


def test_running_load_twice_produces_the_same_rows(sample_tracker_path: Path):
    apps = read_tracker(sample_tracker_path)
    first = [to_row(a) for a in apps]
    second = [to_row(a) for a in read_tracker(sample_tracker_path)]
    assert first == second
