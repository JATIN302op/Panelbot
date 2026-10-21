import os
import logging
import requests
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv

# Environment variables load karein (Telegram Token ke liye)
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Aapki Guarante Shop API Key[span_0](start_span)[span_0](end_span)
API_KEY = "gsk_8d059510f424c1bf8b69941682339a0ff086e77208c7643d"

# Aapki Details
ADMIN_USER_ID = 8548708943
SUPPORT_USERNAME = "highbread"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
BASE_URL = "https://proxy.yamin.bd/apis.php"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Dynamic Settings
BOT_SETTINGS = {
    "markup_percent": 30.0,
    "upi_id": "highbread@upi",
    "usdt_address": "TYourUSDTWalletAddressHere..."
}

# FSM States for Deposit Process
class DepositState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_proof = State()

# Admin Setting States (Button / Text input ke liye)
class AdminState(StatesGroup):
    waiting_for_new_upi = State()
    waiting_for_new_usdt = State()
    waiting_for_new_margin = State()

def apply_markup(base_price):
    try:
        price = float(base_price)
        multiplier = 1 + (BOT_SETTINGS["markup_percent"] / 100.0)
        return round(price * multiplier, 2)
    except:
        return base_price

@dp.message_handler(commands=['start'], state='*')
async def start_cmd(message: types.Message, state: FSMContext):
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📦 Product Catalog", callback_data="show_catalog"),
        InlineKeyboardButton("🌐 Proxy & VPN Products", callback_data="show_proxies"),
        InlineKeyboardButton("💳 Add Balance / Deposit", callback_data="deposit_menu"),
        InlineKeyboardButton("👤 My Account Balance", callback_data="check_account"),
        InlineKeyboardButton("📋 My Orders", callback_data="check_orders"),
        InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")
    )
    
    if message.from_user.id == ADMIN_USER_ID:
        markup.add(InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))

    await message.reply(
        "👋 **Guarante Shop Reselling Bot** mein aapka swagat hai!\n\n"
        "Neeche diye gaye options se products aur balance manage karein:", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# --- DEPOSIT SYSTEM ---
@dp.callback_query_handler(text="deposit_menu")
async def deposit_menu(call: types.CallbackQuery):
    await call.answer()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🇮🇳 UPI (INR)", callback_data="dep_upi"),
        InlineKeyboardButton("🪙 USDT (Crypto)", callback_data="dep_usdt"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="back_home")
    )
    text = (
        "💳 **Deposit Balance**\n\n"
        "Kripya apna payment method select karein:"
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(text=["dep_upi", "dep_usdt"])
async def select_deposit_method(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    method = "UPI (INR)" if call.data == "dep_upi" else "USDT (Crypto)"
    details = f"UPI ID: `{BOT_SETTINGS['upi_id']}`" if call.data == "dep_upi" else f"USDT Address (TRC20):\n`{BOT_SETTINGS['usdt_address']}`"
    
    await state.update_data(method=method)
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="back_home"))
    
    await call.message.edit_text(
        f"💳 **Payment Method: {method}**\n\n"
        f"{details}\n\n"
        f"Kripya upar diye gaye address par payment karein, aur jitna amount aapne bheja hai wo **number mein yahan type karke bhej dein** (Jaise: `100` ya `500`):",
        reply_markup=markup, parse_mode="Markdown"
    )
    await DepositState.waiting_for_amount.set()

@dp.message_handler(state=DepositState.waiting_for_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    amount = message.text.strip()
    await state.update_data(amount=amount)
    
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="back_home"))
    await message.reply(
        f"✅ Amount darj ho gaya: `{amount}`\n\n"
        f"Ab kripya apne payment ka **Screenshot (Photo)** aur sath mein **Transaction ID / UTR** likh kar ek hi message mein bhej dein:",
        reply_markup=markup, parse_mode="Markdown"
    )
    await DepositState.waiting_for_proof.set()

@dp.message_handler(state=DepositState.waiting_for_proof, content_types=['photo', 'text'])
async def process_deposit_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    method = data.get("method")
    amount = data.get("amount")
    
    user = message.from_user
    user_info = f"@{user.username}" if user.username else f"{user.first_name} (ID: {user.id})"
    proof_text = message.text or message.caption or "No text provided"
    
    admin_markup = InlineKeyboardMarkup(row_width=2)
    admin_markup.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}_{amount}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}")
    )
    
    admin_msg = (
        f"🔔 **New Deposit Request!**\n\n"
        f"👤 User: {user_info}\n"
        f"🆔 User ID: `{user.id}`\n"
        f"💳 Method: {method}\n"
        f"💰 Amount: `{amount}`\n"
        f"📝 TxID / Note: {proof_text}\n"
    )
    
    try:
        if message.photo:
            photo_file_id = message.photo[-1].file_id
            await bot.send_photo(ADMIN_USER_ID, photo=photo_file_id, caption=admin_msg, reply_markup=admin_markup, parse_mode="Markdown")
        else:
            await bot.send_message(ADMIN_USER_ID, text=admin_msg, reply_markup=admin_markup, parse_mode="Markdown")
            
        await message.reply("✅ Aapki deposit request admin ke paas approval ke liye bhej di gayi hai! Kripya verification ka intezaar karein.")
    except Exception as e:
        await message.reply("❌ Request bhejne mein error aayi. Kripya support se sampark karein.")
    
    await state.finish()

# --- ADMIN APPROVAL HANDLERS ---
@dp.callback_query_handler(lambda c: c.data.startswith(('app_', 'rej_')))
async def handle_approval(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_USER_ID:
        await call.answer("Aapke paas permission nahi hai!", show_alert=True)
        return
    
    data_parts = call.data.split('_')
    action = data_parts[0]
    target_user_id = int(data_parts[1])
    
    if action == 'app':
        amount = data_parts[2]
        await call.message.edit_caption(caption=call.message.caption + f"\n\n✅ **Status: APPROVED by Admin**", parse_mode="Markdown")
        try:
            await bot.send_message(target_user_id, f"🎉 Badhai ho! Aapka `{amount}` ka deposit request **Approved** ho gaya hai aur account balance update kar diya gaya hai!")
        except:
            pass
        await call.answer("Deposit approved successfully!")
    else:
        await call.message.edit_caption(caption=call.message.caption + f"\n\n❌ **Status: REJECTED by Admin**", parse_mode="Markdown")
        try:
            await bot.send_message(target_user_id, f"❌ Maaf kijiye, aapka deposit request **Reject** kar diya gaya hai. Kripya support se sampark karein.")
        except:
            pass
        await call.answer("Deposit rejected.")

# --- ADMIN PANEL & BUTTON SETTINGS ---
@dp.callback_query_handler(text="admin_panel")
async def admin_panel(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_USER_ID:
        await call.answer("Aapke paas admin access nahi hai!", show_alert=True)
        return
    
    await call.answer()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 Profit Margin Set", callback_data="btn_set_margin"),
        InlineKeyboardButton("🏦 UPI Badlein", callback_data="btn_set_upi"),
        InlineKeyboardButton("🪙 USDT Badlein", callback_data="btn_set_usdt"),
        InlineKeyboardButton("🔙 Main Menu", callback_data="back_home")
    )
    
    text = (
        f"⚙️ **Admin Control Panel**\n\n"
        f"• Current Markup: `{BOT_SETTINGS['markup_percent']}%`\n"
        f"• Current UPI ID: `{BOT_SETTINGS['upi_id']}`\n"
        f"• Current USDT: `{BOT_SETTINGS['usdt_address']}`\n\n"
        f"Badalne ke liye neeche diye gaye buttons par click karein:"
    )
    await call.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(text="btn_set_upi")
async def ask_new_upi(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_USER_ID: return
    await call.answer()
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="admin_panel"))
    await call.message.edit_text("🏦 Kripya apni **nayi UPI ID** yahan type karke bhej dein:", reply_markup=markup, parse_mode="Markdown")
    await AdminState.waiting_for_new_upi.set()

@dp.message_handler(state=AdminState.waiting_for_new_upi)
async def save_new_upi(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_USER_ID: return
    BOT_SETTINGS["upi_id"] = message.text.strip()
    await state.finish()
    await message.reply(f"✅ UPI ID safalpurvak badal kar `{BOT_SETTINGS['upi_id']}` ho gayi hai!", parse_mode="Markdown")

@dp.callback_query_handler(text="btn_set_usdt")
async def ask_new_usdt(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_USER_ID: return
    await call.answer()
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="admin_panel"))
    await call.message.edit_text("🪙 Kripya apna **naya USDT address** yahan type karke bhej dein:", reply_markup=markup, parse_mode="Markdown")
    await AdminState.waiting_for_new_usdt.set()

@dp.message_handler(state=AdminState.waiting_for_new_usdt)
async def save_new_usdt(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_USER_ID: return
    BOT_SETTINGS["usdt_address"] = message.text.strip()
    await state.finish()
    await message.reply(f"✅ USDT address safalpurvak badal kar `{BOT_SETTINGS['usdt_address']}` ho gaya hai!", parse_mode="Markdown")

@dp.callback_query_handler(text="btn_set_margin")
async def ask_new_margin(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_USER_ID: return
    await call.answer()
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Cancel", callback_data="admin_panel"))
    await call.message.edit_text("📊 Kripya naya **profit margin percentage** number mein bhej dein (Jaise: `35`):", reply_markup=markup, parse_mode="Markdown")
    await AdminState.waiting_for_new_margin.set()

@dp.message_handler(state=AdminState.waiting_for_new_margin)
async def save_new_margin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_USER_ID: return
    try:
        new_val = float(message.text.strip())
        BOT_SETTINGS["markup_percent"] = new_val
        await state.finish()
        await message.reply(f"✅ Profit margin safalpurvak `{new_val}%` set ho gaya hai!", parse_mode="Markdown")
    except:
        await message.reply("❌ Kripya sirf sahi number bhejein (Jaise: 35). Dubara koshish karein ya cancel karein.")

@dp.callback_query_handler(text="back_home", state='*')
async def back_home(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.answer()
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📦 Product Catalog", callback_data="show_catalog"),
        InlineKeyboardButton("🌐 Proxy & VPN Products", callback_data="show_proxies"),
        InlineKeyboardButton("💳 Add Balance / Deposit", callback_data="deposit_menu"),
        InlineKeyboardButton("👤 My Account Balance", callback_data="check_account"),
        InlineKeyboardButton("📋 My Orders", callback_data="check_orders"),
        InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")
    )
    if call.from_user.id == ADMIN_USER_ID:
        markup.add(InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel"))
    await call.message.edit_text("👋 **Main Menu:**", reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(text="check_account")
async def check_account(call: types.CallbackQuery):
    await call.answer()
    url = f"{BASE_URL}?action=get_user"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        await call.message.edit_text(f"👤 **Account & Balance Info:**\n```json\n{data}\n```", parse_mode="Markdown")
    else:
        await call.message.edit_text("❌ Account details fetch karne mein samasya aayi.")

@dp.callback_query_handler(text="show_catalog")
async def show_catalog(call: types.CallbackQuery):
    await call.answer()
    url = f"{BASE_URL}?action=get_catalog"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        await call.message.edit_text(f"🛍️ **Catalog List (Markup: {BOT_SETTINGS['markup_percent']}%):**\n```json\n{str(data)[:800]}\n```", parse_mode="Markdown")
    else:
        await call.message.edit_text("❌ Catalog load karne mein asafalta.")

@dp.callback_query_handler(text="show_proxies")
async def show_proxies(call: types.CallbackQuery):
    await call.answer()
    url = f"{BASE_URL}?action=get_proxy_products"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        await call.message.edit_text(f"🌐 **Proxy & VPN Details:**\n```json\n{str(data)[:800]}\n```", parse_mode="Markdown")
    else:
        await call.message.edit_text("❌ Proxy products load karne mein asafalta.")

@dp.callback_query_handler(text="check_orders")
async def check_orders(call: types.CallbackQuery):
    await call.answer()
    url = f"{BASE_URL}?action=get_orders"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        await call.message.edit_text(f"📋 **Your Orders:**\n```json\n{str(data)[:800]}\n```", parse_mode="Markdown")
    else:
        await call.message.edit_text("❌ Orders fetch karne mein asafalta.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
  
