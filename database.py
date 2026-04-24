import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from config import DB_PATH

logger = logging.getLogger(__name__)

USERS_PER_PAGE = 8


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
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
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                phone TEXT DEFAULT "",
                tag TEXT,
                join_date DATETIME,
                funnel_stopped INTEGER DEFAULT 0,
                last_warmup_sent INTEGER DEFAULT 0,
                is_paid INTEGER DEFAULT 0,
                paid_date DATETIME,
                last_buy_intent TEXT DEFAULT "",
                webinar_registered INTEGER DEFAULT 0,
                webinar_attended INTEGER DEFAULT 0,
                clicked_buy INTEGER DEFAULT 0,
                click_buy_time DATETIME,
                buy_reminder_1h_sent INTEGER DEFAULT 0,
                buy_reminder_24h_sent INTEGER DEFAULT 0,
                razbor_photo_sent INTEGER DEFAULT 0,
                razbor_auto_replied INTEGER DEFAULT 0,
                razbor_pay_clicked INTEGER DEFAULT 0,
                razbor_pay_click_time DATETIME,
                razbor_paid INTEGER DEFAULT 0,
                razbor_remind_1h_sent INTEGER DEFAULT 0,
                razbor_remind_24h_sent INTEGER DEFAULT 0,
                razbor_remind_step INTEGER DEFAULT 0,
                protocol_paid INTEGER DEFAULT 0,
                protocol_pay_click_time DATETIME,
                protocol_remind_step INTEGER DEFAULT 0,
                vip_clicked INTEGER DEFAULT 0,
                vip_click_time DATETIME,
                vip_paid INTEGER DEFAULT 0,
                vip_remind_1h_sent INTEGER DEFAULT 0,
                vip_remind_24h_sent INTEGER DEFAULT 0,
                post_webinar_active INTEGER DEFAULT 0,
                post_webinar_step INTEGER DEFAULT 0,
                post_webinar_start DATETIME,
                diag_clicked INTEGER DEFAULT 0,
                diag_click_time DATETIME,
                diag_paid INTEGER DEFAULT 0,
                diag_remind_1h_sent INTEGER DEFAULT 0,
                diag_remind_24h_sent INTEGER DEFAULT 0,
                buy_reminder_step INTEGER DEFAULT 0,
                silence_triggered INTEGER DEFAULT 0,
                last_active DATETIME
            );

            CREATE TABLE IF NOT EXISTS webinar_settings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                webinar_date DATETIME,
                webinar_link TEXT,
                broadcast_text TEXT DEFAULT "",
                is_active INTEGER DEFAULT 0,
                reminder_1d_sent INTEGER DEFAULT 0,
                reminder_2h_sent INTEGER DEFAULT 0,
                reminder_15m_sent INTEGER DEFAULT 0,
                admin_msg_id INTEGER DEFAULT 0
            );

            INSERT OR IGNORE INTO webinar_settings (id, is_active) VALUES (1, 0);

            CREATE TABLE IF NOT EXISTS funnel_content (
                id TEXT PRIMARY KEY,
                text TEXT DEFAULT "",
                media_file_id TEXT DEFAULT "",
                media_type TEXT DEFAULT "",
                btn_text TEXT DEFAULT "",
                btn_url TEXT DEFAULT ""
            );

            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ""
            );
        ''')

        _safe_add_columns(conn, "users", [
            ("razbor_remind_step", "INTEGER DEFAULT 0"),
            ("protocol_paid", "INTEGER DEFAULT 0"),
            ("protocol_pay_click_time", "DATETIME"),
            ("protocol_remind_step", "INTEGER DEFAULT 0"),
            ("buy_reminder_step", "INTEGER DEFAULT 0"),
            ("silence_triggered", "INTEGER DEFAULT 0"),
            ("last_active", "DATETIME"),             ("razbor_upsell_7000_step", "INTEGER DEFAULT 0"),
        ])

        conn.execute(
            "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
            ("razbor_template", "Я посмотрел ваше фото 🔍\n\nУже вижу ключевые причины изменений на лице.\n\nХорошая новость — это можно скорректировать достаточно быстро.\n\n💎 Я могу сделать для вас:\n— персональный видеоразбор\n— точечный протокол\n— покажу, что делать именно вам\n\nСтоимость — 3 000 ₽\n\n👇 Нажмите кнопку, чтобы получить разбор:")
        )

    logger.info("Database initialised.")


def _safe_add_columns(conn, table: str, columns: list):
    for col, definition in columns:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  ПОЛЬЗОВАТЕЛИ
# ══════════════════════════════════════════════════════════════
def upsert_user(tg_id: int, tag: str, username: str = None, full_name: str = None):
    with get_conn() as conn:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO users (tg_id, username, full_name, tag, join_date, funnel_stopped, last_warmup_sent)
            VALUES (?, ?, ?, ?, ?, 0, 0)
            ON CONFLICT(tg_id) DO UPDATE SET
                tag = excluded.tag,
                username = COALESCE(excluded.username, users.username),
                full_name = COALESCE(excluded.full_name, users.full_name),
                funnel_stopped = 0
        ''', (tg_id, username, full_name, tag, now))


def get_user(tg_id: int):
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE tg_id = ?', (tg_id,)).fetchone()


def get_user_by_phone(phone: str):
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE phone LIKE ?', (f'%{phone}%',)).fetchone()


def update_phone(tg_id: int, phone: str):
    with get_conn() as conn:
        conn.execute('UPDATE users SET phone = ? WHERE tg_id = ?', (phone, tg_id))


def get_all_users():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users ORDER BY id DESC').fetchall()


def get_users_by_tag(tag: str):
    """Получить пользователей по тегу ветки"""
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE tag = ? ORDER BY id DESC', (tag,)).fetchall()


def get_users_page(offset: int):
    with get_conn() as conn:
        total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        rows = conn.execute(
            'SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?',
            (USERS_PER_PAGE, offset)
        ).fetchall()
    return rows, total


def get_users_for_reminders():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE funnel_stopped = 0').fetchall()


def set_reminder_step(tg_id: int, field: str, step: int):
    with get_conn() as conn:
        conn.execute(f'UPDATE users SET {field} = ? WHERE tg_id = ?', (step, tg_id))


# ══════════════════════════════════════════════════════════════
#  РАЗБОР (3000 ₽)
# ══════════════════════════════════════════════════════════════
def mark_razbor_photo_sent(tg_id: int):
    with get_conn() as conn:
        conn.execute('UPDATE users SET razbor_photo_sent = 1 WHERE tg_id = ?', (tg_id,))


def mark_razbor_auto_replied(tg_id: int):
    with get_conn() as conn:
        conn.execute('UPDATE users SET razbor_auto_replied = 1 WHERE tg_id = ?', (tg_id,))


def mark_razbor_pay_clicked(tg_id: int) -> bool:
    with get_conn() as conn:
        u = conn.execute('SELECT razbor_pay_clicked FROM users WHERE tg_id = ?', (tg_id,)).fetchone()
        if u and not u['razbor_pay_clicked']:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                'UPDATE users SET razbor_pay_clicked = 1, razbor_pay_click_time = ? WHERE tg_id = ?',
                (now, tg_id)
            )
            return True
    return False


def mark_razbor_paid(tg_id: int):
    with get_conn() as conn:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE users SET razbor_paid = 1, paid_date = ? WHERE tg_id = ?', (now, tg_id))


def get_razbor_reminder_candidates():
    with get_conn() as conn:
        return conn.execute('''
            SELECT * FROM users
            WHERE razbor_pay_clicked = 1 AND razbor_paid = 0 AND funnel_stopped = 0
        ''').fetchall()


def set_razbor_reminder_sent(tg_id: int, kind: str):
    col = f"razbor_remind_{kind}_sent"
    with get_conn() as conn:
        conn.execute(f'UPDATE users SET {col} = 1 WHERE tg_id = ?', (tg_id,))


# ══════════════════════════════════════════════════════════════
#  МИНИ-ПРОТОКОЛ (7000 ₽)
# ══════════════════════════════════════════════════════════════
def mark_protocol_pay_click(tg_id: int):
    with get_conn() as conn:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE users SET protocol_pay_click_time = ? WHERE tg_id = ?', (now, tg_id))


def mark_protocol_paid(tg_id: int):
    with get_conn() as conn:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE users SET protocol_paid = 1, paid_date = ? WHERE tg_id = ?', (now, tg_id))


# ══════════════════════════════════════════════════════════════
#  КУРС (49000 ₽)
# ══════════════════════════════════════════════════════════════
def mark_buy_click(tg_id: int) -> bool:
    with get_conn() as conn:
        user = conn.execute('SELECT clicked_buy FROM users WHERE tg_id = ?', (tg_id,)).fetchone()
        if user and not user['clicked_buy']:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('UPDATE users SET clicked_buy = 1, click_buy_time = ? WHERE tg_id = ?', (now, tg_id))
            return True
    return False


def get_buy_reminder_candidates():
    with get_conn() as conn:
        return conn.execute('''
            SELECT * FROM users
            WHERE clicked_buy = 1 AND is_paid = 0 AND funnel_stopped = 0
        ''').fetchall()


def set_buy_reminder_sent(tg_id: int, kind: str):
    col = f"buy_reminder_{kind}_sent"
    with get_conn() as conn:
        conn.execute(f'UPDATE users SET {col} = 1 WHERE tg_id = ?', (tg_id,))


def mark_paid(tg_id: int):
    with get_conn() as conn:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE users SET is_paid = 1, paid_date = ?, funnel_stopped = 1 WHERE tg_id = ?', (now, tg_id))


def set_last_buy_intent(tg_id: int, intent: str):
    with get_conn() as conn:
        conn.execute('UPDATE users SET last_buy_intent = ? WHERE tg_id = ?', (intent, tg_id))


# ══════════════════════════════════════════════════════════════
#  VIP
# ══════════════════════════════════════════════════════════════
def mark_vip_clicked(tg_id: int) -> bool:
    with get_conn() as conn:
        u = conn.execute('SELECT vip_clicked FROM users WHERE tg_id = ?', (tg_id,)).fetchone()
        if u and not u['vip_clicked']:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                'UPDATE users SET vip_clicked = 1, vip_click_time = ? WHERE tg_id = ?',
                (now, tg_id)
            )
            return True
    return False


def get_vip_reminder_candidates():
    with get_conn() as conn:
        return conn.execute('''
            SELECT * FROM users
            WHERE vip_clicked = 1 AND vip_paid = 0 AND funnel_stopped = 0
        ''').fetchall()


def set_vip_reminder_sent(tg_id: int, kind: str):
    col = f"vip_remind_{kind}_sent"
    with get_conn() as conn:
        conn.execute(f'UPDATE users SET {col} = 1 WHERE tg_id = ?', (tg_id,))


# ══════════════════════════════════════════════════════════════
#  ДИАГНОСТИКА
# ══════════════════════════════════════════════════════════════
def mark_diag_clicked(tg_id: int):
    with get_conn() as conn:
        u = conn.execute('SELECT diag_clicked FROM users WHERE tg_id = ?', (tg_id,)).fetchone()
        if u and not u['diag_clicked']:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('UPDATE users SET diag_clicked = 1, diag_click_time = ? WHERE tg_id = ?', (now, tg_id))


def mark_diag_paid(tg_id: int):
    with get_conn() as conn:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE users SET diag_paid = 1, paid_date = ? WHERE tg_id = ?', (now, tg_id))


def get_diag_reminders():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE diag_clicked = 1 AND diag_paid = 0 AND funnel_stopped = 0').fetchall()


def set_diag_remind_sent(tg_id: int, kind: str):
    with get_conn() as conn:
        conn.execute(f'UPDATE users SET diag_remind_{kind}_sent = 1 WHERE tg_id = ?', (tg_id,))


# ══════════════════════════════════════════════════════════════
#  ВЕБИНАР
# ══════════════════════════════════════════════════════════════
def mark_webinar_registered(tg_id: int):
    with get_conn() as conn:
        conn.execute('UPDATE users SET webinar_registered = 1 WHERE tg_id = ?', (tg_id,))


def mark_webinar_attended(tg_id: int):
    with get_conn() as conn:
        conn.execute('UPDATE users SET webinar_attended = 1 WHERE tg_id = ?', (tg_id,))


def start_post_webinar(tg_id: int):
    with get_conn() as conn:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE users SET post_webinar_active = 1, post_webinar_step = 0, post_webinar_start = ? WHERE tg_id = ?', (now, tg_id))


def increment_post_webinar_step(tg_id: int):
    with get_conn() as conn:
        conn.execute('UPDATE users SET post_webinar_step = post_webinar_step + 1 WHERE tg_id = ?', (tg_id,))


def get_webinar_registered():
    with get_conn() as conn:
        return conn.execute(
            'SELECT * FROM users WHERE webinar_registered = 1 OR tag = "webinar_reg" ORDER BY id DESC'
        ).fetchall()


def get_post_webinar_users():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE is_paid = 0 AND post_webinar_active = 1 AND funnel_stopped = 0').fetchall()


def get_warmup_users():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM users WHERE is_paid = 0 AND funnel_stopped = 0 AND tag IN ("отёки","подтяжка","обучение")').fetchall()


def set_last_warmup_sent(tg_id: int, day: int):
    with get_conn() as conn:
        conn.execute('UPDATE users SET last_warmup_sent = ? WHERE tg_id = ?', (day, tg_id))


# ══════════════════════════════════════════════════════════════
#  ВЕБИНАР SETTINGS
# ══════════════════════════════════════════════════════════════
def get_webinar():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM webinar_settings WHERE id = 1').fetchone()


def update_webinar(webinar_date: str, webinar_link: str, broadcast_text: str = ""):
    with get_conn() as conn:
        conn.execute('''
            UPDATE webinar_settings
            SET webinar_date = ?, webinar_link = ?, broadcast_text = ?,
                is_active = 1, reminder_1d_sent = 0, reminder_2h_sent = 0, reminder_15m_sent = 0
            WHERE id = 1
        ''', (webinar_date, webinar_link, broadcast_text))


def set_webinar_reminder_sent(kind: str):
    with get_conn() as conn:
        conn.execute(f'UPDATE webinar_settings SET reminder_{kind}_sent = 1 WHERE id = 1')


def deactivate_webinar():
    with get_conn() as conn:
        conn.execute('UPDATE webinar_settings SET is_active = 0 WHERE id = 1')


def get_admin_msg_id():
    with get_conn() as conn:
        row = conn.execute('SELECT admin_msg_id FROM webinar_settings WHERE id = 1').fetchone()
        return row['admin_msg_id'] if row else 0


def set_admin_msg_id(msg_id: int):
    with get_conn() as conn:
        conn.execute('UPDATE webinar_settings SET admin_msg_id = ? WHERE id = 1', (msg_id,))


def set_webinar(webinar_date: str, webinar_link: str):
    with get_conn() as conn:
        conn.execute('''
            UPDATE webinar_settings
            SET webinar_date = ?, webinar_link = ?, is_active = 1,
                reminder_1d_sent = 0, reminder_2h_sent = 0, reminder_15m_sent = 0
            WHERE id = 1
        ''', (webinar_date, webinar_link))


def reset_webinar_registrations():
    with get_conn() as conn:
        conn.execute('UPDATE users SET webinar_registered = 0, webinar_attended = 0')


# ══════════════════════════════════════════════════════════════
#  СТАТИСТИКА
# ══════════════════════════════════════════════════════════════
def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        paid = conn.execute('SELECT COUNT(*) FROM users WHERE is_paid = 1').fetchone()[0]
        web_reg = conn.execute('SELECT COUNT(*) FROM users WHERE webinar_registered = 1').fetchone()[0]
        web_att = conn.execute('SELECT COUNT(*) FROM users WHERE webinar_attended = 1').fetchone()[0]
        clicked_buy = conn.execute('SELECT COUNT(*) FROM users WHERE clicked_buy = 1').fetchone()[0]
        razbor_paid = conn.execute('SELECT COUNT(*) FROM users WHERE razbor_paid = 1').fetchone()[0]
        protocol_paid = conn.execute('SELECT COUNT(*) FROM users WHERE protocol_paid = 1').fetchone()[0]
        vip_paid = conn.execute('SELECT COUNT(*) FROM users WHERE vip_paid = 1').fetchone()[0]
        diag_paid = conn.execute('SELECT COUNT(*) FROM users WHERE diag_paid = 1').fetchone()[0]
        by_tag = {row['tag']: row['cnt'] for row in conn.execute('SELECT tag, COUNT(*) as cnt FROM users GROUP BY tag').fetchall()}
    return dict(total=total, paid=paid, webinar_registered=web_reg, webinar_attended=web_att,
                clicked_buy=clicked_buy, razbor_paid=razbor_paid, protocol_paid=protocol_paid,
                vip_paid=vip_paid, diag_paid=diag_paid, by_tag=by_tag)


# ══════════════════════════════════════════════════════════════
#  МОЛЧУНЫ (72Ч)
# ══════════════════════════════════════════════════════════════
def get_silent_72h_users():
    """Пользователи, которые зарегистрировались 72+ ч назад, ничего не купили и ещё не получали триггер."""
    with get_conn() as conn:
        return conn.execute('''
            SELECT * FROM users
            WHERE silence_triggered = 0
              AND funnel_stopped = 0
              AND is_paid = 0
              AND razbor_paid = 0
              AND protocol_paid = 0
              AND vip_paid = 0
              AND join_date IS NOT NULL
              AND join_date < datetime('now', '-72 hours')
        ''').fetchall()


def mark_silence_triggered(tg_id: int):
    with get_conn() as conn:
        conn.execute('UPDATE users SET silence_triggered = 1 WHERE tg_id = ?', (tg_id,))


# ══════════════════════════════════════════════════════════════
#  КОНТЕНТ ВОРОНКИ
# ══════════════════════════════════════════════════════════════
def get_funnel_content(tag: str, day: int):
    with get_conn() as conn:
        return conn.execute('SELECT * FROM funnel_content WHERE id = ?', (f"{tag}_{day}",)).fetchone()


def set_funnel_content(tag: str, day: int, text: str, media_file_id: str = "", media_type: str = "", btn_text: str = "", btn_url: str = ""):
    with get_conn() as conn:
        conn.execute('''
            INSERT INTO funnel_content (id, text, media_file_id, media_type, btn_text, btn_url)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                text = excluded.text,
                media_file_id = excluded.media_file_id,
                media_type = excluded.media_type,
                btn_text = excluded.btn_text,
                btn_url = excluded.btn_url
        ''', (f"{tag}_{day}", text, media_file_id, media_type, btn_text, btn_url))


# ══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════
def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute('SELECT value FROM bot_settings WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute('INSERT INTO bot_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, value))


def clear_all_data():
    with get_conn() as conn:
        conn.execute('DROP TABLE IF EXISTS users')
        conn.execute('DROP TABLE IF EXISTS webinar_settings')
        conn.execute('DROP TABLE IF EXISTS funnel_content')
        conn.execute('DROP TABLE IF EXISTS bot_settings')
    init_db()

# ══════════════════════════════════════════════════════════════
#  МЕДИА FILE_ID (авто-загрузка из папки media/)
# ══════════════════════════════════════════════════════════════
def init_media_table():
    with get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS media_file_ids (
                filename TEXT PRIMARY KEY,
                file_id  TEXT NOT NULL,
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')


def get_media_file_id(filename: str) -> str:
    """Вернуть сохранённый file_id по имени файла. Пустая строка если нет."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                'SELECT file_id FROM media_file_ids WHERE filename = ?', (filename,)
            ).fetchone()
            return row['file_id'] if row else ""
    except Exception:
        return ""


def set_media_file_id(filename: str, file_id: str):
    """Сохранить или обновить file_id для файла."""
    with get_conn() as conn:
        conn.execute('''
            INSERT INTO media_file_ids (filename, file_id)
            VALUES (?, ?)
            ON CONFLICT(filename) DO UPDATE SET file_id = excluded.file_id,
                                                uploaded_at = CURRENT_TIMESTAMP
        ''', (filename, file_id))

def stop_all_reminders_for_product(tg_id: int, product_prefix: str):
    """
    Пример: product_prefix = 'razbor' обнулит дожимы по разбору, 
    чтобы они не мешали дожимам по курсу.
    """
    with get_conn() as conn:
        conn.execute(f'UPDATE users SET {product_prefix}_remind_step = 10 WHERE tg_id = ?', (tg_id,))