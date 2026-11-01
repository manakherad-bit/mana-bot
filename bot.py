import os
import logging
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import threading

# راه‌اندازی لاگ
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "9057310870:AAFfuH_q1F7wFmNN4_jumMup2DEB0rp2-lY"

# یک وب‌سرور بسیار کوچک با Flask برای اینکه رندر راضی شود و پورت را باز نگه دارد
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Mana Bot is running successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# تابع تلگرام
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_name = update.message.from_user.first_name
    response = f"سلام {user_name} عزیز! پیام شما ('{user_text}') در ربات مانا روی سرور ابری دریافت شد. سیستم کاملاً متصل است!"
    await update.message.reply_text(response)

def main_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    logger.info("Bot started polling...")
    application.run_polling()

if __name__ == '__main__':
    # اجرای وب‌سرور در پس‌زمینه برای رندر
    t = threading.Thread(target=run_flask)
    t.start()
    
    # اجرای ربات تلگرام
    main_bot()
