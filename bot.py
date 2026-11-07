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

TOKEN = "*******"
SHEET_NAME = "Mana_Database"

# تنظیمات نام کاربری و رمز عبور ربات
BOT_USERNAME = "ربات مانا خرد"
BOT_PASSWORD = "Mana@112233tc"

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
        logger.info("ربات تلگرام با موفقیت راه‌اندازی شد.")

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
            return "Error", 500
        return "OK", 200
    except Exception as e:
        logger.error(f"خطا در پردازش وب‌هوک: {e}")
        return "Error", 500

# --- احراز هویت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated', False):
        context.user_data['state'] = 'WAITING_FOR_USERNAME'
        text = f"🔐 به **{BOT_USERNAME}** خوش آمدید.\nلطفاً **نام کاربری** خود را وارد کنید:"
        if update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode="Markdown")
            await update.callback_query.answer()
        else:
            await update.message.reply_text(text, parse_mode="Markdown")
        return

    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✏️🗑️ ویرایش/حذف محصول", callback_data="menu_edit_del_product"),
            InlineKeyboardButton("➕ ثبت محصول جدید", callback_data="menu_add_product")
        ],
        [
            InlineKeyboardButton("✏️🗑️ ویرایش/حذف مشتری", callback_data="menu_edit_del_customer"),
            InlineKeyboardButton("➕ ثبت مشتری جدید", callback_data="menu_add_customer")
        ],
        [
            InlineKeyboardButton("🎯 تفکیک مشتریان (بالقوه/بالفعل)", callback_data="menu_customer_categories")
        ],
        [
            InlineKeyboardButton("✏️🗑️ ویرایش/حذف لجستیک", callback_data="menu_edit_del_logistics"),
            InlineKeyboardButton("➕ ثبت حمل جدید", callback_data="menu_add_logistics")
        ],
        [
            InlineKeyboardButton("🔔 ثبت پیگیری / یادآوری", callback_data="menu_add_followup"),
            InlineKeyboardButton("📊 لیست پیگیری‌ها", callback_data="menu_list_followups")
        ],
        [
            InlineKeyboardButton("💰 ثبت تراکنش مالی", callback_data="menu_add_finance"),
            InlineKeyboardButton("📈 گزارش مالی", callback_data="menu_list_finance")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "سلام مدیر عزیز! 🌟\n"
        f"به پنل مدیریت هوشمند بازرگانی **{BOT_USERNAME}** خوش آمدید.\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    
    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
        await update.callback_query.answer()
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('authenticated', False):
        await update.callback_query.answer("لطفاً ابتدا با دستور /start وارد شوید.", show_alert=True)
        return

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
            "📦 اطلاعات محصول جدید را خط‌به‌خط وارد کنید:\n\nنام محصول\nشماره بچ\nتاریخ انقضا\nموجودی\nلینک COA",
            parse_mode="Markdown"
        )
    elif data == "menu_add_customer":
        context.user_data['state'] = 'WAITING_FOR_CUSTOMER_DATA'
        await query.message.reply_text(
            "📝 اطلاعات مشتری جدید را خط‌به‌خط وارد کنید:\n\nنام شرکت\nشخص رابط\nتلفن\nعلاقه‌مندی‌ها\nوضعیت (بالقوه / بالفعل)",
            parse_mode="Markdown"
        )
    elif data == "menu_customer_categories":
        try:
            sheet = client.open(SHEET_NAME).worksheet("Customers")
            records = sheet.get_all_records()
            prospects = [r for r in records if "بالقوه" in str(r.get("Status", ""))]
            active = [r for r in records if "بالفعل" in str(r.get("Status", "")) or "فعال" in str(r.get("Status", ""))]
            
            msg = f"👥 **دسته‌بندی مشتریان مانا:**\n\n"
            msg += f"🎯 **مشتریان بالقوه (لیدها):** {len(prospects)} شرکت\n"
            for p in prospects[-5:]:
                msg.s += f"- {p.get('Company_Name')} ({p.get('Contact_Person')})\n"
            
            msg += f"\n⭐ **مشتریان بالفعل (فعال/خریدکرده):** {len(active)} شرکت\n"
            for a in active[-5:]:
                msg += f"- {a.get('Company_Name')} ({p.get('Contact_Person')})\n"
                
            await query.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ خطا در دسته‌بندی مشتریان: {e}")
        await show_back_menu(query.message)

    elif data == "menu_add_followup":
        context.user_data['state'] = 'WAITING_FOR_FOLLOWUP_DATA'
        await query.message.reply_text(
            "🔔 اطلاعات پیگیری/یادآوری را خط‌به‌خط وارد کنید:\n\nنام مشتری/شرکت\nموضوع پیگیری (مثلاً: تست نمونه سوربیتول)\nتاریخ پیگیری (مثلاً: 1405/08/20)\nتوضیحات و نتیجه",
            parse_mode="Markdown"
        )
    elif data == "menu_list_followups":
        try:
            sheet = client.open(SHEET_NAME).worksheet("FollowUps")
            records = sheet.get_all_records()
            if not records:
                await query.message.reply_text("📭 هیچ پیگیری یا یادآوری ثبت نشده است.")
            else:
                msg = "📊 **لیست پیگیری‌ها و یادآوری‌ها:**\n\n"
                for r in records[-10:]:
                    msg += f"🏢 مشتری: {r.get('Customer')}\n📌 موضوع: {r.get('Topic')}\n📅 تاریخ: {r.get('Date')}\n💬 توضیحات: {r.get('Notes')}\n-------------------\n"
                await query.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ خطا در خواندن پیگیری‌ها (شاید شیت FollowUps ساخته نشده باشد): {e}")
        await show_back_menu(query.message)

    elif data == "menu_add_finance":
        context.user_data['state'] = 'WAITING_FOR_FINANCE_DATA'
        await query.message.reply_text(
            "💰 اطلاعات تراکنش مالی را خط‌به‌خط وارد کنید:\n\nمشتری/فروشنده\nنوع تراکنش (فروش / خرید / هزینه)\nمبلغ (تومان)\nوضعیت تسویه (تسویه شده / چک / نسیه)",
            parse_mode="Markdown"
        )
    elif data == "menu_list_finance":
        try:
            sheet = client.open(SHEET_NAME).worksheet("Financial")
            records = sheet.get_all_records()
            if not records:
                await query.message.reply_text("📭 هیچ تراکنش مالی ثبت نشده است.")
            else:
                msg = "📈 **گزارش تراکنش‌های مالی:**\n\n"
                for r in records[-10:]:
                    msg += f"🏢 طرف حساب: {r.get('Party')}\n🏷 نوع: {r.get('Type')}\n💵 مبلغ: {r.get('Amount')}\n📌 وضعیت: {r.get('Status')}\n-------------------\n"
                await query.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ خطا در خواندن اطلاعات مالی (شاید شیت Financial ساخته نشده باشد): {e}")
        await show_back_menu(query.message)

    elif data == "menu_add_logistics":
        context.user_data['state'] = 'WAITING_FOR_LOGISTICS_DATA'
        await query.message.reply_text(
            "🚚 اطلاعات حمل را خط‌به‌خط وارد کنید:\n\nمشتری\nمحصول\nتاریخ بارگیری\nتاریخ تخلیه\nپلاک کامیون\nتلفن راننده",
            parse_mode="Markdown"
        )
    elif data in ["menu_edit_del_product", "menu_edit_del_customer", "menu_edit_del_logistics"]:
        target_ws = "Products" if "product" in data else ("Customers" if "customer" in data else "Logistics")
        target_name = "محصولات" if "product" in data else ("مشتریان" if "customer" in data else "لجستیک")
        try:
            sheet = client.open(SHEET_NAME).worksheet(target_ws)
            records = sheet.get_all_records()
            if not records:
                await query.message.reply_text(f"📭 موردی در {target_name} نیست.")
                return
            context.user_data['cached_records'] = records
            context.user_data['target_ws'] = target_ws
            msg = f"✏️🗑️ **لیست {target_name}:**\nدستور را به شکل `حذف 2` یا `ویرایش 1` بفرستید:\n\n"
            for i, r in enumerate(records, 1):
                keys = list(r.keys())
                main_val = r.get(keys[1], "بدون عنوان") if len(keys) > 1 else "بدون عنوان"
                msg += f"{i}. {main_val} (شناسه: `{r.get(keys[0])}`)\n"
            context.user_data['state'] = 'WAITING_FOR_INDEX_ACTION'
            await query.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ خطا: {e}")

async def show_back_menu(message):
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]]
    await message.reply_text("برای بازگشت به منو کلیک کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text
    
    if state == 'WAITING_FOR_USERNAME':
        if text.strip() == BOT_USERNAME:
            context.user_data['state'] = 'WAITING_FOR_PASSWORD'
            await update.message.reply_text("✅ نام کاربری تایید شد.\nاکنون **رمز عبور** را وارد کنید:")
        else:
            await update.message.reply_text("❌ نام کاربری اشتباه است. لطفاً دوباره تلاش کنید.")
        return

    if state == 'WAITING_FOR_PASSWORD':
        if text.strip() == BOT_PASSWORD:
            context.user_data['authenticated'] = True
            context.user_data['state'] = None
            await update.message.reply_text("✅ احراز هویت با موفقیت انجام شد!")
            await show_main_menu(update, context)
        else:
            await update.message.reply_text("❌ رمز عبور اشتباه است.")
            context.user_data['state'] = 'WAITING_FOR_USERNAME'
        return

    if not context.user_data.get('authenticated', False):
        await update.message.reply_text("⛔ لطفاً ابتدا با دستور /start وارد شوید.")
        return

    if not state:
        await update.message.reply_text("لطفاً از /start استفاده کنید.")
        return

    client = get_gsheet_client()
    if not client:
        await update.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    try:
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if state == 'WAITING_FOR_FOLLOWUP_DATA':
            if len(lines) < 4:
                await update.message.reply_text("❌ اطلاعات پیگیری ناقص است. لطفاً هر ۴ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("FollowUps")
            sheet.append_row([lines[0], lines[1], lines[2], lines[3]])
            await update.message.reply_text("✅ یادآوری و پیگیری جدید با موفقیت ثبت شد!", parse_mode="Markdown")
            context.user_data['state'] = None

        elif state == 'WAITING_FOR_FINANCE_DATA':
            if len(lines) < 4:
                await update.message.reply_text("❌ اطلاعات مالی ناقص است. لطفاً هر ۴ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Financial")
            sheet.append_row([lines[0], lines[1], lines[2], lines[3]])
            await update.message.reply_text("✅ تراکنش مالی با موفقیت ثبت شد!", parse_mode="Markdown")
            context.user_data['state'] = None

        elif state == 'WAITING_FOR_CUSTOMER_DATA':
            if len(lines) < 5:
                await update.message.reply_text("❌ اطلاعات مشتری ناقص است.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Customers")
            cust_id = "CUST-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([cust_id, lines[0], lines[1], lines[2], lines[3], lines[4]])
            await update.message.reply_text(f"✅ مشتری جدید ثبت شد!\nشناسه: `{cust_id}`", parse_mode="Markdown")
            context.user_data['state'] = None

        elif state == 'WAITING_FOR_PRODUCT_DATA':
            if len(lines) < 5:
                await update.message.reply_text("❌ اطلاعات محصول ناقص است.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Products")
            prod_id = "PROD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([prod_id, lines[0], lines[1], lines[2], lines[3], lines[4]])
            await update.message.reply_text(f"✅ محصول جدید ثبت شد!\nشناسه: `{prod_id}`", parse_mode="Markdown")
            context.user_data['state'] = None

        elif state == 'WAITING_FOR_LOGISTICS_DATA':
            if len(lines) < 6:
                await update.message.reply_text("❌ اطلاعات لجستیک ناقص است.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Logistics")
            order_id = "ORD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([order_id, lines[0], lines[1], lines[2], lines[3], lines[4], lines[5]])
            await update.message.reply_text(f"✅ حمل جدید ثبت شد!\nشناسه سفارش: `{order_id}`", parse_mode="Markdown")
            context.user_data['state'] = None

    except Exception as e:
        logger.error(f"خطا: {e}")
        await update.message.reply_text(f"❌ خطا: {e}")
        context.user_data['state'] = None

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
            logger.info("وب‌هوک با موفقیت تنظیم شد.")
        except Exception as e:
            logger.error(f"خطا در تنظیم وب‌هوک: {e}")

    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)
