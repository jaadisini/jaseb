#!/bin/bash
# start.sh

clear
echo -e "\e[1;32m   🚀 Jaseb System - Professional Edition 🚀\e[0m"
echo "====================================================="
echo ""
echo -e "\e[1;33m[INFO]\e[0m Memastikan semua library sudah terinstall..."
pip install -r requirements.txt
pip install "urllib3<2.0"

echo ""
echo -e "\e[1;32m[START]\e[0m Menjalankan Bot Utama di background..."
# Jalankan bot utama di latar belakang
python3 main_bot.py &
sleep 2

echo -e "\e[1;32m[START]\e[0m Menjalankan Userbot Manager..."
# Jalankan userbot manager di depan agar lognya terlihat
python3 userbot_manager.py
