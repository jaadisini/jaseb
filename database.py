# database.py (FIXED: Rewritten with Thread-Safe Connections)
import sqlite3, datetime, json, threading

DB_NAME = 'jaseb_system.db'
# Membuat objek thread-local untuk menyimpan koneksi database per-thread
thread_local = threading.local()

def get_db_connection():
    """Membuat atau mengambil koneksi database yang sudah ada untuk thread saat ini."""
    if not hasattr(thread_local, "conn"):
        thread_local.conn = sqlite3.connect(DB_NAME, timeout=20, check_same_thread=False)
        thread_local.conn.row_factory = sqlite3.Row
    return thread_local.conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, join_date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS subscriptions (user_id INTEGER PRIMARY KEY, end_date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS userbots (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, session_string TEXT UNIQUE, userbot_id INTEGER UNIQUE, userbot_name TEXT, status TEXT DEFAULT "pending", is_running_worker BOOLEAN DEFAULT 0)')
    try: cursor.execute('ALTER TABLE userbots ADD COLUMN is_running_worker BOOLEAN DEFAULT 0')
    except sqlite3.OperationalError: pass
    cursor.execute('CREATE TABLE IF NOT EXISTS jaseb_config (userbot_id INTEGER PRIMARY KEY, message_type TEXT, message_text TEXT, message_file_id TEXT, is_running BOOLEAN DEFAULT 0, delay_per_group INTEGER DEFAULT 20, pm_reply_status BOOLEAN DEFAULT 0, pm_reply_text TEXT, promo_status BOOLEAN DEFAULT 0, promo_keywords TEXT, promo_message TEXT, message_entities TEXT)')
    try:
        cursor.execute('ALTER TABLE jaseb_config ADD COLUMN pm_reply_status BOOLEAN DEFAULT 0'); cursor.execute('ALTER TABLE jaseb_config ADD COLUMN pm_reply_text TEXT')
        cursor.execute('ALTER TABLE jaseb_config ADD COLUMN promo_status BOOLEAN DEFAULT 0'); cursor.execute('ALTER TABLE jaseb_config ADD COLUMN promo_keywords TEXT')
        cursor.execute('ALTER TABLE jaseb_config ADD COLUMN promo_message TEXT'); cursor.execute('ALTER TABLE jaseb_config ADD COLUMN message_entities TEXT')
    except sqlite3.OperationalError: pass
    cursor.execute('CREATE TABLE IF NOT EXISTS banned_groups (userbot_id INTEGER, chat_id INTEGER, reason TEXT, banned_until TEXT, PRIMARY KEY (userbot_id, chat_id))')
    try: cursor.execute('ALTER TABLE banned_groups ADD COLUMN banned_until TEXT')
    except sqlite3.OperationalError: pass
    cursor.execute('CREATE TABLE IF NOT EXISTS redeem_codes (code TEXT PRIMARY KEY, duration_days INTEGER, is_used BOOLEAN DEFAULT 0, used_by INTEGER, used_date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS promo_settings (id INTEGER PRIMARY KEY DEFAULT 1, keywords TEXT DEFAULT "jaseb,sebar", message TEXT DEFAULT "Butuh Jasa Sebar Profesional? Hubungi kami!")')
    cursor.execute('CREATE TABLE IF NOT EXISTS jaseb_logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, userbot_id INTEGER, timestamp TEXT, log_text TEXT)')
    conn.commit()
    print("[DB] Database siap digunakan.")

# --- SEMUA FUNGSI DIBAWAH INI SEKARANG MENGGUNAKAN get_db_connection() ---

def count_running_workers():
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT COUNT(*) FROM userbots WHERE status = 'active' AND is_running_worker = 1"); return c.fetchone()[0]
def add_banned_group(userbot_id, chat_id, reason, ban_duration_hours=1):
    conn = get_db_connection(); c = conn.cursor()
    banned_until = (datetime.datetime.now() + datetime.timedelta(hours=ban_duration_hours)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR REPLACE INTO banned_groups (userbot_id, chat_id, reason, banned_until) VALUES (?, ?, ?, ?)", (userbot_id, chat_id, reason, banned_until)); conn.commit()
def get_banned_group_ids(userbot_id):
    conn = get_db_connection(); c = conn.cursor(); now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("SELECT chat_id FROM banned_groups WHERE userbot_id = ? AND banned_until > ?", (userbot_id, now)); return [row['chat_id'] for row in c.fetchall()]
def redeem_code(code, user_id):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT duration_days, is_used FROM redeem_codes WHERE code = ?", (code,)); result = c.fetchone()
    if not result: return "NOT_FOUND"
    duration, is_used = result['duration_days'], result['is_used']
    if is_used: return "ALREADY_USED"
    add_subscription(user_id, duration)
    c.execute("UPDATE redeem_codes SET is_used = 1, used_by = ?, used_date = ? WHERE code = ?", (user_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), code)); conn.commit()
    return duration
def set_jaseb_message(userbot_id, message_type, text=None, file_id=None, entities=None):
    conn = get_db_connection(); c = conn.cursor()
    entities_json = json.dumps([e.to_dict() for e in entities]) if entities else None
    c.execute("INSERT INTO jaseb_config (userbot_id, message_type, message_text, message_file_id, message_entities) VALUES (?, ?, ?, ?, ?) ON CONFLICT(userbot_id) DO UPDATE SET message_type=excluded.message_type, message_text=excluded.message_text, message_file_id=excluded.message_file_id, message_entities=excluded.message_entities", (userbot_id, message_type, text, file_id, entities_json)); conn.commit()
def set_userbot_promo_config(userbot_id, status=None, keywords=None, message=None):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO jaseb_config (userbot_id) VALUES (?)", (userbot_id,))
    if status is not None: c.execute("UPDATE jaseb_config SET promo_status = ? WHERE userbot_id = ?", (int(status), userbot_id))
    if keywords is not None: c.execute("UPDATE jaseb_config SET promo_keywords = ? WHERE userbot_id = ?", (keywords, userbot_id))
    if message is not None: c.execute("UPDATE jaseb_config SET promo_message = ? WHERE userbot_id = ?", (message, userbot_id))
    conn.commit()
def get_jaseb_config(userbot_id):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT * FROM jaseb_config WHERE userbot_id = ?", (userbot_id,)); result = c.fetchone()
    if result:
        entities_json = result['message_entities']; entities = json.loads(entities_json) if entities_json else None
        return {'type': result['message_type'], 'text': result['message_text'], 'file_id': result['message_file_id'], 'running': bool(result['is_running']), 'delay': result['delay_per_group'], 'pm_reply_status': bool(result['pm_reply_status']), 'pm_reply_text': result['pm_reply_text'], 'promo_status': bool(result['promo_status']), 'promo_keywords': result['promo_keywords'], 'promo_message': result['promo_message'], 'message_entities': entities}
    return None
def add_jaseb_log(userbot_id, log_text):
    conn = get_db_connection(); c = conn.cursor(); timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO jaseb_logs (userbot_id, timestamp, log_text) VALUES (?, ?, ?)", (userbot_id, timestamp, log_text)); conn.commit()
def get_latest_jaseb_logs(userbot_id, limit=10):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT timestamp, log_text FROM jaseb_logs WHERE userbot_id = ? ORDER BY log_id DESC LIMIT ?", (userbot_id, limit)); return c.fetchall()
def set_worker_status(userbot_id, status: bool):
    conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE userbots SET is_running_worker = ? WHERE userbot_id = ?", (int(status), userbot_id)); conn.commit()
def reset_all_worker_statuses():
    conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE userbots SET is_running_worker = 0"); conn.commit(); print("[DB] Semua status worker telah direset.")
def get_idle_active_userbots():
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT session_string, userbot_id, owner_id, userbot_name FROM userbots WHERE status = 'active' AND is_running_worker = 0"); return c.fetchall()
def get_system_stats():
    conn = get_db_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total_users = c.fetchone()['COUNT(*)']
    c.execute("SELECT COUNT(*) FROM subscriptions WHERE end_date > ?", (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)); active_subscriptions = c.fetchone()['COUNT(*)']
    c.execute("SELECT COUNT(*) FROM userbots WHERE status = 'active'"); active_userbots = c.fetchone()['COUNT(*)']
    return {'total_users': total_users, 'active_subscriptions': active_subscriptions, 'active_userbots': active_userbots}
def fetch_and_claim_pending_userbots():
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT id, owner_id, session_string FROM userbots WHERE status = 'pending'"); pending_bots = c.fetchall()
    if not pending_bots: return []
    pending_ids = [bot['id'] for bot in pending_bots]; placeholders = ','.join('?' for _ in pending_ids)
    c.execute(f"UPDATE userbots SET status = 'activating' WHERE id IN ({placeholders})", pending_ids); conn.commit()
    return pending_bots
def set_pm_reply_status(userbot_id, status: bool):
    conn = get_db_connection(); c = conn.cursor(); c.execute("INSERT OR IGNORE INTO jaseb_config (userbot_id) VALUES (?)", (userbot_id,)); c.execute("UPDATE jaseb_config SET pm_reply_status = ? WHERE userbot_id = ?", (int(status), userbot_id)); conn.commit()
def set_pm_reply_text(userbot_id, text: str):
    conn = get_db_connection(); c = conn.cursor(); c.execute("INSERT OR IGNORE INTO jaseb_config (userbot_id) VALUES (?)", (userbot_id,)); c.execute("UPDATE jaseb_config SET pm_reply_text = ? WHERE userbot_id = ?", (text, userbot_id)); conn.commit()
def add_user(user_id, first_name, username):
    conn = get_db_connection(); c = conn.cursor(); c.execute("INSERT OR IGNORE INTO users (user_id, first_name, username, join_date) VALUES (?, ?, ?, ?)", (user_id, first_name, username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))); conn.commit()
def is_user_registered(user_id):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)); return c.fetchone() is not None
def add_subscription(user_id, duration_days):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,)); result = c.fetchone()
    base_date = datetime.datetime.now()
    if result and datetime.datetime.strptime(result['end_date'], "%Y-%m-%d %H:%M:%S") > base_date: base_date = datetime.datetime.strptime(result['end_date'], "%Y-%m-%d %H:%M:%S")
    end_date = base_date + datetime.timedelta(days=duration_days); c.execute("INSERT OR REPLACE INTO subscriptions (user_id, end_date) VALUES (?, ?)", (user_id, end_date.strftime("%Y-%m-%d %H:%M:%S"))); conn.commit()
def get_all_subscriptions():
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT s.user_id, u.first_name, u.join_date, s.end_date, (SELECT COUNT(*) FROM userbots WHERE owner_id=s.user_id AND status='active') as bot_count FROM subscriptions s JOIN users u ON s.user_id = u.user_id ORDER BY s.end_date DESC"); return c.fetchall()
def save_redeem_code(code, duration_days):
    conn = get_db_connection(); c = conn.cursor(); c.execute("INSERT OR IGNORE INTO redeem_codes (code, duration_days) VALUES (?, ?)", (code, duration_days)); conn.commit()
def get_all_user_ids():
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT user_id FROM users"); return [row['user_id'] for row in c.fetchall()]
def add_userbot_session(owner_id, session_string):
    conn = get_db_connection(); c = conn.cursor()
    try: c.execute("INSERT INTO userbots (owner_id, session_string) VALUES (?, ?)", (owner_id, session_string)); conn.commit(); return True
    except sqlite3.IntegrityError: return False
def update_userbot_details(session_string, userbot_id, userbot_name):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("UPDATE userbots SET userbot_id = ?, userbot_name = ?, status = 'active' WHERE session_string = ?", (userbot_id, userbot_name, session_string))
    promo_keywords, promo_message = get_default_promo_settings()
    c.execute("INSERT OR IGNORE INTO jaseb_config (userbot_id, promo_keywords, promo_message, promo_status) VALUES (?, ?, ?, 1)", (userbot_id, promo_keywords, promo_message))
    conn.commit()
def set_userbot_error(session_string, error_message):
    conn = get_db_connection(); c = conn.cursor(); c.execute("UPDATE userbots SET status = ? WHERE session_string = ?", (f"error: {error_message[:100]}", session_string)); conn.commit()
def is_user_subscribed(user_id):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,)); result = c.fetchone()
    if result: return datetime.datetime.now() < datetime.datetime.strptime(result['end_date'], "%Y-%m-%d %H:%M:%S")
    return False
def get_userbots_by_owner(owner_id):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT userbot_id, userbot_name FROM userbots WHERE owner_id = ? AND status = 'active'", (owner_id,)); return c.fetchall()
def set_jaseb_delay(userbot_id, delay_seconds):
    conn = get_db_connection(); c = conn.cursor(); c.execute("INSERT INTO jaseb_config (userbot_id, delay_per_group) VALUES (?, ?) ON CONFLICT(userbot_id) DO UPDATE SET delay_per_group=excluded.delay_per_group", (userbot_id, delay_seconds)); conn.commit()
def get_subscription_end_date(user_id):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT end_date FROM subscriptions WHERE user_id = ?", (user_id,)); result = c.fetchone()
    return result['end_date'] if result else "Tidak Terdaftar"
def toggle_jaseb_status(userbot_id):
    conn = get_db_connection(); c = conn.cursor(); c.execute("SELECT is_running FROM jaseb_config WHERE userbot_id = ?", (userbot_id,)); result = c.fetchone()
    if result is None: c.execute("INSERT OR IGNORE INTO jaseb_config (userbot_id) VALUES (?)", (userbot_id,)); result = {'is_running': 0}
    new_status = not bool(result['is_running']); c.execute("UPDATE jaseb_config SET is_running = ? WHERE userbot_id = ?", (int(new_status), userbot_id)); conn.commit()
    return new_status
def get_default_promo_settings():
    conn = get_db_connection(); c = conn.cursor(); c.execute("INSERT OR IGNORE INTO promo_settings (id) VALUES (1)"); conn.commit()
    c.execute("SELECT keywords, message FROM promo_settings WHERE id = 1"); result = c.fetchone()
    return (result['keywords'], result['message']) if result else ("", "")
def set_default_promo_settings(keywords=None, message=None):
    conn = get_db_connection(); c = conn.cursor()
    if keywords is not None: c.execute("UPDATE promo_settings SET keywords = ? WHERE id = 1", (keywords,))
    if message is not None: c.execute("UPDATE promo_settings SET message = ? WHERE id = 1", (message,))
    conn.commit()

init_db()
