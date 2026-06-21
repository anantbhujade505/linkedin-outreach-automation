from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from models.schemas import ExtractedProfile, ProfileStatus, RunStatus
from utils.timers import iso_now


class SQLiteRepository:
    def __init__(self, db_path: str, schema_path: str = "database/schema.sql") -> None:
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(self.schema_path.read_text(encoding="utf-8"))

    def create_run(self, run_id: str, job_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs (id, job_type, status, started_at) VALUES (?, ?, ?, ?)",
                (run_id, job_type, RunStatus.RUNNING.value, iso_now()),
            )

    def finish_run(self, run_id: str, status: RunStatus, error_message: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = ?, error_message = ? WHERE id = ?",
                (status.value, iso_now(), error_message, run_id),
            )

    def upsert_profile(
        self,
        linkedin_url: str,
        first_name: str | None = None,
        company: str | None = None,
        sheet_row: int | None = None,
        status: ProfileStatus = ProfileStatus.NEW,
    ) -> int:
        now = iso_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO profiles (linkedin_url, first_name, company, sheet_row, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(linkedin_url) DO UPDATE SET
                    first_name = excluded.first_name,
                    company = excluded.company,
                    sheet_row = excluded.sheet_row,
                    updated_at = excluded.updated_at
                """,
                (linkedin_url, first_name, company, sheet_row, status.value, now, now),
            )
            row = conn.execute("SELECT id FROM profiles WHERE linkedin_url = ?", (linkedin_url,)).fetchone()
            return int(row["id"])

    def update_profile_context(self, profile_id: int, extracted: ExtractedProfile) -> None:
        with self._connect() as conn:
            recent_activity = extracted.recent_activity or "\n\n".join(extracted.latest_posts)
            conn.execute(
                """
                UPDATE profiles SET name = ?, headline = ?, current_role = ?, mutual_connections = ?,
                    recent_activity = ?, updated_at = ? WHERE id = ?
                """,
                (
                    extracted.name,
                    extracted.headline,
                    extracted.current_role,
                    extracted.mutual_connections,
                    recent_activity,
                    iso_now(),
                    profile_id,
                ),
            )

    def update_profile_status(self, profile_id: int, status: ProfileStatus) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE profiles SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, iso_now(), profile_id),
            )

    def record_message(
        self,
        run_id: str,
        profile_id: int,
        message_type: str,
        draft: str,
        reviewed: str,
        final: str,
        char_limit: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (run_id, profile_id, message_type, draft, reviewed, final, char_limit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, profile_id, message_type, draft, reviewed, final, char_limit, iso_now()),
            )

    def record_action(
        self,
        run_id: str,
        action_type: str,
        status: str,
        profile_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO actions (run_id, profile_id, action_type, status, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, profile_id, action_type, status, json.dumps(metadata or {}), iso_now()),
            )

    def create_or_update_followup(self, profile_id: int, connection_sent_at: str, status: str = "pending") -> None:
        now = iso_now()
        with self._connect() as conn:
            existing = conn.execute("SELECT id FROM followups WHERE profile_id = ? AND status = 'pending'", (profile_id,)).fetchone()
            if existing:
                conn.execute("UPDATE followups SET updated_at = ? WHERE id = ?", (now, existing["id"]))
            else:
                conn.execute(
                    """
                    INSERT INTO followups (profile_id, connection_sent_at, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (profile_id, connection_sent_at, status, now, now),
                )

    def pending_followups(self, older_than_iso: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT f.*, p.linkedin_url, p.sheet_row, p.first_name, p.company
                    FROM followups f
                    JOIN profiles p ON p.id = f.profile_id
                    WHERE f.status = 'pending' AND f.connection_sent_at <= ?
                    ORDER BY f.connection_sent_at ASC
                    """,
                    (older_than_iso,),
                )
            )

    def mark_followup(self, followup_id: int, status: str, accepted_at: str | None = None, withdrawn_at: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE followups SET status = ?, accepted_at = COALESCE(?, accepted_at),
                    withdrawn_at = COALESCE(?, withdrawn_at), updated_at = ? WHERE id = ?
                """,
                (status, accepted_at, withdrawn_at, iso_now(), followup_id),
            )

    def count_actions_since(self, action_type: str, since_iso: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM actions WHERE action_type = ? AND status = 'success' AND created_at >= ?",
                (action_type, since_iso),
            ).fetchone()
            return int(row["count"])
