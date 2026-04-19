"""
Storage layer backed by SQLite.
The public interface stays close to the old Baserow service so main.py
does not need a second architecture.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from services.lead_utils import coerce_amount, normalize_phone

logger = logging.getLogger(__name__)

if os.getenv("RENDER"):
    data_dir = Path("/data")
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / ".test").touch()
        (data_dir / ".test").unlink()
        DB_PATH = data_dir / "leads.db"
    except PermissionError:
        DB_PATH = Path("/tmp/data/leads.db")
else:
    DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leads.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str):
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _init_db():
    with _get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                name              TEXT,
                phone             TEXT,
                source            TEXT,
                source_platform   TEXT,
                source_channel    TEXT,
                source_account    TEXT,
                source_listing    TEXT,
                source_campaign   TEXT,
                utm_source        TEXT,
                utm_medium        TEXT,
                utm_campaign      TEXT,
                client_type       TEXT,
                concrete_grade    TEXT,
                volume            REAL,
                address           TEXT,
                comment           TEXT,
                calculated_amount REAL,
                sales_priority    TEXT,
                assigned_manager  TEXT,
                lead_status       TEXT,
                next_action       TEXT,
                route_bucket      TEXT,
                sales_playbook    TEXT,
                qualification_script TEXT,
                sla_minutes       INTEGER,
                contact_deadline_at TEXT,
                lead_id           INTEGER,
                created_at        TEXT
            );

            CREATE TABLE IF NOT EXISTS calculations (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                concrete_grade TEXT,
                volume         REAL,
                distance       REAL,
                total_amount   REAL,
                timestamp      TEXT
            );

            CREATE TABLE IF NOT EXISTS logs (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                action    TEXT,
                error     TEXT,
                data      TEXT,
                timestamp TEXT
            );
            """
        )

        for column, column_type in (
            ("source_platform", "TEXT"),
            ("source_channel", "TEXT"),
            ("source_account", "TEXT"),
            ("source_listing", "TEXT"),
            ("source_campaign", "TEXT"),
            ("utm_source", "TEXT"),
            ("utm_medium", "TEXT"),
            ("utm_campaign", "TEXT"),
            ("client_type", "TEXT"),
            ("comment", "TEXT"),
            ("sales_priority", "TEXT"),
            ("assigned_manager", "TEXT"),
            ("lead_status", "TEXT"),
            ("next_action", "TEXT"),
            ("route_bucket", "TEXT"),
            ("sales_playbook", "TEXT"),
            ("qualification_script", "TEXT"),
            ("sla_minutes", "INTEGER"),
            ("contact_deadline_at", "TEXT"),
        ):
            _ensure_column(conn, "leads", column, column_type)

    logger.info(f"SQLite initialized: {DB_PATH}")


_init_db()


class BaserowService:
    """SQLite implementation with the old service interface."""

    def is_available(self) -> bool:
        return True

    async def log_lead(self, lead_data: dict):
        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO leads
                    (name, phone, source, source_platform, source_channel, source_account,
                     source_listing, source_campaign, utm_source, utm_medium, utm_campaign,
                     client_type, concrete_grade, volume, address, comment, calculated_amount,
                     sales_priority, assigned_manager, lead_status, next_action, route_bucket,
                     sales_playbook, qualification_script, sla_minutes, contact_deadline_at,
                     lead_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lead_data.get("name"),
                        normalize_phone(lead_data.get("phone")) or lead_data.get("phone"),
                        lead_data.get("source"),
                        lead_data.get("source_platform"),
                        lead_data.get("source_channel"),
                        lead_data.get("source_account"),
                        lead_data.get("source_listing"),
                        lead_data.get("source_campaign"),
                        lead_data.get("utm_source"),
                        lead_data.get("utm_medium"),
                        lead_data.get("utm_campaign"),
                        lead_data.get("client_type"),
                        lead_data.get("concrete_grade"),
                        lead_data.get("volume"),
                        lead_data.get("address"),
                        lead_data.get("comment"),
                        coerce_amount(lead_data.get("calculated_amount")),
                        lead_data.get("sales_priority"),
                        lead_data.get("assigned_manager"),
                        lead_data.get("lead_status"),
                        lead_data.get("next_action"),
                        lead_data.get("route_bucket"),
                        lead_data.get("sales_playbook"),
                        lead_data.get("qualification_script"),
                        lead_data.get("sla_minutes"),
                        lead_data.get("contact_deadline_at"),
                        lead_data.get("lead_id"),
                        lead_data.get("created_at") or datetime.now().isoformat(),
                    ),
                )
            logger.info("Lead saved to SQLite")
        except Exception as e:
            logger.error(f"SQLite lead save failed: {e}")

    async def log_calculation(self, calc_data: dict, result: dict):
        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO calculations
                    (concrete_grade, volume, distance, total_amount, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        calc_data.get("concrete_grade"),
                        calc_data.get("volume"),
                        calc_data.get("distance"),
                        result.get("total"),
                        datetime.now().isoformat(),
                    ),
                )
        except Exception as e:
            logger.error(f"SQLite calculation save failed: {e}")

    async def log_error(self, action: str, error: str, data: dict):
        try:
            with _get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO logs (action, error, data, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        action,
                        error,
                        json.dumps(data, ensure_ascii=False)[:4000],
                        datetime.now().isoformat(),
                    ),
                )
        except Exception as e:
            logger.error(f"SQLite error log failed: {e}")

    def get_leads(self, limit: int = 100) -> list:
        try:
            with _get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"SQLite read failed: {e}")
            return []

    def get_dashboard_stats(self) -> dict:
        today = datetime.now().date().isoformat()
        week_start = datetime.now().date().fromordinal(datetime.now().date().toordinal() - 6).isoformat()

        try:
            with _get_conn() as conn:
                total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
                today_count = conn.execute(
                    "SELECT COUNT(*) FROM leads WHERE substr(created_at, 1, 10) = ?",
                    (today,),
                ).fetchone()[0]
                week_count = conn.execute(
                    "SELECT COUNT(*) FROM leads WHERE substr(created_at, 1, 10) >= ?",
                    (week_start,),
                ).fetchone()[0]
                source_rows = conn.execute(
                    """
                    SELECT COALESCE(source_platform, source, 'unknown') AS source, COUNT(*) AS cnt
                    FROM leads
                    WHERE substr(created_at, 1, 10) >= ?
                    GROUP BY COALESCE(source_platform, source, 'unknown')
                    ORDER BY cnt DESC, source ASC
                    """,
                    (week_start,),
                ).fetchall()
                channel_rows = conn.execute(
                    """
                    SELECT COALESCE(source_channel, 'unknown') AS channel, COUNT(*) AS cnt
                    FROM leads
                    WHERE substr(created_at, 1, 10) >= ?
                    GROUP BY COALESCE(source_channel, 'unknown')
                    ORDER BY cnt DESC, channel ASC
                    """,
                    (week_start,),
                ).fetchall()
                priority_rows = conn.execute(
                    """
                    SELECT COALESCE(sales_priority, 'unknown') AS priority, COUNT(*) AS cnt
                    FROM leads
                    WHERE substr(created_at, 1, 10) >= ?
                    GROUP BY COALESCE(sales_priority, 'unknown')
                    ORDER BY cnt DESC, priority ASC
                    """,
                    (week_start,),
                ).fetchall()
                manager_rows = conn.execute(
                    """
                    SELECT COALESCE(assigned_manager, 'unassigned') AS manager, COUNT(*) AS cnt
                    FROM leads
                    WHERE substr(created_at, 1, 10) >= ?
                    GROUP BY COALESCE(assigned_manager, 'unassigned')
                    ORDER BY cnt DESC, manager ASC
                    """,
                    (week_start,),
                ).fetchall()
                playbook_rows = conn.execute(
                    """
                    SELECT COALESCE(sales_playbook, 'unassigned') AS playbook, COUNT(*) AS cnt
                    FROM leads
                    WHERE substr(created_at, 1, 10) >= ?
                    GROUP BY COALESCE(sales_playbook, 'unassigned')
                    ORDER BY cnt DESC, playbook ASC
                    """,
                    (week_start,),
                ).fetchall()
                overdue_rows = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM leads
                    WHERE contact_deadline_at IS NOT NULL
                      AND contact_deadline_at != ''
                      AND contact_deadline_at < ?
                      AND COALESCE(lead_status, 'new') NOT IN ('completed', 'won', 'closed', 'lost')
                    """,
                    (datetime.now().isoformat(),),
                ).fetchone()
                due_soon_rows = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM leads
                    WHERE contact_deadline_at IS NOT NULL
                      AND contact_deadline_at != ''
                      AND contact_deadline_at >= ?
                      AND contact_deadline_at < ?
                      AND COALESCE(lead_status, 'new') NOT IN ('completed', 'won', 'closed', 'lost')
                    """,
                    (
                        datetime.now().isoformat(),
                        datetime.fromtimestamp(datetime.now().timestamp() + 15 * 60).isoformat(),
                    ),
                ).fetchone()
                latest = conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 1").fetchone()

            return {
                "total": total,
                "today": today_count,
                "week": week_count,
                "sources": [dict(row) for row in source_rows],
                "channels": [dict(row) for row in channel_rows],
                "priorities": [dict(row) for row in priority_rows],
                "managers": [dict(row) for row in manager_rows],
                "playbooks": [dict(row) for row in playbook_rows],
                "overdue_contacts": int((overdue_rows or {"cnt": 0})["cnt"]),
                "due_soon_contacts": int((due_soon_rows or {"cnt": 0})["cnt"]),
                "latest": dict(latest) if latest else None,
            }
        except Exception as e:
            logger.error(f"SQLite dashboard stats failed: {e}")
            return {
                "total": 0,
                "today": 0,
                "week": 0,
                "sources": [],
                "channels": [],
                "priorities": [],
                "managers": [],
                "playbooks": [],
                "overdue_contacts": 0,
                "due_soon_contacts": 0,
                "latest": None,
            }

    def get_logs(self, limit: int = 20, action: str | None = None) -> list[dict]:
        try:
            with _get_conn() as conn:
                if action:
                    rows = conn.execute(
                        "SELECT * FROM logs WHERE action = ? ORDER BY id DESC LIMIT ?",
                        (action, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM logs ORDER BY id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"SQLite log read failed: {e}")
            return []

    def get_workqueue(
        self,
        limit: int = 30,
        assigned_manager: str | None = None,
        route_bucket: str | None = None,
    ) -> list[dict]:
        try:
            with _get_conn() as conn:
                query = """
                    SELECT *,
                           CASE COALESCE(sales_priority, 'normal')
                               WHEN 'high' THEN 0
                               WHEN 'normal' THEN 1
                               ELSE 2
                           END AS priority_rank,
                           CASE
                               WHEN contact_deadline_at IS NOT NULL
                                AND contact_deadline_at != ''
                                AND contact_deadline_at < ? THEN 0
                               WHEN contact_deadline_at IS NOT NULL
                                AND contact_deadline_at != '' THEN 1
                               ELSE 2
                           END AS deadline_rank
                    FROM leads
                    WHERE COALESCE(lead_status, 'new') NOT IN ('completed', 'won', 'closed', 'lost')
                """
                params: list = [datetime.now().isoformat()]

                if assigned_manager:
                    query += " AND COALESCE(assigned_manager, '') = ?"
                    params.append(assigned_manager)
                if route_bucket:
                    query += " AND COALESCE(route_bucket, '') = ?"
                    params.append(route_bucket)

                query += """
                    ORDER BY deadline_rank ASC,
                             priority_rank ASC,
                             COALESCE(contact_deadline_at, '9999-12-31T23:59:59') ASC,
                             id DESC
                    LIMIT ?
                """
                params.append(limit)

                rows = conn.execute(query, params).fetchall()

            result = []
            now_iso = datetime.now().isoformat()
            for row in rows:
                item = dict(row)
                deadline = item.get("contact_deadline_at")
                item["is_overdue"] = bool(deadline and deadline < now_iso)
                result.append(item)
            return result
        except Exception as e:
            logger.error(f"SQLite workqueue failed: {e}")
            return []

    def update_local_lead(self, local_id: int, updates: dict) -> dict | None:
        allowed_fields = {
            "assigned_manager",
            "lead_status",
            "next_action",
            "sales_priority",
            "sales_playbook",
            "qualification_script",
            "sla_minutes",
            "contact_deadline_at",
            "source_campaign",
            "comment",
        }
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        if not safe_updates:
            return None

        try:
            with _get_conn() as conn:
                assignments = ", ".join(f"{field} = ?" for field in safe_updates)
                values = list(safe_updates.values()) + [local_id]
                conn.execute(
                    f"UPDATE leads SET {assignments} WHERE id = ?",
                    values,
                )
                row = conn.execute("SELECT * FROM leads WHERE id = ?", (local_id,)).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"SQLite local lead update failed: {e}")
            return None

    def find_lead_by_phone(self, phone: str) -> dict | None:
        normalized = normalize_phone(phone)
        if not normalized:
            return None

        digits = normalized.lstrip("+")
        try:
            with _get_conn() as conn:
                rows = conn.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 200").fetchall()
            for row in rows:
                row_dict = dict(row)
                row_phone = normalize_phone(row_dict.get("phone"))
                if not row_phone:
                    continue
                row_digits = row_phone.lstrip("+")
                if row_phone == normalized or row_digits.endswith(digits[-10:]):
                    return row_dict
        except Exception as e:
            logger.error(f"SQLite duplicate lookup failed: {e}")
        return None
