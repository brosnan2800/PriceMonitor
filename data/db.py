#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 持久化层
表结构：users / watchlist / alerts / tasks / push_log
"""

import sqlite3
import json
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "secretary.db"


# ── 初始化 ────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     TEXT PRIMARY KEY,          -- 平台唯一ID（feishu open_id / telegram chat_id）
    platform    TEXT NOT NULL,             -- feishu / telegram
    username    TEXT,
    settings    TEXT DEFAULT '{}',         -- JSON：推送偏好
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    last_seen   TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    symbol      TEXT NOT NULL,             -- 股票代码 / 货币对 / 加密货币
    asset_type  TEXT NOT NULL,             -- a_stock / hk_stock / us_stock / forex / crypto / commodity
    name        TEXT,                      -- 显示名称，如"贵州茅台"
    added_at    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(user_id, symbol)
);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    condition       TEXT NOT NULL,         -- above / below / change_pct
    threshold       REAL NOT NULL,
    enabled         INTEGER DEFAULT 1,
    cooldown_until  TEXT,                  -- 冷却到期时间，期间不重复推送
    triggered_count INTEGER DEFAULT 0,
    in_trigger      INTEGER DEFAULT 0,     -- 1=当前处于触发状态，等待价格回归正常区间
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    task_type   TEXT NOT NULL,             -- daily_report / announcement / price_alert / index_report
    config      TEXT DEFAULT '{}',         -- JSON：任务参数
    cron_expr   TEXT NOT NULL,             -- cron 表达式，如 "0 9 * * 1-5"
    enabled     INTEGER DEFAULT 1,
    last_run_at TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS push_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT NOT NULL,
    task_id      INTEGER,
    content_hash TEXT,                     -- 防重复推送
    pushed_at    TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS builtin_report_log (
    report_type  TEXT NOT NULL,            -- 'morning' | 'digest'
    sent_date    TEXT NOT NULL,            -- '2026-05-12'
    sent_at      TEXT DEFAULT (datetime('now','localtime')),
    status       TEXT DEFAULT 'sent',      -- running | sent | failed
    claimed_at   TEXT,
    last_error   TEXT,
    UNIQUE (report_type, sent_date)        -- 每天每类只记录一次
);
"""


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库，建表"""
    with _conn() as conn:
        conn.executescript(SCHEMA)
        _migrate_builtin_report_log(conn)
    logger.info(f"数据库初始化完成: {DB_PATH}")


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _migrate_builtin_report_log(conn: sqlite3.Connection) -> None:
    """兼容历史库：为 builtin_report_log 增加运行态字段。"""
    if not _column_exists(conn, "builtin_report_log", "status"):
        conn.execute("ALTER TABLE builtin_report_log ADD COLUMN status TEXT DEFAULT 'sent'")
    if not _column_exists(conn, "builtin_report_log", "claimed_at"):
        conn.execute("ALTER TABLE builtin_report_log ADD COLUMN claimed_at TEXT")
    if not _column_exists(conn, "builtin_report_log", "last_error"):
        conn.execute("ALTER TABLE builtin_report_log ADD COLUMN last_error TEXT")


# ── Users ─────────────────────────────────────────────────────────────

def upsert_user(user_id: str, platform: str, username: str = "") -> None:
    with _conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, platform, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen = datetime('now','localtime'),
                username = excluded.username
        """, (user_id, platform, username))


def get_user(user_id: str) -> Optional[Dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_settings(user_id: str) -> Dict:
    user = get_user(user_id)
    if not user:
        return {}
    try:
        return json.loads(user.get("settings") or "{}")
    except json.JSONDecodeError:
        return {}


def update_user_settings(user_id: str, settings: Dict) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET settings = ? WHERE user_id = ?",
                     (json.dumps(settings, ensure_ascii=False), user_id))


# ── Watchlist ─────────────────────────────────────────────────────────

def add_watchlist(user_id: str, symbol: str, asset_type: str, name: str = "") -> bool:
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO watchlist (user_id, symbol, asset_type, name) VALUES (?, ?, ?, ?)",
                (user_id, symbol.upper(), asset_type, name)
            )
        return True
    except Exception as e:
        logger.error(f"添加自选失败: {e}")
        return False


def remove_watchlist(user_id: str, symbol: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM watchlist WHERE user_id = ? AND symbol = ?",
                           (user_id, symbol.upper()))
        return cur.rowcount > 0


def get_watchlist(user_id: str) -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM watchlist WHERE user_id = ? ORDER BY added_at",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Alerts ────────────────────────────────────────────────────────────

def add_alert(user_id: str, symbol: str, condition: str, threshold: float) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO alerts (user_id, symbol, condition, threshold) VALUES (?, ?, ?, ?)",
            (user_id, symbol.upper(), condition, threshold)
        )
        return cur.lastrowid


def get_alerts(user_id: str, enabled_only: bool = True) -> List[Dict]:
    with _conn() as conn:
        sql = "SELECT * FROM alerts WHERE user_id = ?"
        params: list = [user_id]
        if enabled_only:
            sql += " AND enabled = 1"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_all_alerts(enabled_only: bool = True) -> List[Dict]:
    """获取所有用户的价格预警（供调度器全局扫描）"""
    with _conn() as conn:
        sql = "SELECT * FROM alerts"
        if enabled_only:
            sql += " WHERE enabled = 1"
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def delete_alert(alert_id: int, user_id: str) -> bool:
    """删除指定预警，校验 user_id 防止越权"""
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id)
        )
        return cur.rowcount > 0


def set_alert_cooldown(alert_id: int, until: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE alerts SET cooldown_until = ?, triggered_count = triggered_count + 1 WHERE id = ?",
            (until, alert_id)
        )


def toggle_alert(alert_id: int, enabled: bool) -> None:
    with _conn() as conn:
        conn.execute("UPDATE alerts SET enabled = ? WHERE id = ?", (int(enabled), alert_id))


def set_alert_triggered(alert_id: int) -> None:
    """标记预警为触发状态（等待价格回归正常才能再次触发）"""
    with _conn() as conn:
        conn.execute(
            "UPDATE alerts SET in_trigger = 1, triggered_count = triggered_count + 1 WHERE id = ?",
            (alert_id,)
        )


def reset_alert_triggered(alert_id: int) -> None:
    """价格恢复正常区间后重置触发状态（允许下次再触发）"""
    with _conn() as conn:
        conn.execute("UPDATE alerts SET in_trigger = 0 WHERE id = ?", (alert_id,))


# ── Tasks ─────────────────────────────────────────────────────────────

def add_task(user_id: str, task_type: str, config: Dict, cron_expr: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (user_id, task_type, config, cron_expr) VALUES (?, ?, ?, ?)",
            (user_id, task_type, json.dumps(config, ensure_ascii=False), cron_expr)
        )
        return cur.lastrowid


def upsert_announcement_task_merge(user_id: str, new_symbols: List[str], cron_expr: Optional[str]) -> Tuple[int, bool, List[str], str]:
    """公告监控 upsert-merge：
    - 有则累加股票（去重），cron 有传则更新，无传则沿用
    - 无则新建（cron 默认 0 9,12,15 * * 1-5）
    返回 (task_id, is_new, final_symbols, final_cron)
    """
    default_cron = "0 9,12,15 * * 1-5"
    with _conn() as conn:
        row = conn.execute(
            "SELECT id, config, cron_expr FROM tasks WHERE user_id = ? AND task_type = 'announcement' LIMIT 1",
            (user_id,)
        ).fetchone()
        if row:
            existing_config = json.loads(row["config"] or "{}")
            existing_symbols = existing_config.get("symbols", [])
            # 累加去重，保持顺序
            merged = list(dict.fromkeys(existing_symbols + new_symbols))
            final_cron = cron_expr if cron_expr else row["cron_expr"]
            config_json = json.dumps({"symbols": merged}, ensure_ascii=False)
            conn.execute(
                "UPDATE tasks SET config = ?, cron_expr = ?, enabled = 1 WHERE id = ?",
                (config_json, final_cron, row["id"])
            )
            return row["id"], False, merged, final_cron
        else:
            final_cron = cron_expr if cron_expr else default_cron
            config_json = json.dumps({"symbols": new_symbols}, ensure_ascii=False)
            cur = conn.execute(
                "INSERT INTO tasks (user_id, task_type, config, cron_expr) VALUES (?, 'announcement', ?, ?)",
                (user_id, config_json, final_cron)
            )
            return cur.lastrowid, True, new_symbols, final_cron


def update_task_config(task_id: int, config: Dict) -> None:
    """更新任务 config 字段"""
    with _conn() as conn:
        conn.execute(
            "UPDATE tasks SET config = ? WHERE id = ?",
            (json.dumps(config, ensure_ascii=False), task_id)
        )


def get_tasks(user_id: str, enabled_only: bool = False) -> List[Dict]:
    with _conn() as conn:
        sql = "SELECT * FROM tasks WHERE user_id = ?"
        params: list = [user_id]
        if enabled_only:
            sql += " AND enabled = 1"
        rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["config"] = json.loads(d["config"] or "{}")
            except json.JSONDecodeError:
                d["config"] = {}
            result.append(d)
        return result


def get_all_enabled_tasks() -> List[Dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM tasks WHERE enabled = 1").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["config"] = json.loads(d["config"] or "{}")
            except json.JSONDecodeError:
                d["config"] = {}
            result.append(d)
        return result


def toggle_task(task_id: int, enabled: bool) -> None:
    with _conn() as conn:
        conn.execute("UPDATE tasks SET enabled = ? WHERE id = ?", (int(enabled), task_id))


def delete_task(task_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cur.rowcount > 0


def update_task_last_run(task_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE tasks SET last_run_at = datetime('now','localtime') WHERE id = ?",
            (task_id,)
        )


# ── Push Log（防重复推送） ────────────────────────────────────────────

def log_push(user_id: str, task_id: Optional[int], content_hash: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO push_log (user_id, task_id, content_hash) VALUES (?, ?, ?)",
            (user_id, task_id, content_hash)
        )


def already_pushed(user_id: str, content_hash: str, within_hours: int = 24) -> bool:
    with _conn() as conn:
        row = conn.execute("""
            SELECT 1 FROM push_log
            WHERE user_id = ? AND content_hash = ?
              AND pushed_at >= datetime('now', ?, 'localtime')
            LIMIT 1
        """, (user_id, content_hash, f"-{within_hours} hours")).fetchone()
        return row is not None


# ── Builtin Report Log（内置任务去重） ────────────────────────────────

def builtin_report_sent_today(report_type: str) -> bool:
    """检查今天指定类型的内置报告是否已发送（防止重启导致重复推送）"""
    from datetime import datetime as _dt
    today = _dt.now().strftime('%Y-%m-%d')
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM builtin_report_log
            WHERE report_type=? AND sent_date=?
              AND (status='sent' OR (status IS NULL AND sent_at IS NOT NULL))
            LIMIT 1
            """,
            (report_type, today)
        ).fetchone()
    return row is not None


def try_claim_builtin_report(report_type: str, stale_after_minutes: int = 10) -> bool:
    """
    原子抢占当天内置报告发送资格。
    返回 True 表示本次触发链路获得发送资格；False 表示已被其他链路占用/完成。
    """
    from datetime import datetime as _dt, timedelta as _td

    now = _dt.now()
    today = now.strftime('%Y-%m-%d')
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    with _conn() as conn:
        row = conn.execute(
            """
            SELECT status, claimed_at, sent_at
            FROM builtin_report_log
            WHERE report_type=? AND sent_date=?
            LIMIT 1
            """,
            (report_type, today)
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO builtin_report_log (report_type, sent_date, status, claimed_at, sent_at)
                VALUES (?, ?, 'running', ?, NULL)
                """,
                (report_type, today, now_str)
            )
            return True

        status = row["status"]

        # 兼容历史数据：没有 status 且有 sent_at 视为已发送
        if (status is None and row["sent_at"]) or status == "sent":
            return False

        if status == "running":
            claimed_at = row["claimed_at"]
            stale = True
            if claimed_at:
                try:
                    ts = _dt.strptime(claimed_at, '%Y-%m-%d %H:%M:%S')
                    stale = (now - ts) >= _td(minutes=max(1, stale_after_minutes))
                except ValueError:
                    stale = True

            if not stale:
                return False

            # CAS 更新：只有读取到的 claimed_at 仍未变化时才允许接管，避免并发双抢占。
            if claimed_at is None:
                cur = conn.execute(
                    """
                    UPDATE builtin_report_log
                    SET status='running', claimed_at=?, last_error=NULL
                    WHERE report_type=? AND sent_date=?
                      AND status='running' AND claimed_at IS NULL
                    """,
                    (now_str, report_type, today)
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE builtin_report_log
                    SET status='running', claimed_at=?, last_error=NULL
                    WHERE report_type=? AND sent_date=?
                      AND status='running' AND claimed_at=?
                    """,
                    (now_str, report_type, today, claimed_at)
                )
            return cur.rowcount > 0

        # failed / 其他未知状态，允许重试抢占
        cur = conn.execute(
            """
            UPDATE builtin_report_log
            SET status='running', claimed_at=?, last_error=NULL
            WHERE report_type=? AND sent_date=? AND status!='sent'
            """,
            (now_str, report_type, today)
        )
        return cur.rowcount > 0


def finalize_builtin_report(report_type: str, success: bool, error: str = "") -> None:
    """结束一次内置报告发送流程，更新最终状态。"""
    from datetime import datetime as _dt
    today = _dt.now().strftime('%Y-%m-%d')
    with _conn() as conn:
        if success:
            conn.execute(
                """
                UPDATE builtin_report_log
                SET status='sent', sent_at=datetime('now','localtime'), last_error=NULL
                WHERE report_type=? AND sent_date=?
                """,
                (report_type, today)
            )
        else:
            conn.execute(
                """
                UPDATE builtin_report_log
                SET status='failed', last_error=?
                WHERE report_type=? AND sent_date=?
                """,
                (error[:500], report_type, today)
            )


def mark_builtin_report_sent(report_type: str) -> None:
    """标记今天指定类型的内置报告已发送"""
    finalize_builtin_report(report_type, success=True)
