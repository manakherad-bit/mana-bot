import os
import logging
import json
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import threading
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "9057310870:AAFfuH_q1F7wFmNN4_jumMup2DEB0rp2-lY"

# اتصال به گوگل شیت با استفاده از متغیر محیطی Render
SHEET_NAME = "Mana_Database"  # نام دقیق فایل گوگل شیت شما

def get_gsheet_client():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            logger.error("GOOGLE_CREDENTIALS_JSON not found in environment variables!")
            return None
        
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        logger.error(f"Error connecting to Google Sheets: {e}")
        return None

web_app = Flask(__name__)

@web_app.route('/')
def home():
    client = get_gsheet_client()
    status = "Connected to Google Sheets successfully!" if client else "Failed to connect to Google Sheets!"
    return f"Mana Bot is running successfully! | DB Status: {status}"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_name = update.message.from_user.first_name
    
    # تست ساده اتصال به شیت هنگام دریافت پیام
    client = get_gsheet_client()
    db_status = "متصل به گوگل‌شیت ✅" if client else "خطا در اتصال به گوگل‌شیت ❌"

    response = (
        f"سلام {user_name} عزیز!\n"
        f"پیام شما: '{user_text}'\n"
        f"وضعیت دیتابیس مانا: {db_status}"
    )
    await update.message.reply_text(response)

def main_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    logger.info("Bot started polling...")
    application.run_polling()

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.start()
    main_bot()

