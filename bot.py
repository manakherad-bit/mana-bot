import os
import logging
import json
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
import threading
import gspread
from google.oauth2.service_account import Credentials
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "9057310870:AAFfuH_q1F7wFmNN4_jumMup2DEB0rp2-lY"
SHEET_NAME = "Mana_Database"

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

# --- دستورات مدیریت مشتریان (Customers) ---

async def add_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # فرمت دستور: /add_customer Company | Contact | Phone | Preferences | Status
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ لطفاً اطلاعات را به این شکل وارد کنید:\n`/add_customer نام شرکت | شخص رابط | تلفن | علاقه‌مندی‌ها | وضعیت`", parse_mode="Markdown")
        return
    
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 5:
        await update.message.reply_text("❌ اطلاعات ناقص است. ۵ قسمت (شرکت، رابط، تلفن، علاقه‌مندی، وضعیت) با علامت | باید جدا شوند.")
        return

    client = get_gsheet_client()
    if not client:
        await update.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    try:
        sheet = client.open(SHEET_NAME).worksheet("Customers")
        # تولید Customer_ID خودکار بر اساس تاریخ و زمان
        cust_id = "CUST-" + datetime.datetime.now().strftime("%m%d%H%M")
        
        row_data = [cust_id, parts[0], parts[1], parts[2], parts[3], parts[4]]
        sheet.append_row(row_data)
        
        await update.message.reply_text(f"✅ مشتری جدید با موفقیت ثبت شد!\nشناسه مشتری: `{cust_id}`", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error adding customer: {e}")
        await update.message.reply_text(f"❌ خطا در ثبت اطلاعات: {e}")

async def delete_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # فرمت دستور: /delete_customer CUST-102
    if not context.args:
        await update.message.reply_text("❌ لطفاً شناسه مشتری را وارد کنید:\n`/delete_customer CUST-XXXX`", parse_mode="Markdown")
        return
    
    cust_id = context.args[0].strip()
    client = get_gsheet_client()
    if not client:
        await update.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    try:
        sheet = client.open(SHEET_NAME).worksheet("Customers")
        cell = sheet.find(cust_id)
        if cell:
            sheet.delete_rows(cell.row)
            await update.message.reply_text(f"🗑️ مشتری با شناسه `{cust_id}` با موفقیت حذف شد.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ مشتری با شناسه `{cust_id}` یافت نشد.")
    except Exception as e:
        logger.error(f"Error deleting customer: {e}")
        await update.message.reply_text(f"❌ خطا در حذف اطلاعات: {e}")

async def edit_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # فرمت دستور: /edit_customer CUST-102 | ستون (مثلا Phone) | مقدار جدید
    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("❌ فرمت اشتباه است. نمونه:\n`/edit_customer CUST-102 | Phone | 09120000000`", parse_mode="Markdown")
        return

    cust_id, col_name, new_value = parts[0], parts[1], parts[2]
    client = get_gsheet_client()
    if not client:
        await update.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    try:
        sheet = client.open(SHEET_NAME).worksheet("Customers")
        cell = sheet.find(cust_id)
        if not cell:
            await update.message.reply_text(f"⚠️ مشتری با شناسه `{cust_id}` یافت نشد.")
            return

        # پیدا کردن شماره ستون بر اساس نام هدر در ردیف اول
        header_row = sheet.row_values(1)
        if col_name not in header_row:
            await update.message.reply_text(f"⚠️ نام ستون `{col_name}` معتبر نیست. ستون‌های موجود: {header_row}")
            return
        
        col_index = header_row.index(col_name) + 1
        sheet.update_cell(cell.row, col_index, new_value)
        await update.message.reply_text(f"✏️ اطلاعات مشتری `{cust_id}` (ستون {col_name}) با موفقیت به `{new_value}` ویرایش شد.", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error editing customer: {e}")
        await update.message.reply_text(f"❌ خطا در ویرایش اطلاعات: {e}")

# مدیریت پیام‌های متنی عادی
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_name = update.message.from_user.first_name
    
    client = get_gsheet_client()
    db_status = "متصل به گوگل‌شیت ✅" if client else "خطا در اتصال به گوگل‌شیت ❌"

    response = (
        f"سلام {user_name} عزیز!\n"
        f"وضعیت دیتابیس مانا: {db_status}\n\n"
        f"برای ثبت مشتری جدید از دستور زیر استفاده کنید:\n"
        f"`/add_customer نام شرکت | شخص رابط | تلفن | علاقه‌مندی‌ها | وضعیت`"
    )
    await update.message.reply_text(response, parse_mode="Markdown")

def main_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    
    # ثبت دستورات
    application.add_handler(CommandHandler("add_customer", add_customer))
    application.add_handler(CommandHandler("delete_customer", delete_customer))
    application.add_handler(CommandHandler("edit_customer", edit_customer))
    
    # ثبت هندلر پیام‌های متنی عادی
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("Bot started polling with CRM commands...")
    application.run_polling()

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.start()
    main_bot()
