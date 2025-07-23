# userbot_manager.py (FIXED: Premium Emoji Sending Logic)
import asyncio, logging, time, traceback, json, os
from collections import deque
from pyrogram import Client, filters, errors
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType, MessageEntityType
from pyrogram.types import MessageEntity
from telegram import Bot, ParseMode
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.align import Align

import config, database

console = Console()
userbot_statuses = {}
system_logs = deque(maxlen=5)
sending_logs = deque(maxlen=10)

def log_system(message: str):
    timestamp = time.strftime('%H:%M:%S')
    system_logs.append(f"[[dim]{timestamp}[/dim]] {message}")
def log_sending(message: str):
    timestamp = time.strftime('%H:%M:%S')
    sending_logs.append(f"[[dim]{timestamp}[/dim]] {message}")

def create_dashboard_layout() -> Layout:
    layout = Layout()
    layout.split(
        Layout(Panel("📊 DASBOR JASEB REAL-TIME", style="bold blue", padding=(0,1)), name="header", size=3),
        Layout(name="main_body", ratio=1),
        Layout(name="footer", size=8),
    )
    layout["main_body"].split_column(Layout(name="status_table"), Layout(name="live_log", minimum_size=5))
    layout["footer"].update(Panel(Text("\n".join(system_logs), justify="left"), title="📝 LOG SISTEM (5 TERAKHIR)", border_style="yellow"))
    return layout

def render_dashboard() -> Panel:
    userbot_table = Table(border_style="cyan", padding=(0, 1), expand=True)
    userbot_table.add_column("Nama Userbot", style="bold magenta", no_wrap=True)
    userbot_table.add_column("Status", style="bold", width=25)
    userbot_table.add_column("Progress", justify="center")
    userbot_table.add_column("Target ID", style="dim")

    for uid, data in list(userbot_statuses.items()):
        status = data.get("status", "Inisialisasi...")
        status_color = "yellow"; 
        if "Sebar Pesan" in status: status_color = "green"
        elif "Istirahat" in status: status_color = "blue"
        elif "Gagal" in status or "Crash" in status: status_color = "red"
        userbot_table.add_row(data.get("name", str(uid)), f"[{status_color}]{status}[/{status_color}]", data.get("progress", "-"), str(data.get("current_target", "-")))
    
    sending_log_panel = Panel(Text("\n".join(sending_logs), justify="left"), title="📡 LOG PENGIRIMAN REAL-TIME (10 TERAKHIR)", border_style="green")
    layout = create_dashboard_layout()
    layout["status_table"].update(Panel(userbot_table, title="🤖 STATUS USERBOT AKTIF"))
    layout["live_log"].update(sending_log_panel)
    return Panel(layout, style="bold blue")

def send_cycle_start_notification(owner_id, userbot_name):
    try: Bot(token=config.BOT_TOKEN).send_message(owner_id, f"🤖 Userbot *{userbot_name}* Anda akan memulai siklus penyebaran pesan.", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass
def log_to_channel(level, title, message):
    icons = {'SUCCESS': '✅', 'ERROR': '❌', 'WARNING': '⚠️', 'INFO': 'ℹ️', 'SUMMARY': '📊'}; icon = icons.get(level, '⚙️')
    formatted_text = f"{icon} *{level}: {title}*\n\n{message}"
    try: Bot(token=config.BOT_TOKEN).send_message(chat_id=config.LOG_CHANNEL_ID, text=formatted_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e: log_system(f"❌ Gagal mengirim log ke channel: {e}")
async def activate_pending_userbots():
    claimed_bots = database.fetch_and_claim_pending_userbots()
    if not claimed_bots: return
    log_system(f"⚙️ Mengklaim {len(claimed_bots)} userbot baru...")
    for _, owner_id, session_string in claimed_bots:
        try:
            async with Client(":memory:", api_id=config.API_ID, api_hash=config.API_HASH, session_string=session_string) as temp_app:
                ud = await temp_app.get_me(); database.update_userbot_details(session_string, ud.id, ud.first_name)
                log_system(f"✅ Userbot '{ud.first_name}' diaktifkan.")
        except Exception as e:
            database.set_userbot_error(session_string, str(e)); log_system(f"❌ Aktivasi GAGAL untuk owner {owner_id}.")
            log_to_channel('ERROR', 'Aktivasi Userbot Gagal', f"Sesi dari owner `{owner_id}` tidak valid.\n*Error*: `{str(e)}`")
async def promo_handler(client, message):
    userbot_id = client.me.id; promo_config = database.get_jaseb_config(userbot_id)
    if not promo_config or not promo_config.get('promo_status') or not promo_config.get('promo_keywords') or not message.text: return
    keywords = [k.strip().lower() for k in promo_config['promo_keywords'].split(',')]
    if any(keyword in message.text.lower() for keyword in keywords):
        try:
            await message.reply_text(promo_config['promo_message'], quote=True)
            log_system(f"📣 Promo terkirim ke '{message.chat.title}' oleh '{client.me.first_name}'")
        except Exception: pass
async def pm_auto_reply_handler(client, message):
    userbot_id = client.me.id; config = database.get_jaseb_config(userbot_id)
    if config and config.get('pm_reply_status') and config.get('pm_reply_text'):
        try:
            await message.reply_text(config['pm_reply_text'], quote=True)
            log_system(f"💬 Userbot '{client.me.first_name}' membalas PM dari {message.from_user.id}")
        except Exception: pass

async def jaseb_worker(session_string, userbot_id, owner_id, userbot_name):
    app = None; status = userbot_statuses.setdefault(userbot_id, {})
    status.update({"name": userbot_name, "status": "Inisialisasi...", "progress": "-", "current_target": "-"})
    try:
        database.set_worker_status(userbot_id, True)
        app = Client(name=f"userbot_{userbot_id}", session_string=session_string, api_id=config.API_ID, api_hash=config.API_HASH)
        app.add_handler(MessageHandler(promo_handler, filters.group & filters.text & ~filters.me)); app.add_handler(MessageHandler(pm_auto_reply_handler, filters.private & ~filters.me))
        await app.start(); me = await app.get_me(); userbot_name = me.first_name; status["name"] = userbot_name
        status["status"] = "🟢 Online"; log_to_channel('SUCCESS', 'Userbot Online', f"Userbot `{userbot_name}` (`{userbot_id}`) berhasil terhubung."); database.add_jaseb_log(userbot_id, f"✅ Userbot '{userbot_name}' berhasil online.")
        while True:
            if not database.is_user_subscribed(owner_id):
                status["status"] = "⚠️ Langganan Habis"; log_to_channel('WARNING', 'Langganan Berakhir', f"Userbot `{userbot_name}` dihentikan (owner `{owner_id}`).")
                database.add_jaseb_log(userbot_id, "⚠️ Langganan berakhir, userbot dihentikan."); break
            
            jaseb_config = database.get_jaseb_config(userbot_id)
            if not jaseb_config or not jaseb_config.get('running'): status["status"] = "⏹️ Berhenti (Idle)"; await asyncio.sleep(15); continue
            
            send_cycle_start_notification(owner_id, userbot_name)
            delay_per_group = jaseb_config.get('delay', 20); status["status"] = "🔄 Memulai Siklus"; database.add_jaseb_log(userbot_id, "🔄 Memulai siklus penyebaran pesan...")
            all_targets = []; status["status"] = "🎯 Sinkronisasi"
            try:
                async for dialog in app.get_dialogs():
                    if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]: all_targets.append(dialog.chat.id)
            except Exception as e: status["status"] = f"❌ Gagal Sync: {e}"; await asyncio.sleep(60); continue
            
            banned_ids = set(database.get_banned_group_ids(userbot_id)); targets = [tid for tid in all_targets if tid not in banned_ids]
            log_system(f"'{userbot_name}' memulai siklus: {len(targets)} target, skip {len(banned_ids)}.")
            if not targets: status["status"] = "💤 Target Kosong"; await asyncio.sleep(120); continue
            
            sent_count, error_count = 0, 0
            for i, target_id in enumerate(targets):
                status.update({"status": "▶️ Sebar Pesan", "progress": f"{i+1}/{len(targets)}", "current_target": target_id})
                current_config = database.get_jaseb_config(userbot_id)
                if not current_config or not current_config.get('running'): status["status"] = "⏹️ Dihentikan"; log_system(f"Siklus '{userbot_name}' dihentikan pengguna."); break
                try:
                    msg_type, text, file_id, entities_data = current_config['type'], current_config['text'], current_config['file_id'], current_config.get('message_entities')
                    
                    # --- PERBAIKAN LOGIKA PREMIUM EMOJI DI SINI ---
                    entities = []
                    if entities_data:
                        for entity in entities_data:
                            # Mengubah string 'type' kembali menjadi Enum Pyrogram
                            entity['type'] = MessageEntityType[entity['type'].split('.')[-1].upper()]
                            entities.append(MessageEntity(**entity))
                    
                    if msg_type == 'text': await app.send_message(target_id, text, entities=entities)
                    elif msg_type == 'photo': await app.send_photo(target_id, file_id, caption=text, caption_entities=entities)
                    elif msg_type == 'video': await app.send_video(target_id, file_id, caption=text, caption_entities=entities)
                    sent_count += 1
                    log_sending(f"✅ [green]{userbot_name}[/green] -> Sukses kirim ke {target_id}")
                except (errors.ChatWriteForbidden, errors.UserBannedInChannel, errors.ChannelPrivate) as e:
                    error_count += 1; database.add_banned_group(userbot_id, target_id, type(e).__name__)
                    log_sending(f"❌ [red]{userbot_name}[/red] -> Gagal ({type(e).__name__}) di {target_id} -> di-skip")
                except errors.FloodWait as e:
                    status["status"] = f"⏳ Flood Wait ({e.value}s)"; await asyncio.sleep(e.value + 5)
                    log_sending(f"⏳ [yellow]{userbot_name}[/yellow] -> Flood wait {e.value} detik.")
                except Exception as e: 
                    error_count += 1
                    log_sending(f"❌ [red]{userbot_name}[/red] -> Gagal (Error: {e}) di {target_id}")
                await asyncio.sleep(delay_per_group)
            
            status.update({"status": "💤 Istirahat", "progress": f"{sent_count}/{len(targets)} (Selesai)", "current_target": "-"})
            log_to_channel('SUMMARY', f"Siklus Selesai: {userbot_name}", f"✅ Berhasil: *{sent_count}*\n❌ Gagal: *{error_count}*\nTotal Target: *{len(targets)}*")
            database.add_jaseb_log(userbot_id, f"📊 Siklus selesai. Berhasil: {sent_count}, Gagal: {error_count}."); await asyncio.sleep(30)
    except Exception as e:
        status.update({"status": "❌ Crash", "progress": "-", "current_target": "-"})
        log_system(f"❌ Worker '{userbot_name}' CRASHED: {e}")
        log_to_channel('ERROR', 'Worker Userbot Crash', f"Terjadi error fatal pada `{userbot_name}` (`{userbot_id}`).\n*Error*: `{e}`")
    finally:
        if app and app.is_connected: await app.stop()
        database.set_worker_status(userbot_id, False)
        if userbot_id in userbot_statuses: del userbot_statuses[userbot_id]
        log_system(f"🔴 Userbot '{userbot_name}' telah berhenti.")
        log_to_channel('INFO', 'Userbot Offline', f"Userbot `{userbot_name}` (`{userbot_id}`) telah berhenti.")

async def worker_manager():
    active_tasks = {}
    while True:
        try:
            await activate_pending_userbots(); idle_bots = database.get_idle_active_userbots()
            for bot_id, task in list(active_tasks.items()):
                if task.done(): del active_tasks[bot_id]
            for bot_data in idle_bots:
                bot_id = bot_data['userbot_id']
                if bot_id not in active_tasks:
                    log_system(f"🚀 Membuat task untuk userbot '{bot_data['userbot_name']}' ({bot_id}).")
                    active_tasks[bot_id] = asyncio.create_task(jaseb_worker(bot_data['session_string'], bot_id, bot_data['owner_id'], bot_data['userbot_name']))
            await asyncio.sleep(30)
        except Exception as e:
            log_system(f"💥 Error fatal di loop manager: {e}"); await asyncio.sleep(60)

async def main_dashboard():
    database.reset_all_worker_statuses(); log_to_channel('INFO', 'Sistem Dimulai', "Worker manager dan dasbor telah dimulai.")
    manager_task = asyncio.create_task(worker_manager())
    with Live(render_dashboard(), screen=True, redirect_stderr=False, refresh_per_second=2) as live:
        while not manager_task.done():
            live.update(render_dashboard()); await asyncio.sleep(0.5)

if __name__ == "__main__":
    try: asyncio.run(main_dashboard())
    except KeyboardInterrupt: console.print("\n[bold red]Dasbor dihentikan oleh pengguna.[/bold red]")
