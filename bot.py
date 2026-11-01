import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# تنظیمات لاگ‌گیری برای رصد وضعیت در رندر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# توکن ربات مانا
TOKEN = "9057310870:AAFfuH_q1F7wFmNN4_jumMup2DEB0rp2-lY"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_name = update.message.from_user.first_name
    
    print(f"پیام دریافت شد از {user_name}: {user_text}")
    
    response = (
        f"سلام {user_name} عزیز!\n"
        f"پیام شما دریافت شد: '{user_text}'\n\n"
        f"🌟 ربات شرکت بازرگانی مانا با موفقیت روی سرور ابری رندر مستقر شد و آنلاین است!"
    )
    await update.message.reply_text(response)

def main():
    # ساخت اپلیکیشن تلگرام
    application = ApplicationBuilder().token(TOKEN).build()
    
    # اضافه کردن هندلر برای دریافت پیام‌های متنی
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("ربات مانا روی سرور ابری شروع به کار کرد...")
    
    # استفاده از روش Webhook یا پمپاژ مناسب برای هاست‌های ابری رندر
    # رندر به یک پورت نیاز دارد، اما برای تست اولیه از روش polling استاندارد با پورت دینامیک استفاده میکنیم
    port = int(os.environ.get("PORT", "10000"))
    
    # اجرای ربات به صورت وب‌هاک یا پولینگ سازگار با رندر
    # در رندر برای اینکه سرویس وب بسته نشود، از ساختار وب‌سرور سبک استفاده میکنیم
    # اما ساده‌ترین راه در رندر این است که رندر را به عنوان Background Worker تعریف کنیم 
    # یا از پورت وب‌سرویس استفاده کنیم.
