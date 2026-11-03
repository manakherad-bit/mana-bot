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

# --- شروع و بررسی احراز هویت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # بررسی اینکه آیا کاربر قبلاً لاگین کرده است یا خیر
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
            InlineKeyboardButton("✏️🗑️ ویرایش/حذف لجستیک", callback_data="menu_edit_del_logistics"),
            InlineKeyboardButton("➕ ثبت حمل جدید", callback_data="menu_add_logistics")
        ],
        [
            InlineKeyboardButton("📊 جدول پیگیری‌ها", callback_data="menu_followups"),
            InlineKeyboardButton("📋 نمایش مشتریان", callback_data="menu_list_customers")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "سلام مدیر عزیز! 🌟\n"
        f"به پنل مدیریت هوشمند **{BOT_USERNAME}** خوش آمدید.\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    
    if update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
        await update.callback_query.answer()
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # اگر کاربر لاگین نکرده باشد، اجازه دسترسی به دکمه‌ها داده نمی‌شود
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
            "📦 لطفاً اطلاعات محصول جدید را به‌صورت خط‌به‌خط (هر مورد در یک خط با زدن Enter) ارسال کنید:\n\n"
            "نام محصول\n"
            "شماره بچ (Batch)\n"
            "تاریخ انقضا\n"
            "موجودی\n"
            "لینک COA",
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
            "وضعیت",
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
        
    elif data in ["menu_edit_del_product", "menu_edit_del_customer", "menu_edit_del_logistics"]:
        target_ws = "Products" if "product" in data else ("Customers" if "customer" in data else "Logistics")
        target_name = "محصولات" if "product" in data else ("مشتریان" if "customer" in data else "لجستیک")
        
        try:
            sheet = client.open(SHEET_NAME).worksheet(target_ws)
            records = sheet.get_all_records()
            if not records:
                await query.message.reply_text(f"📭 هیچ موردی در بخش {target_name} ثبت نشده است.")
                return
            
            context.user_data['cached_records'] = records
            context.user_data['target_ws'] = target_ws
            
            msg = f"✏️🗑️ **لیست {target_name}:**\nبرای حذف یا ویرایش، دستور خود را به یکی از شکل‌های زیر بفرستید:\n(مثال: `حذف 2` یا `ویرایش 1`)\n\n"
            
            for i, r in enumerate(records, 1):
                keys = list(r.keys())
                main_val = r.get(keys[1], "بدون عنوان") if len(keys) > 1 else "بدون عنوان"
                msg += f"{i}. {main_val} (شناسه: `{r.get(keys[0])}`)\n"
                
            context.user_data['state'] = 'WAITING_FOR_INDEX_ACTION'
            await query.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            await query.message.reply_text(f"❌ خطا در دریافت اطلاعات: {e}")

async def show_back_menu(message):
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main")]]
    await message.reply_text("برای بازگشت به منو کلیک کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text
    
    # کنترل مراحل ورود نام کاربری و رمز عبور
    if state == 'WAITING_FOR_USERNAME':
        if text.strip() == BOT_USERNAME:
            context.user_data['state'] = 'WAITING_FOR_PASSWORD'
            await update.message.reply_text("✅ نام کاربری تایید شد.\nاکنون لطفاً **رمز عبور** خود را وارد کنید:")
        else:
            await update.message.reply_text("❌ نام کاربری اشتباه است. لطفاً دوباره تلاش کنید یا /start را بفرستید.")
        return

    if state == 'WAITING_FOR_PASSWORD':
        if text.strip() == BOT_PASSWORD:
            context.user_data['authenticated'] = True
            context.user_data['state'] = None
            await update.message.reply_text("✅ احراز هویت با موفقیت انجام شد!")
            await show_main_menu(update, context)
        else:
            await update.message.reply_text("❌ رمز عبور اشتباه است. لطفاً دوباره تلاش کنید یا /start را بفرستید.")
            context.user_data['state'] = 'WAITING_FOR_USERNAME'
        return

    # بررسی احراز هویت برای بقیه بخش‌ها
    if not context.user_data.get('authenticated', False):
        await update.message.reply_text("⛔ لطفاً ابتدا با دستور /start و ورود نام کاربری و رمز عبور وارد شوید.")
        return

    if not state:
        await update.message.reply_text("لطفاً ابتدا از دستور /start برای ورود به منو استفاده کنید.")
        return

    client = get_gsheet_client()
    if not client:
        await update.message.reply_text("❌ خطا در اتصال به گوگل‌شیت.")
        return

    try:
        if state == 'WAITING_FOR_INDEX_ACTION':
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("❌ فرمت اشتباه است. لطفاً به صورت `حذف 2` یا `ویرایش 1` ارسال کنید.", parse_mode="Markdown")
                return
            
            action_word = parts[0]
            try:
                idx = int(parts[1]) - 1
            except ValueError:
                await update.message.reply_text("❌ شماره ردیف وارد شده معتبر نیست.")
                return
                
            records = context.user_data.get('cached_records', [])
            target_ws = context.user_data.get('target_ws')
            
            if idx < 0 or idx >= len(records):
                await update.message.reply_text("❌ شماره ردیف وارد شده در لیست وجود ندارد.")
                return
                
            selected_record = records[idx]
            keys = list(selected_record.keys())
            rec_id = selected_record.get(keys[0])
            sheet_row_idx = idx + 2
            
            if "حذف" in action_word:
                sheet = client.open(SHEET_NAME).worksheet(target_ws)
                sheet.delete_rows(sheet_row_idx)
                await update.message.reply_text(f"✅ ردیف شماره {idx + 1} با موفقیت حذف شد.", parse_mode="Markdown")
                context.user_data['state'] = None
                
            elif "ویرایش" in action_word:
                context.user_data['edit_sheet'] = target_ws
                context.user_data['edit_row'] = sheet_row_idx
                context.user_data['edit_id'] = rec_id
                
                if target_ws == "Products":
                    context.user_data['state'] = 'WAITING_FOR_EDIT_PRODUCT_DATA'
                    await update.message.reply_text(
                        f"📦 در حال ویرایش ردیف {idx + 1} (محصول `{rec_id}`).\nلطفاً اطلاعات جدید را به‌صورت خط‌به‌خط وارد کنید:\n\n"
                        "نام محصول\nشماره بچ\nتاریخ انقضا\nموجودی\nلینک COA", parse_mode="Markdown"
                    )
                elif target_ws == "Customers":
                    context.user_data['state'] = 'WAITING_FOR_EDIT_CUSTOMER_DATA'
                    await update.message.reply_text(
                        f"📝 در حال ویرایش ردیف {idx + 1} (مشتری `{rec_id}`).\nلطفاً اطلاعات جدید را به‌صورت خط‌به‌خط وارد کنید:\n\n"
                        "نام شرکت\nشخص رابط\nتلفن\nعلاقه‌مندی‌ها\nوضعیت", parse_mode="Markdown"
                    )
                elif target_ws == "Logistics":
                    context.user_data['state'] = 'WAITING_FOR_EDIT_LOGISTICS_DATA'
                    await update.message.reply_text(
                        f"🚚 در حال ویرایش ردیف {idx + 1} (لجستیک `{rec_id}`).\nلطفاً اطلاعات جدید را به‌صورت خط‌به‌خط وارد کنید:\n\n"
                        "مشتری\nمحصول\nتاریخ بارگیری\nتاریخ تخلیه\nپلاک کامیون\nتلفن راننده", parse_mode="Markdown"
                    )
            return

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        if state == 'WAITING_FOR_PRODUCT_DATA':
            if len(lines) < 5:
                await update.message.reply_text("❌ اطلاعات ناقص است. لطفاً هر ۵ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Products")
            prod_id = "PROD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([prod_id, lines[0], lines[1], lines[2], lines[3], lines[4]])
            await update.message.reply_text(f"✅ محصول جدید با موفقیت ثبت شد!\nشناسه: `{prod_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
            
        elif state == 'WAITING_FOR_CUSTOMER_DATA':
            if len(lines) < 5:
                await update.message.reply_text("❌ اطلاعات ناقص است. لطفاً هر ۵ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Customers")
            cust_id = "CUST-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([cust_id, lines[0], lines[1], lines[2], lines[3], lines[4]])
            await update.message.reply_text(f"✅ مشتری جدید با موفقیت ثبت شد!\nشناسه: `{cust_id}`", parse_mode="Markdown")
            context.user_data['state'] = None
            
        elif state == 'WAITING_FOR_LOGISTICS_DATA':
            if len(lines) < 6:
                await update.message.reply_text("❌ اطلاعات لجستیک ناقص است. لطفاً هر ۶ مورد را در خطوط جداگانه وارد کنید.")
                return
            sheet = client.open(SHEET_NAME).worksheet("Logistics")
            order_id = "ORD-" + datetime.datetime.now().strftime("%m%d%H%M")
            sheet.append_row([order_id, lines[0], lines[1], lines[2], lines[3], lines[4], lines[5]])
            await update.message.reply_text(f"✅ حمل جدید با موفقیت ثبت شد!\nشناسه سفارش: `{order_id}`", parse_mode="Markdown")
            context.user_data['state'] = None

        elif state in ['WAITING_FOR_EDIT_PRODUCT_DATA', 'WAITING_FOR_EDIT_CUSTOMER_DATA', 'WAITING_FOR_EDIT_LOGISTICS_DATA']:
            target_ws = context.user_data.get('edit_sheet')
            row_idx = context.user_data.get('edit_row')
            rec_id = context.user_data.get('edit_id')
            
            expected_count = 6 if target_ws == "Logistics" else 5
            if len(lines) < expected_count:
                await update.message.reply_text(f"❌ اطلاعات ناقص است. لطفاً تمام {expected_count} مورد را در خطوط جداگانه وارد کنید.")
                return
                
            sheet = client.open(SHEET_NAME).worksheet(target_ws)
            new_row_data = [rec_id] + lines
            
            sheet.update(f"A{row_idx}:F{row_idx}" if expected_count == 5 else f"A{row_idx}:G{row_idx}", [new_row_data])
            await update.message.reply_text(f"✅ اطلاعات ردیف با موفقیت ویرایش و به‌روزرسانی شد!", parse_mode="Markdown")
            context.user_data['state'] = None
            
    except Exception as e:
        logger.error(f"خطا در ثبت یا ویرایش اطلاعات: {e}")
        await update.message.reply_text(f"❌ خطا: {e}")
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
