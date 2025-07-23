# main_bot.py (FIXED: Clean Pop-up Notifications)
import logging, random, string, asyncio, threading, time, datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ParseMode, Bot
from telegram.utils.helpers import escape_markdown
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler, CallbackContext)
import config, database
import userbot_manager 

# (Kode dari atas sampai fungsi-fungsi receive... tidak berubah)
# ...
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] - %(message)s', datefmt='%d-%b-%y %H:%M:%S'); logger = logging.getLogger(__name__)
(GET_EXTEND_ID, GET_EXTEND_DURATION, GET_OWNER_ID_FOR_USERBOT, GET_SESSION_STRING, GET_REDEEM_DURATION, GET_BROADCAST_MESSAGE, SELECT_USERBOT_TO_CONFIG, GET_JASEB_MESSAGE, GET_JASEB_DELAY, GET_PROMO_KEYWORDS, GET_PROMO_MESSAGE, GET_PM_REPLY_TEXT, GET_REDEEM_CODE, GET_PROMO_USERBOT_KEYWORDS, GET_PROMO_USERBOT_MESSAGE) = range(15)
def log_to_channel(level, title, message):
    icons = {'SUCCESS': '✅', 'ERROR': '❌', 'WARNING': '⚠️', 'INFO': '👤', 'SUMMARY': '📊'}; icon = icons.get(level, '⚙️')
    formatted_text = f"{icon} *{level}: {title}*\n\n{message}"
    try: Bot(token=config.BOT_TOKEN).send_message(chat_id=config.LOG_CHANNEL_ID, text=formatted_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e: logger.error(f"Gagal kirim log ke channel dari main_bot: {e}")
def send_or_edit(update: Update, text: str, reply_markup: InlineKeyboardMarkup):
    try:
        if update.callback_query: update.callback_query.answer(); update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        elif update.message: update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e: 
        if 'not modified' not in str(e).lower(): logger.warning(f"Gagal mengirim atau edit pesan: {e}")
def start(update: Update, context: CallbackContext) -> int:
    user = update.effective_user
    if user.id in config.ADMIN_IDS: database.add_user(user.id, user.first_name, user.username); show_admin_menu(update, context); return ConversationHandler.END
    if not database.is_user_registered(user.id): show_registration_menu(update, context); return ConversationHandler.END
    database.add_user(user.id, user.first_name, user.username); show_customer_menu(update, context); return ConversationHandler.END
def cancel(update: Update, context: CallbackContext) -> int:
    user_data = context.user_data
    if 'in_promo_menu' in user_data or 'in_pm_reply_menu' in user_data :
        if 'in_promo_menu' in user_data: del user_data['in_promo_menu']
        if 'in_pm_reply_menu' in user_data: del user_data['in_pm_reply_menu']
        show_userbot_settings_menu(update, context)
    elif 'selected_userbot_id' in user_data:
        show_customer_menu(update, context)
    else:
        if update.message: update.message.reply_text('Aksi dibatalkan.')
        start(update, context)
    return ConversationHandler.END
def show_registration_menu(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("✍️ Daftar & Lanjutkan", callback_data='register_now')]]
    text = f"👋 *Selamat Datang di @{context.bot.username}!* \n\nUntuk menggunakan bot, Anda perlu mendaftarkan diri. Proses ini hanya sekali dan data Anda akan aman bersama kami."
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def register_user(update: Update, context: CallbackContext):
    user = update.effective_user; database.add_user(user.id, user.first_name, user.username)
    update.callback_query.answer("✅ Pendaftaran Berhasil!", show_alert=True)
    log_to_channel('INFO', 'Pengguna Baru Mendaftar', f"Pengguna baru telah mendaftar.\n- Nama: {user.first_name}\n- ID: `{user.id}`\n- Username: @{user.username}")
    start(update, context)
def show_admin_menu(update: Update, context: CallbackContext):
    stats = database.get_system_stats()
    text = (f"👑 *Mode Administrator*\n\nSelamat datang, {escape_markdown(update.effective_user.first_name)}! Statistik sistem saat ini:\n\n"
            f"👤 Total Pengguna: `{stats['total_users']}`\n⭐ Pelanggan Aktif: `{stats['active_subscriptions']}`\n🤖 Userbot Aktif: `{stats['active_userbots']}`")
    keyboard = [[InlineKeyboardButton("➕ Tambah Langganan", callback_data='admin_extend_sub'), InlineKeyboardButton("🤖 Tambah Userbot", callback_data='admin_add_userbot')],
                [InlineKeyboardButton("👥 List Pelanggan", callback_data='admin_list_customers')],
                [InlineKeyboardButton("🎁 Buat Kode Redeem", callback_data='admin_redeem'), InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast')],
                [InlineKeyboardButton("⚙️ Atur Promo Default", callback_data='admin_promo')],
                [InlineKeyboardButton("🕶️ Masuk Mode Pelanggan", callback_data='admin_as_customer')]]
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def show_customer_menu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id; context.user_data.clear(); is_subscribed = database.is_user_subscribed(user_id)
    expiry_date_str = database.get_subscription_end_date(user_id); userbots = database.get_userbots_by_owner(user_id)
    status_text = "🟢 *Aktif*" if is_subscribed else "🔴 *Tidak Aktif*"
    text = f"👤 *Dasbor Pelanggan*\n\nStatus Langganan: {status_text}\nBerakhir Pada: `{expiry_date_str}`\n\n"
    if not userbots: text += "Anda belum memiliki userbot."
    else: text += "Silakan pilih userbot untuk dikelola:"
    keyboard = []; userbot_buttons = [InlineKeyboardButton(f"🤖 {escape_markdown(name)}", callback_data=f"select_ubot_{uid}") for uid, name in userbots]
    for i in range(0, len(userbot_buttons), 2): keyboard.append(userbot_buttons[i:i+2])
    keyboard.append([InlineKeyboardButton("🎁 Tukar Kode Redeem", callback_data="redeem_code_start")])
    keyboard.append([InlineKeyboardButton("💳 Info & Bantuan", callback_data='customer_renew_info')])
    if update.effective_user.id in config.ADMIN_IDS: keyboard.append([InlineKeyboardButton("👑 Kembali ke Menu Admin", callback_data='back_to_admin')])
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def show_userbot_settings_menu(update: Update, context: CallbackContext, success_text: str = None):
    query = update.callback_query
    userbot_id = None
    if query and query.data.startswith('select_ubot_'): userbot_id = int(query.data.split('_')[-1]); context.user_data['selected_userbot_id'] = userbot_id
    elif 'selected_userbot_id' in context.user_data: userbot_id = context.user_data['selected_userbot_id']
    if not userbot_id:
        text = "❌ Terjadi kesalahan. Silakan mulai ulang dari /start."
        if query: update.callback_query.edit_message_text(text)
        else: update.message.reply_text(text)
        return
    userbots = database.get_userbots_by_owner(update.effective_user.id); userbot_name = next((name for uid, name in userbots if uid == userbot_id), "N/A")
    config_data = database.get_jaseb_config(userbot_id); is_running = config_data and config_data.get('running', False)
    status_bot = "▶️ *Berjalan*" if is_running else "⏹️ *Berhenti*"; toggle_text = "⏹️ Hentikan Sebar" if is_running else "▶️ Mulai Sebar"
    text = ""
    if success_text: text += f"✅ _{success_text}_\n\n" # Menampilkan notifikasi sukses
    text += f"⚙️ *Panel Kontrol untuk {escape_markdown(userbot_name)}*\n\n`Status Sebar: {status_bot}`"
    keyboard = [[InlineKeyboardButton(toggle_text, callback_data=f"toggle_{userbot_id}")], [InlineKeyboardButton("📝 Atur Pesan Sebar", callback_data=f"set_msg_{userbot_id}")], [InlineKeyboardButton("⏱️ Atur Jeda Sebar", callback_data=f"set_delay_{userbot_id}")], [InlineKeyboardButton("💬 Atur Auto-Reply PM", callback_data=f"pm_reply_menu_{userbot_id}")], [InlineKeyboardButton("📣 Atur Auto-Reply Grup", callback_data=f"promo_menu_{userbot_id}")], [InlineKeyboardButton("📊 Lihat Log Aktivitas", callback_data=f"view_log_{userbot_id}")], [InlineKeyboardButton("⬅️ Kembali ke Daftar Userbot", callback_data="back_to_customer")]]
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def view_jaseb_log(update: Update, context: CallbackContext):
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1]); logs = database.get_latest_jaseb_logs(userbot_id)
    if not logs: text = "Tidak ada aktivitas log yang tercatat untuk userbot ini."
    else:
        text = "📊 *10 Aktivitas Terakhir Userbot:*\n\n"
        for timestamp, log_text in logs: text += f"`{timestamp}`\n_{escape_markdown(log_text)}_\n\n"
    keyboard = [[InlineKeyboardButton("⬅️ Kembali", callback_data=f"select_ubot_{userbot_id}")]]
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def customer_renew_info(update: Update, context: CallbackContext):
    text = "*Bantuan & Informasi*\n\nUntuk perpanjangan, aktivasi, atau jika mengalami kendala, silakan hubungi admin melalui tombol di bawah."
    keyboard = [[InlineKeyboardButton("💬 Hubungi Admin", url=f"tg://user?id={config.ADMIN_IDS[0]}")], [InlineKeyboardButton("⬅️ Kembali", callback_data='back_to_customer')]]
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def list_customers(update: Update, context: CallbackContext):
    customers = database.get_all_subscriptions(); text = "*👥 List Pelanggan Aktif:*\n\n"
    if not customers: text = "Belum ada pelanggan."
    else:
        for cust in customers: text += (f"• Nama: {escape_markdown(cust['first_name'])}\n  ID: `{cust['user_id']}`\n  Jml Bot: {cust['bot_count']}\n  Expire: `{cust['end_date']}`\n\n")
    keyboard = [[InlineKeyboardButton("⬅️ Kembali", callback_data='back_to_admin')]]
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def show_pm_reply_menu(update: Update, context: CallbackContext, success_text: str = None):
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1])
    context.user_data['selected_userbot_id'] = userbot_id; context.user_data['in_pm_reply_menu'] = True
    config = database.get_jaseb_config(userbot_id); status = config.get('pm_reply_status', False) if config else False
    raw_text = config.get('pm_reply_text', '') if config else ''; display_text = escape_markdown(raw_text) if raw_text else '_Belum diatur_'
    status_text = "🟢 *Aktif*" if status else "🔴 *Tidak Aktif*"; toggle_button_text = "🔴 Nonaktifkan" if status else "🟢 Aktifkan"
    menu_text = ""; 
    if success_text: menu_text += f"✅ _{success_text}_\n\n"
    menu_text += (f"💬 *Pengaturan Auto-Reply PM*\n\nStatus Saat Ini: {status_text}\nTeks Balasan Saat Ini:\n`{display_text}`")
    keyboard = [[InlineKeyboardButton(toggle_button_text, callback_data=f"toggle_pm_reply_{userbot_id}")], [InlineKeyboardButton("📝 Ubah Teks Balasan", callback_data=f"set_pm_text_{userbot_id}")], [InlineKeyboardButton("⬅️ Kembali", callback_data=f"select_ubot_{userbot_id}")]]
    send_or_edit(update, menu_text, InlineKeyboardMarkup(keyboard))
def toggle_pm_reply_status(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1]); config = database.get_jaseb_config(userbot_id)
    current_status = config.get('pm_reply_status', False) if config else False; new_status = not current_status
    database.set_pm_reply_status(userbot_id, new_status); 
    query.answer(f"✅ Auto-reply PM {'diaktifkan' if new_status else 'dinonaktifkan'}")
    show_pm_reply_menu(update, context)
def set_pm_reply_text_start(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return ConversationHandler.END
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1]); context.user_data['selected_userbot_id'] = userbot_id
    query.edit_message_text("✍️ Silakan kirim teks baru untuk balasan otomatis PM.\n\nKirim /cancel untuk membatalkan."); return GET_PM_REPLY_TEXT
def receive_pm_reply_text(update: Update, context: CallbackContext):
    userbot_id = context.user_data['selected_userbot_id']; new_text = update.message.text
    database.set_pm_reply_text(userbot_id, new_text)
    show_pm_reply_menu(update, context, success_text="Teks balasan berhasil disimpan!")
    return ConversationHandler.END
def subscription_gate(update: Update, context: CallbackContext, check_query=True) -> bool:
    user_id = update.effective_user.id
    if user_id in config.ADMIN_IDS: return True
    if not database.is_user_subscribed(user_id):
        if check_query and hasattr(update, 'callback_query') and update.callback_query: update.callback_query.answer("❌ Fitur ini hanya untuk pelanggan aktif.", show_alert=True)
        else: update.message.reply_text("❌ Fitur ini hanya untuk pelanggan aktif.")
        return False
    return True
def redeem_code_start(update: Update, context: CallbackContext):
    text = "🎁 *Tukar Kode Redeem*\n\nSilakan masukkan kode redeem Anda:"
    if update.callback_query: update.callback_query.edit_message_text(text)
    else: update.message.reply_text(text)
    return GET_REDEEM_CODE
def receive_redeem_code(update: Update, context: CallbackContext):
    if not subscription_gate(update, context, check_query=False): return ConversationHandler.END
    code = update.message.text; user_id = update.effective_user.id; result = database.redeem_code(code, user_id)
    if isinstance(result, int):
        update.message.reply_text(f"✅ Berhasil! Langganan Anda telah diperpanjang selama *{result} hari*.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Kembali ke Dasbor", callback_data="back_to_customer")]]))
        log_to_channel("SUCCESS", "Kode Redeem Digunakan", f"Pengguna `{user_id}` berhasil menukarkan kode `{code}` senilai *{result} hari*.")
    elif result == "NOT_FOUND": update.message.reply_text("❌ Kode redeem tidak ditemukan.")
    elif result == "ALREADY_USED": update.message.reply_text("❌ Kode redeem ini sudah pernah digunakan.")
    return ConversationHandler.END
def show_promo_userbot_menu(update: Update, context: CallbackContext, success_text: str = None):
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1])
    context.user_data['selected_userbot_id'] = userbot_id; context.user_data['in_promo_menu'] = True
    config = database.get_jaseb_config(userbot_id); status = config.get('promo_status', False) if config else False
    keywords = config.get('promo_keywords', '_Belum diatur_') if config else '_Belum diatur_'; message = config.get('promo_message', '_Belum diatur_') if config else '_Belum diatur_'
    status_text = "🟢 *Aktif*" if status else "🔴 *Tidak Aktif*"; toggle_button_text = "🔴 Nonaktifkan" if status else "🟢 Aktifkan"
    menu_text = "";
    if success_text: menu_text += f"✅ _{success_text}_\n\n"
    menu_text += (f"📣 *Pengaturan Auto-Reply Grup*\n\nStatus: {status_text}\nKata Kunci: `{escape_markdown(str(keywords))}`\nPesan Balasan:\n`{escape_markdown(str(message))}`")
    keyboard = [[InlineKeyboardButton(toggle_button_text, callback_data=f"toggle_promo_{userbot_id}")], [InlineKeyboardButton("✏️ Ubah Kata Kunci", callback_data=f"set_promo_keys_{userbot_id}")], [InlineKeyboardButton("📝 Ubah Pesan Balasan", callback_data=f"set_promo_msg_{userbot_id}")], [InlineKeyboardButton("⬅️ Kembali", callback_data=f"select_ubot_{userbot_id}")]]
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def toggle_userbot_promo_status(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1]); config = database.get_jaseb_config(userbot_id)
    current_status = config.get('promo_status', False) if config else False; new_status = not current_status
    database.set_userbot_promo_config(userbot_id, status=new_status)
    query.answer(f"✅ Auto-reply grup {'diaktifkan' if new_status else 'dinonaktifkan'}")
    show_promo_userbot_menu(update, context)
def set_promo_userbot_keywords_start(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return ConversationHandler.END
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1]); context.user_data['selected_userbot_id'] = userbot_id
    query.edit_message_text("✍️ Kirimkan kata kunci baru, pisahkan dengan koma (contoh: `jaseb,promo,iklan`):"); return GET_PROMO_USERBOT_KEYWORDS
def receive_promo_userbot_keywords(update: Update, context: CallbackContext):
    userbot_id = context.user_data['selected_userbot_id']; keywords = update.message.text
    database.set_userbot_promo_config(userbot_id, keywords=keywords)
    show_promo_userbot_menu(update, context, success_text="Kata kunci berhasil diubah!")
    return ConversationHandler.END
def set_promo_userbot_message_start(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return ConversationHandler.END
    query = update.callback_query; userbot_id = int(query.data.split('_')[-1]); context.user_data['selected_userbot_id'] = userbot_id
    query.edit_message_text("✍️ Kirimkan teks pesan balasan yang baru:"); return GET_PROMO_USERBOT_MESSAGE
def receive_promo_userbot_message(update: Update, context: CallbackContext):
    userbot_id = context.user_data['selected_userbot_id']; message = update.message.text
    database.set_userbot_promo_config(userbot_id, message=message)
    show_promo_userbot_menu(update, context, success_text="Pesan balasan berhasil diubah!")
    return ConversationHandler.END
def receive_jaseb_message(update: Update, context: CallbackContext):
    message, userbot_id = update.message, context.user_data.get('selected_userbot_id'); text, file_id, msg_type, entities = (None, None, None, None)
    if message.text: text, msg_type, entities = message.text, 'text', message.entities
    elif message.photo: text, file_id, msg_type, entities = message.caption, message.photo[-1].file_id, 'photo', message.caption_entities
    elif message.video: text, file_id, msg_type, entities = message.caption, message.video.file_id, 'video', message.caption_entities
    if msg_type and userbot_id:
        database.set_jaseb_message(userbot_id, msg_type, text, file_id, entities)
        show_userbot_settings_menu(update, context, success_text="Pesan sebar berhasil disimpan!")
        return ConversationHandler.END
    else: update.message.reply_text("❌ Gagal menyimpan. Format pesan tidak didukung."); return GET_JASEB_MESSAGE
def noop(update: Update, context: CallbackContext): update.callback_query.answer()
def toggle_jaseb(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return
    userbot_id = int(update.callback_query.data.split('_')[1]); config = database.get_jaseb_config(userbot_id)
    if not config or not config.get('type'): update.callback_query.answer("❌ Set pesan sebar dulu sebelum memulai!", show_alert=True); return
    new_status = database.toggle_jaseb_status(userbot_id); status_text = "dimulai" if new_status else "dihentikan"
    update.callback_query.answer(f"✅ Proses sebar pesan telah {status_text}.", show_alert=True); show_userbot_settings_menu(update, context)
def set_delay_start(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return ConversationHandler.END
    context.user_data['selected_userbot_id'] = int(update.callback_query.data.split('_')[-1]); update.callback_query.edit_message_text("Masukkan jeda antar grup (detik, min. 10):"); return GET_JASEB_DELAY
def get_jaseb_delay(update: Update, context: CallbackContext):
    delay, userbot_id = int(update.message.text), context.user_data['selected_userbot_id']
    if delay < 10: update.message.reply_text("❌ Jeda minimal 10 detik. Coba lagi."); return GET_JASEB_DELAY
    database.set_jaseb_delay(userbot_id, delay)
    show_userbot_settings_menu(update, context, success_text=f"Jeda berhasil diatur ke {delay} detik.")
    return ConversationHandler.END
def set_message_start(update: Update, context: CallbackContext):
    if not subscription_gate(update, context): return ConversationHandler.END
    context.user_data['selected_userbot_id'] = int(update.callback_query.data.split('_')[-1]); update.callback_query.edit_message_text("✍️ Kirim pesan untuk disebar (teks, foto, atau video)."); return GET_JASEB_MESSAGE
def extend_sub_start(update: Update, context: CallbackContext): update.callback_query.answer(); update.callback_query.edit_message_text("Masukkan ID Pelanggan:"); return GET_EXTEND_ID
def get_extend_id(update: Update, context: CallbackContext): context.user_data['extend_id'] = int(update.message.text); update.message.reply_text("Masukkan jumlah durasi (hari):"); return GET_EXTEND_DURATION
def get_extend_duration(update: Update, context: CallbackContext):
    duration = int(update.message.text); customer_id = context.user_data['extend_id']; database.add_subscription(customer_id, duration)
    update.message.reply_text(f"✅ Langganan untuk `{customer_id}` berhasil ditambah `{duration}` hari.")
    log_to_channel('SUCCESS', 'Langganan Diperpanjang', f"Admin `{update.effective_user.id}` telah memperpanjang langganan untuk `{customer_id}` selama *{duration} hari*."); show_admin_menu(update, context); return ConversationHandler.END
def add_userbot_start(update: Update, context: CallbackContext): update.callback_query.answer(); update.callback_query.edit_message_text("*Masukkan ID Pelanggan pemilik userbot:*"); return GET_OWNER_ID_FOR_USERBOT
def get_owner_id_for_userbot(update: Update, context: CallbackContext): context.user_data['owner_id'] = int(update.message.text); update.message.reply_text("✅ OK. Sekarang kirimkan *Session String* dari Pyrogram."); return GET_SESSION_STRING
def get_session_string(update: Update, context: CallbackContext):
    session_str = update.message.text; owner_id = context.user_data.get('owner_id')
    if database.add_userbot_session(owner_id, session_str):
        update.message.reply_text("✅ *Sesi Diterima!*\nUserbot baru akan segera diaktifkan oleh sistem dalam beberapa saat.")
        log_to_channel('INFO', 'Userbot Baru Ditambahkan', f"Admin `{update.effective_user.id}` menambahkan sesi userbot baru untuk owner `{owner_id}`.")
    else: update.message.reply_text("❌ Gagal! Sesi ini sepertinya sudah ada di database.")
    show_admin_menu(update, context); return ConversationHandler.END
def show_promo_menu(update: Update, context: CallbackContext):
    keywords, message = database.get_default_promo_settings()
    text = f"*Pengaturan Promo Default*\n\nPengaturan ini akan diterapkan ke semua userbot baru.\n\nKata Kunci: `{escape_markdown(keywords)}`\nPesan: `{escape_markdown(message)}`"
    keyboard = [[InlineKeyboardButton("✏️ Ubah Kata Kunci", callback_data='promo_set_keywords')], [InlineKeyboardButton("📝 Ubah Pesan", callback_data='promo_set_message')], [InlineKeyboardButton("⬅️ Kembali", callback_data='back_to_admin')]]
    send_or_edit(update, text, InlineKeyboardMarkup(keyboard))
def promo_set_keywords_start(update: Update, context: CallbackContext):
    update.callback_query.edit_message_text("Kirimkan kata kunci default baru, pisahkan dengan koma:"); return GET_PROMO_KEYWORDS
def get_promo_keywords(update: Update, context: CallbackContext):
    database.set_default_promo_settings(keywords=update.message.text); update.message.reply_text("✅ Kata kunci default berhasil diubah."); show_admin_menu(update, context); return ConversationHandler.END
def promo_set_message_start(update: Update, context: CallbackContext):
    update.callback_query.edit_message_text("Kirimkan teks pesan default yang baru:"); return GET_PROMO_MESSAGE
def get_promo_message(update: Update, context: CallbackContext):
    database.set_default_promo_settings(message=update.message.text); update.message.reply_text("✅ Pesan default berhasil diubah."); show_admin_menu(update, context); return ConversationHandler.END
def broadcast_start(update: Update, context: CallbackContext):
    update.callback_query.answer(); update.callback_query.edit_message_text("Kirim pesan untuk di-broadcast (teks/foto/video):"); return GET_BROADCAST_MESSAGE
def receive_broadcast_message(update: Update, context: CallbackContext):
    user_ids = database.get_all_user_ids(); sent_count = 0
    for uid in user_ids:
        try: context.bot.copy_message(uid, update.message.chat_id, update.message.message_id); sent_count += 1; time.sleep(0.1)
        except Exception: pass
    update.message.reply_text(f"📢 Broadcast selesai. Terkirim ke {sent_count}/{len(user_ids)} pengguna."); show_admin_menu(update, context); return ConversationHandler.END
def redeem_start(update: Update, context: CallbackContext):
    update.callback_query.answer(); update.callback_query.edit_message_text("Masukkan nilai durasi kode (hari):"); return GET_REDEEM_DURATION
def get_redeem_duration(update: Update, context: CallbackContext):
    duration = int(update.message.text); code = 'JASEB-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)); database.save_redeem_code(code, duration)
    update.message.reply_text(f"✅ Kode dibuat:\n`{code}`\nNilai: {duration} hari."); show_admin_menu(update, context); return ConversationHandler.END
def run_userbot_manager_in_background():
    logger.info("Starting Userbot Manager thread..."); asyncio.run(userbot_manager.main())
def main():
    updater = Updater(config.BOT_TOKEN, use_context=True); dp = updater.dispatcher
    redeem_conv = ConversationHandler(entry_points=[CallbackQueryHandler(redeem_code_start, pattern='^redeem_code_start$')], states={GET_REDEEM_CODE: [MessageHandler(Filters.text & ~Filters.command, receive_redeem_code)]}, fallbacks=[CommandHandler('cancel', cancel)])
    promo_userbot_conv = ConversationHandler(entry_points=[CallbackQueryHandler(set_promo_userbot_keywords_start, pattern=r'^set_promo_keys_\d+$'), CallbackQueryHandler(set_promo_userbot_message_start, pattern=r'^set_promo_msg_\d+$')], states={GET_PROMO_USERBOT_KEYWORDS: [MessageHandler(Filters.text & ~Filters.command, receive_promo_userbot_keywords)], GET_PROMO_USERBOT_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, receive_promo_userbot_message)]}, fallbacks=[CommandHandler('cancel', cancel)])
    pm_reply_conv = ConversationHandler(entry_points=[CallbackQueryHandler(set_pm_reply_text_start, pattern=r'^set_pm_text_\d+$')], states={GET_PM_REPLY_TEXT: [MessageHandler(Filters.text & ~Filters.command, receive_pm_reply_text)]}, fallbacks=[CommandHandler('cancel', cancel)])
    admin_promo_conv = ConversationHandler(entry_points=[CallbackQueryHandler(promo_set_keywords_start, pattern='^promo_set_keywords$'), CallbackQueryHandler(promo_set_message_start, pattern='^promo_set_message$')], states={GET_PROMO_KEYWORDS: [MessageHandler(Filters.text & ~Filters.command, get_promo_keywords)], GET_PROMO_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, get_promo_message)]}, fallbacks=[CommandHandler('cancel', cancel)])
    conv_handler = ConversationHandler(
        entry_points=[ CallbackQueryHandler(extend_sub_start, pattern='^admin_extend_sub$'), CallbackQueryHandler(add_userbot_start, pattern='^admin_add_userbot$'), CallbackQueryHandler(set_message_start, pattern=r'^set_msg_\d+$'), CallbackQueryHandler(set_delay_start, pattern=r'^set_delay_\d+$'), CallbackQueryHandler(redeem_start, pattern='^admin_redeem$'), CallbackQueryHandler(broadcast_start, pattern='^admin_broadcast$')],
        states={ GET_EXTEND_ID: [MessageHandler(Filters.regex(r'^\d+$'), get_extend_id)], GET_EXTEND_DURATION: [MessageHandler(Filters.regex(r'^\d+$'), get_extend_duration)], GET_OWNER_ID_FOR_USERBOT: [MessageHandler(Filters.regex(r'^\d+$'), get_owner_id_for_userbot)], GET_SESSION_STRING: [MessageHandler(Filters.text & ~Filters.command, get_session_string)], GET_JASEB_MESSAGE: [MessageHandler(Filters.all & ~Filters.command, receive_jaseb_message)], GET_JASEB_DELAY: [MessageHandler(Filters.regex(r'^\d+$'), get_jaseb_delay)], GET_REDEEM_DURATION: [MessageHandler(Filters.regex(r'^\d+$'), get_redeem_duration)], GET_BROADCAST_MESSAGE: [MessageHandler(Filters.all & ~Filters.command, receive_broadcast_message)]},
        fallbacks=[CommandHandler('cancel', cancel)], allow_reentry=True)
    
    dp.add_handler(CommandHandler("start", start)); dp.add_handler(conv_handler); dp.add_handler(pm_reply_conv); dp.add_handler(redeem_conv); dp.add_handler(promo_userbot_conv); dp.add_handler(admin_promo_conv)
    dp.add_handler(CallbackQueryHandler(show_userbot_settings_menu, pattern=r'^select_ubot_\d+$')); dp.add_handler(CallbackQueryHandler(view_jaseb_log, pattern=r'^view_log_\d+$')); dp.add_handler(CallbackQueryHandler(show_promo_userbot_menu, pattern=r'^promo_menu_\d+$')); dp.add_handler(CallbackQueryHandler(toggle_userbot_promo_status, pattern=r'^toggle_promo_\d+$'))
    dp.add_handler(CallbackQueryHandler(show_pm_reply_menu, pattern=r'^pm_reply_menu_\d+$')); dp.add_handler(CallbackQueryHandler(toggle_pm_reply_status, pattern=r'^toggle_pm_reply_\d+$'))
    dp.add_handler(CallbackQueryHandler(list_customers, pattern='^admin_list_customers$')); dp.add_handler(CallbackQueryHandler(lambda u,c: show_customer_menu(u,c), pattern='^admin_as_customer$')); dp.add_handler(CallbackQueryHandler(show_admin_menu, pattern='^back_to_admin$')); dp.add_handler(CallbackQueryHandler(toggle_jaseb, pattern=r'^toggle_\d+$')); dp.add_handler(CallbackQueryHandler(register_user, pattern='^register_now$')); dp.add_handler(CallbackQueryHandler(show_customer_menu, pattern='^back_to_customer$')); dp.add_handler(CallbackQueryHandler(customer_renew_info, pattern='^customer_renew_info$')); dp.add_handler(CallbackQueryHandler(noop, pattern='^noop$'))
    dp.add_handler(CallbackQueryHandler(show_promo_menu, pattern='^admin_promo$'))
    manager_thread = threading.Thread(target=run_userbot_manager_in_background, daemon=True); manager_thread.start()
    updater.start_polling(); logger.info("Bot Utama Telah Aktif dan siap menerima perintah."); updater.idle()
if __name__ == '__main__':
    main()
