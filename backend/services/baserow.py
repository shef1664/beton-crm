"""
Слой хранения данных — SQLite (замена Baserow).
Интерфейс сохранён: main.py не требует изменений.
"""
import sqlite3
import logging
import json
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# На Render — персистентный диск /data, локально — рядом с backend/
import os
if os.getenv("RENDER"):
    # Пробуем примонтированный диск, fallback на /tmp
    _data_dir = Path("/data")
    try:
        _data_dir.mkdir(parents=True, exist_ok=True)
        (_data_dir / ".test").touch()
        (_data_dir / ".test").unlink()
        DB_PATH = _data_dir / "leads.db"
    except PermissionError:
        DB_PATH = Path("/tmp/data/leads.db")
else:
    DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leads.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """Создаёт таблицы если их нет."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS leads (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT,
                phone            TEXT,
                source           TEXT,
                concrete_grade   TEXT,
                volume           REAL,
                address          TEXT,
                calculated_amount REAL,
                lead_id          INTEGER,
                created_at       TEXT
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
        """)
    logger.info(f"✅ SQLite база данных: {DB_PATH}")


# Инициализируем при импорте
_init_db()


class BaserowService:
    """SQLite-реализация с тем же интерфейсом что был у Baserow."""

    def is_available(self) -> bool:
        return True

    async def log_lead(self, lead_data: dict):
        """Сохраняет заявку в таблицу leads."""
        try:
            with _get_conn() as conn:
                conn.execute(
                    """INSERT INTO leads
                       (name, phone, source, concrete_grade, volume,
                        address, calculated_amount, lead_id, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        lead_data.get("name"),
                        lead_data.get("phone"),
                        lead_data.get("source"),
                        lead_data.get("concrete_grade"),
                        lead_data.get("volume"),
                        lead_data.get("address"),
                        lead_data.get("calculated_amount"),
                        lead_data.get("lead_id"),
                        lead_data.get("created_at") or datetime.now().isoformat(),
                    ),
                )
            logger.info("✅ Заявка сохранена в SQLite")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в SQLite: {e}")

    async def log_calculation(self, calc_data: dict, result: dict):
        """Сохраняет расчёт в таблицу calculations."""
        try:
            with _get_conn() as conn:
                conn.execute(
                    """INSERT INTO calculations
                       (concrete_grade, volume, distance, total_amount, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        calc_data.get("concrete_grade"),
                        calc_data.get("volume"),
                        calc_data.get("distance"),
                        result.get("total"),
                        datetime.now().isoformat(),
                    ),
                )
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения расчёта: {e}")

    async def log_error(self, action: str, error: str, data: dict):
        """Сохраняет ошибку в таблицу logs."""
        try:
            with _get_conn() as conn:
                conn.execute(
                    """INSERT INTO logs (action, error, data, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (
                        action,
                        error,
                        json.dumps(data, ensure_ascii=False)[:2000],
                        datetime.now().isoformat(),
                    ),
                )
        except Exception as e:
            logger.error(f"❌ Ошибка записи лога: {e}")

    def get_leads(self, limit: int = 100) -> list:
        """Возвращает последние заявки (для отладки)."""
        try:
            with _get_conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ Ошибка чтения заявок: {e}")
            return []
