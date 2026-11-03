import os
import logging
import json
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

# دریافت نام دامنه رندر از متغیرهای محیطی یا تنظیم دستی
# رندر به طور خودکان Render URL را ست می‌کند یا خودتون آدرس وب‌سرویس رندر رو اینجا بذارید
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

def get_gsheet_client():
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            logger.error("GOOGLE_CREDENTIALS_JSON not found!")
            return None
        creds_dict = json.loads(creds_json)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"Error connecting to Google Sheets: {e}")
        return None

web_app = Flask(__name__)

# راه‌اندازی اپلیکیشن تلگرام به صورت گلوبال
application = ApplicationBuilder().token(TOKEN).build()

@web_app.route('/')
def home():
    client = get_gsheet_client()
    status = "Connected to Google Sheets successfully!" if client else "Failed to connect to Google Sheets!"
    return f"Mana Bot Webhook is running! | DB Status: {status}"

# نقطه دریافت آپدیت‌ها از تلگرام (Webhook Endpoint)
@web_app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        json_update = request.get_json(force=True)
        update = Update.de_json(json_update, application.bot)
        
        # اجرای ناهمگام آپدیت در حلقه رویداد تلگرام
        import asyncio
        asyncio.run(application.process_update(update))
        return "OK", 200
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        return "Error", 500

# --- منوی اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ ثبت مشتری جدید", callback_data="menu_add_customer"),
         InlineKeyboardButton("➕ ثبت محصول جدید", callback_data="menu_add_product")],
        [InlineKeyboardButton("➕ ثبت حمل و نقل", callback_data="menu_add_logistics"),
         InlineKeyboardButton("✏️🗑️ ویرایش/حذف مشتری", callback_data="menu_edit_del_customer")],
        [InlineKeyboardButton("✏️🗑️ ویرایش/حذف محصول", callback_data="menu_edit_del_product"),
         InlineKeyboardButton("✏️🗑️ ویرایش/حذف لجستیک", callback_data="menu_edit_del_logistics")],
        [InlineKeyboardButton("📋 نمایش مشتریان ثبت شده", callback_data="menu_list_customers"),
         InlineKeyboardButton("📊 جدول پیگیری‌ها", callback_data="menu_followups")]
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

    if data == "menu_add_customer":
        context.user_data['state'] = 'WAITING_FOR_CUSTOMER_DATA'
        await query.message.reply_text(
            "📝 لطفاً اطلاعات مشتری جدید را به شکل زیر (با استفاده از علامت |) ارسال کنید:\n\n"
            "`نام شرکت | شخص رابط | تلفن | علاقه‌مندی‌ها | وضعیت`\n\n"
            "*(مثال: پتروآریا | آقای رضایی | 09123456789 | خرید استون | فعال)*",
            parse_mode="Markdown"
        )
    elif data == "menu_add_product":
        context.user_data['state'] = 'WAITING_FOR_PRODUCT_DATA'
        await query.message.reply_text(
            "📦 لطفاً اطلاعات محصول جدید را به شکل زیر ارسال کنید:\n\n"
            "`نام محصول | شماره بچ (Batch) | تاریخ انقضا | موجودی | لینک COA`",
            parse_mode="Markdown"
        )
    elif data == "menu_add_logistics":
        context.user_data['state'] = 'WAITING_FOR_LOGISTICS_DATA'
        await query.message.reply_text(
            "🚚 لطفاً اطلاعات حمل و نقل را به شکل زیر ارسال کنید:\n\n"
            "`شماره سفارش | مشتری | محصول | تاریخ بارگیری | تاریخ تخلیه | پلاک کامیون | تلفن راننده`",
            parse_mode="Markdown"
        )
    elif data == "menu_list_customers":
        try:
            sheet = client.open(SHEET_NAME).worksheet("Customers")
            records = sheet.get_all_records()
            if not records:
                await query.message.reply_text("📭 هیچ مشتری‌ای ثبت نشده است.")
            else:
                msg = "📋 **لیست مشتریان ثبت شده:**\n\n"
                for r in records[-10:]:
                    msg += f"🆔 شناسه: `{r.get('Customer_ID')}`\n🏢 شرکت: {r.get('Company_Name')}\n👤 رابط: {r.get('Contact_Person')}\n📞 تلفن: {r.get('Phone')}\n📌 وضعیت: {r.get('Status')}\n-------------------\n"
                await query.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ خطا در خواندن اطلاعات: {e}")
        await show_back_menu(query.message)
    elif data == "menu_followups":
        await query.message.reply_text("📊 جدول پیگیری‌ها به‌زودی فعال می‌شود.")
        await show_back_menu(query.message)
    elif data in ["menu_edit_del_customer", "menu_edit_del_product", "menu_edit_del_logistics"]:
        target = "Customers" if "customer" in data else ("Products" if "product" in data else "Logistics")
        await query.message.reply_text(
            f"✏️🗑️ برای ویرایش یا حذف در بخش **{target}**، دستور مربوطه را ارسال کنید:\n"
            "حذف: `/delete_customer CUST-XXXX`\nویرایش: `/edit_customer CUST-XXXX | ستون | مقدار جدید`",
            parse_mode="Markdown"
        )

async def show_back_menu(message):
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]]
    await message.reply_text("برای بازگشت به منو کلیک کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text
    if not state:
        await update.message.reply_text("لطفاً ابتدا دستور /start را ارسال کنید.")
        return

    client = get_gsheet_client()
    if not client:
        await update.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    try:
        if state == 'WAITING_FOR_CUSTOMER_DATA':
            parts = [p.strip() for p in text.split("|")]
            if len(parts) < 5:
                await update.message.reply_text("❌ اطلاعات ناقص است. ۵ قسمت با | جدا شوند.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Customers")
            cust_id = "CUST-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([cust_id, parts[0], parts[1], parts[2], parts[3], parts[4]])
            await update.message.reply_text(f"✅ مشتری جدید با موفقیت ثبت شد!\nشناسه: `{cust_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
        elif state == 'WAITING_FOR_PRODUCT_DATA':
            parts = [p.strip() for p in text.split("|")]
            if len(parts) < 5:
                await update.message.reply_text("❌ اطلاعات ناقص است.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Products")
            prod_id = "PROD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([prod_id, parts[0], parts[1], parts[2], parts[3], parts[4]])
            await update.message.reply_text(f"✅ محصول جدید ثبت شد!\nشناسه: `{prod_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
        elif state == 'WAITING_FOR_LOGISTICS_DATA':
            parts = [p.strip() for p in text.split("|")]
            if len(parts) < 6:
                await update.message.reply_text("❌ اطلاعات لجستیک ناقص است.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Logistics")
            order_id = "ORD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([order_id] + parts)
            await update.message.reply_text(f"✅ حمل و نقل ثبت شد!\nشناسه سفارش: `{order_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ خطا: {e}")
        context.user_data['state'] = None

# تنظیم هندلرها
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(start, pattern="^back_to_main$"))
application.add_handler(CallbackQueryHandler(button_handler, pattern="^menu_"))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))

if __name__ == '__main__':
    # تنظیم وب‌هوک تلگرام به محض استارت اپلیکیشن
    import requests
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/{TOKEN}"
        set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}"
        requests.get(set_url)
        logger.info(f"Webhook set to: {webhook_url}")

    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
