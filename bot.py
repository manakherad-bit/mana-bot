import os
import logging
import json
import threading
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import gspread
from google.oauth2.service_account import Credentials
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "9057310870:AAFfuH_q1F7wFmNN4_jumMup2DEB0rp2-lY"
SHEET_NAME = "Mana_Database"

RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

def get_gsheet_client():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            logger.error("GOOGLE_CREDENTIALS_JSON یافت نشد!")
            return None
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"خطا در اتصال به گوگل‌شیت: {e}")
        return None

web_app = Flask(__name__)

application = ApplicationBuilder().token(TOKEN).build()

telegram_loop = None

def run_telegram_background_loop():
    global telegram_loop
    telegram_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(telegram_loop)
    
    async def init_bot():
        await application.initialize()
        await application.start()
        logger.info("ربات تلگرام با موفقیت راه‌اندازی و مقداردهی شد.")

    telegram_loop.run_until_complete(init_bot())
    
    try:
        telegram_loop.run_forever()
    except Exception as e:
        logger.error(f"خطای لوپ تلگرام: {e}")

@web_app.route('/')
def home():
    client = get_gsheet_client()
    status = "اتصال به گوگل‌شیت برقرار است!" if client else "خطا در اتصال به گوگل‌شیت!"
    return f"وب‌هوک ربات مانا فعال است! | وضعیت دیتابیس: {status}"

@web_app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        json_update = request.get_json(force=True)
        update = Update.de_json(json_update, application.bot)
        
        if telegram_loop and telegram_loop.is_running():
            asyncio.run_coroutine_threadsafe(application.process_update(update), telegram_loop)
        else:
            logger.error("حلقه رویداد تلگرام در حال اجرا نیست!")
            return "Error", 500
            
        return "OK", 200
    except Exception as e:
        logger.error(f"خطا در پردازش وب‌هوک: {e}")
        return "Error", 500

# --- منوی اصلی ربات با چیدمان جدید ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("➕ ثبت محصول جدید", callback_data="menu_add_product"),
            InlineKeyboardButton("✏️🗑️ ویرایش/حذف محصول", callback_data="menu_edit_del_product")
        ],
        [
            InlineKeyboardButton("➕ ثبت مشتری جدید", callback_data="menu_add_customer"),
            InlineKeyboardButton("✏️🗑️ ویرایش/حذف مشتری", callback_data="menu_edit_del_customer")
        ],
        [
            InlineKeyboardButton("➕ ثبت حمل جدید", callback_data="menu_add_logistics"),
            InlineKeyboardButton("✏️🗑️ ویرایش/حذف لجستیک", callback_data="menu_edit_del_logistics")
        ],
        [
            InlineKeyboardButton("📊 جدول پیگیری‌ها", callback_data="menu_followups"),
            InlineKeyboardButton("📋 نمایش مشتریان", callback_data="menu_list_customers")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "سلام مدیر عزیز! 🌟\n"
        "به پنل مدیریت هوشمند شرکت بازرگانی **مانا** خوش آمدید.\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    
    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
        await update.callback_query.answer()
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    client = get_gsheet_client()
    if not client:
        await query.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    if data == "menu_add_product":
        context.user_data['state'] = 'WAITING_FOR_PRODUCT_DATA'
        await query.message.reply_text(
            "📦 لطفاً اطلاعات محصول جدید را به‌صورت خط‌به‌خط (هر مورد در یک خط با زدن Enter) ارسال کنید:\n\n"
            "نام محصول\n"
            "شماره بچ (Batch)\n"
            "تاریخ انقضا\n"
            "موجودی\n"
            "لینک COA\n\n"
            "*(مثال: استون | BATCH123 | 2027/05 | 1000 | http://...)*",
            parse_mode="Markdown"
        )
    elif data == "menu_add_customer":
        context.user_data['state'] = 'WAITING_FOR_CUSTOMER_DATA'
        await query.message.reply_text(
            "📝 لطفاً اطلاعات مشتری جدید را به‌صورت خط‌به‌خط (هر مورد در یک خط با زدن Enter) ارسال کنید:\n\n"
            "نام شرکت\n"
            "شخص رابط\n"
            "تلفن\n"
            "علاقه‌مندی‌ها\n"
            "وضعیت\n\n"
            "*(مثال:\nپتروآریا\nآقای رضایی\n09123456789\nخرید استون\nفعال)*",
            parse_mode="Markdown"
        )
    elif data == "menu_add_logistics":
        context.user_data['state'] = 'WAITING_FOR_LOGISTICS_DATA'
        await query.message.reply_text(
            "🚚 لطفاً اطلاعات حمل و نقل را به‌صورت خط‌به‌خط (هر مورد در یک خط با زدن Enter) ارسال کنید:\n\n"
            "مشتری\n"
            "محصول\n"
            "تاریخ بارگیری\n"
            "تاریخ تخلیه\n"
            "پلاک کامیون\n"
            "تلفن راننده",
            parse_mode="Markdown"
        )
    elif data == "menu_list_customers":
        try:
            sheet = client.open(SHEET_NAME).worksheet("Customers")
            records = sheet.get_all_records()
            if not records:
                await query.message.reply_text("📭 هیچ مشتری‌ای در بخش مشتریان ثبت نشده است.")
            else:
                msg = "📋 **لیست مشتریان ثبت شده:**\n\n"
                for r in records[-10:]:
                    msg += f"🆔 شناسه: `{r.get('Customer_ID')}`\n🏢 شرکت: {r.get('Company_Name')}\n👤 رابط: {r.get('Contact_Person')}\n📞 تلفن: {r.get('Phone')}\n📌 وضعیت: {r.get('Status')}\n-------------------\n"
                await query.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ خطا در خواندن اطلاعات مشتریان: {e}")
        await show_back_menu(query.message)
    elif data == "menu_followups":
        await query.message.reply_text("📊 جدول پیگیری‌ها به‌زودی فعال می‌شود.")
        await show_back_menu(query.message)
    elif data in ["menu_edit_del_customer", "menu_edit_del_product", "menu_edit_del_logistics"]:
        target = "مشتریان" if "customer" in data else ("محصولات" if "product" in data else "لجستیک")
        await query.message.reply_text(
            f"✏️🗑️ برای ویرایش یا حذف در بخش **{target}**، دستور مربوطه را ارسال کنید:\n"
            "حذف: `/delete_record شناسه`\nویرایش: `/edit_record شناسه | ستون | مقدار جدید`",
            parse_mode="Markdown"
        )

async def show_back_menu(message):
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]]
    await message.reply_text("برای بازگشت به منو کلیک کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text
    if not state:
        await update.message.reply_text("لطفاً ابتدا از دستور /start برای ورود به منو استفاده کنید.")
        return

    client = get_gsheet_client()
    if not client:
        await update.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    try:
        # تفکیک خط‌به‌خط ورودی‌های کاربر (جایگزین علامت |)
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if state == 'WAITING_FOR_PRODUCT_DATA':
            if len(lines) < 5:
                await query.message.reply_text("❌ اطلاعات ناقص است. لطفاً هر ۵ مورد را در خطوط جداگانه وارد کنید.") if 'query' in locals() else await update.message.reply_text("❌ اطلاعات ناقص است. لطفاً هر ۵ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Products")
            prod_id = "PROD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([prod_id, lines[0], lines[1], lines[2], lines[3], lines[4]])
            await update.message.reply_text(f"✅ محصول جدید با موفقیت در بخش محصولات ثبت شد!\nشناسه: `{prod_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
            
        elif state == 'WAITING_FOR_CUSTOMER_DATA':
            if len(lines) < 5:
                await update.message.reply_text("❌ اطلاعات ناقص است. لطفاً هر ۵ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Customers")
            cust_id = "CUST-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([cust_id, lines[0], lines[1], lines[2], lines[3], lines[4]])
            await update.message.reply_text(f"✅ مشتری جدید با موفقیت در بخش مشتریان ثبت شد!\nشناسه: `{cust_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
            
        elif state == 'WAITING_FOR_LOGISTICS_DATA':
            if len(lines) < 6:
                await update.message.reply_text("❌ اطلاعات لجستیک ناقص است. لطفاً هر ۶ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Logistics")
            order_id = "ORD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([order_id, lines[0], lines[1], lines[2], lines[3], lines[4], lines[5]])
            await update.message.reply_text(f"✅ حمل جدید با موفقیت در بخش لجستیک ثبت شد!\nشناسه سفارش: `{order_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
            
    except Exception as e:
        logger.error(f"خطا در ثبت اطلاعات: {e}")
        await update.message.reply_text(f"❌ خطا در ثبت اطلاعات: {e}")
        context.user_data['state'] = None

# تنظیم هندلرها
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(start, pattern="^back_to_main$"))
application.add_handler(CallbackQueryHandler(button_handler, pattern="^menu_"))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))

if __name__ == '__main__':
    t = threading.Thread(target=run_telegram_background_loop, daemon=True)
    t.start()

    import requests
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/{TOKEN}"
        set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
        try:
            requests.get(set_url)
            logger.info(f"وب‌هوک با موفقیت روی آدرس تنظیم شد: {webhook_url}")
        except Exception as e:
            logger.error(f"تنظیم وب‌هوک ناموفق بود: {e}")

    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
