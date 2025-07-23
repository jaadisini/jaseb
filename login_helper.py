# login_helper.py (FIXED: Sekarang selalu memaksa login baru)
import asyncio
import os
from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, PhoneCodeInvalid, SessionPasswordNeeded, PasswordHashInvalid

# Nama file sesi sementara yang akan dibuat dan dihapus
SESSION_NAME = "login_bantuan"

async def main():
    print("🚀 Skrip Bantuan Login Userbot 🚀")
    
    # --- LOGIKA BARU: Hapus file sesi lama jika ada ---
    if os.path.exists(f"{SESSION_NAME}.session"):
        os.remove(f"{SESSION_NAME}.session")
        print("ℹ️ File sesi lama (.session) ditemukan dan telah dihapus untuk memulai login baru.")
    
    try:
        api_id = int(input("Masukkan API ID Anda: "))
        api_hash = input("Masukkan API Hash Anda: ")

        # Menggunakan nama sesi sementara, bukan ":memory:", untuk kontrol penuh
        async with Client(SESSION_NAME, api_id=api_id, api_hash=api_hash) as app:
            session_string = await app.export_session_string()
            ud = await app.get_me()
            
            print(f"\n✅ Login Berhasil!")
            print(f"  Nama: {ud.first_name}")
            print(f"  User ID: {ud.id}\n")
            print("🔑 SESSION STRING ANDA 👇")
            print("==================================================")
            print(session_string)
            print("==================================================")
            
    except (ValueError, ApiIdInvalid):
        print("\n❌ [ERROR] API ID atau API Hash tidak valid.")
    except (PhoneCodeInvalid, PasswordHashInvalid):
        print("\n❌ [ERROR] Kode OTP atau Password 2FA salah.")
    except Exception as e:
        print(f"\n❌ [ERROR] Terjadi kesalahan: {e}")

if __name__ == "__main__":
    asyncio.run(main())
