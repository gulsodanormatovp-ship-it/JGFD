import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Token va Admin ID
TOKEN = "SIZNING_BOT_TOKENINGIZ"
ADMIN_ID = 123456789  # O'z Telegram ID raqamingizni yozing

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# --- BAZA BILAN ISHLASH ---
def db_connect():
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            balance INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            channel_link TEXT,
            channel_name TEXT
        )
    """)
    conn.commit()
    conn.close()

db_connect()

def get_setting(key, default=""):
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# --- FSM (STATE) HOLATLAR ---
class AdminState(StatesGroup):
    user_id = State()
    amount = State()
    card = State()
    channel_id = State()
    channel_link = State()
    channel_name = State()
    broadcast_text = State()

class BuyState(StatesGroup):
    waiting_for_username = State()

# --- MAJBURIY OBUNANI TEKSHIRISH ---
async def check_subscription(user_id: int) -> bool:
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id, channel_link, channel_name FROM channels")
    channels = cursor.fetchall()
    conn.close()

    for ch_id, ch_link, ch_name in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            pass
    return True

# --- /START BUYRUG'I ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    # Obunani tekshirish
    if not await check_subscription(user_id):
        conn = sqlite3.connect("store_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT channel_link, channel_name FROM channels")
        channels = cursor.fetchall()
        conn.close()
        
        kb_list = []
        for link, name in channels:
            kb_list.append([InlineKeyboardButton(text=f"📢 {name}", url=link)])
        kb_list.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
        
        await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))
        return

    # Foydalanuvchini bazaga qo'shish
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name, username, balance) VALUES (?, ?, ?, 0)", 
                   (user_id, message.from_user.full_name, message.from_user.username))
    conn.commit()
    conn.close()

    await show_main_menu(message)

async def show_main_menu(message_or_callback, edit=False):
    user_id = message_or_callback.from_user.id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="shop_stars"),
         InlineKeyboardButton(text="💎 Telegram Premium", callback_data="shop_premium")],
        [InlineKeyboardButton(text="🎁 Telegram Gifts", callback_data="shop_gifts"),
         InlineKeyboardButton(text="📞 Virtual Raqam", callback_data="shop_numbers")],
        [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="top_up"),
         InlineKeyboardButton(text="👤 Profil", callback_data="profile")]
    ])
    
    if user_id == ADMIN_ID:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel")])

    text = f"🔥 **Store Zen Tp Bot** — raqamli xizmatlar olami!\nKerakli bo'limni tanlang[cite: 1, 10]:"
    
    if edit:
        await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "check_sub")
async def verify_sub(callback: types.CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await show_main_menu(callback)
    else:
        await callback.answer("❌ Hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)

# --- PROFIL ---
@dp.callback_query(F.data == "profile")
async def user_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, full_name, username FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()

    text = (f"👤 **Ism:** {user[1]}\n"
            f"🔗 **Username:** @{user[2] if user[2] else 'Mavjud emas'}\n"
            f"🆔 **ID:** `{user_id}`\n"
            f"💰 **Balans:** {user[0]:,} so'm")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# --- DO'KON BO'LIMLARI (STARS, PREMIUM, GIFTS) ---
@dp.callback_query(F.data.in_({"shop_stars", "shop_premium", "shop_gifts", "shop_numbers"}))
async def shop_sections(callback: types.CallbackQuery):
    action = callback.data
    titles = {
        "shop_stars": "⭐ **Telegram Stars do'koni**\nMiqdorni tanlang:",
        "shop_premium": "💎 **Telegram Premium obunasi**\nMuddatingizni tanlang:",
        "shop_gifts": "🎁 **Telegram Gifts (Sovg'alar)**\nSovg'ani tanlang:",
        "shop_numbers": "📞 **Virtual raqamlar**\nDavlatni tanlang:"
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="50 ta - 9,400 so'm", callback_data="buy_item_50")],
        [InlineKeyboardButton(text="100 ta - 18,800 so'm", callback_data="buy_item_100")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]
    ])
    await callback.message.edit_text(titles[action], reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("buy_item_"))
async def process_buy(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(item=callback.data)
    await callback.message.edit_text("👤 Stars yuboriladigan Telegram Username kiriting (masalan: `@username`):",
                                     reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]]))
    await state.set_state(BuyState.waiting_for_username)

@dp.message(BuyState.waiting_for_username)
async def finish_buy(message: types.Message, state: FSMContext):
    username = message.text
    await message.answer(f"✅ Buyurtmangiz qabul qilindi!\nQabul qiluvchi: {username}\nTez orada avtomatik bajariladi.")
    await state.clear()
    await show_main_menu(message)

# --- BALANDNI TO'LDIRISH ---
@dp.callback_query(F.data == "top_up")
async def top_up_balance(callback: types.CallbackQuery):
    card = get_setting("card_number", "Karta belgilanmagan")
    text = (f"💳 **Balansni to'ldirish uchun karta:**\n\n"
            f"`{card}`\n\n"
            f"Pulni o'tkazib, chekni adminga yuboring.")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# --- ⚙️ ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton(text="➕ / ➖ Balansni o'zgartirish", callback_data="adm_balance")],
        [InlineKeyboardButton(text="💳 Karta raqamni o'zgartirish", callback_data="adm_card")],
        [InlineKeyboardButton(text="📢 Majburiy obuna kanali qo'shish", callback_data="adm_add_channel")],
        [InlineKeyboardButton(text="✉️ Xabar tarqatish (Broadcast)", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="back_home")]
    ])
    await callback.message.edit_text("⚙️ **To'liq boshqaruv Admin Paneli:**", reply_markup=keyboard, parse_mode="Markdown")

# Statistika
@dp.callback_query(F.data == "adm_stats")
async def adm_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    conn.close()

    text = f"📊 **Bot Statistikasi:**\n\n👥 Jami foydalanuvchilar: {users_count} ta"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_panel")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")

# Karta o'zgartirish
@dp.callback_query(F.data == "adm_card")
async def adm_card(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    current_card = get_setting("card_number", "Mavjud emas")
    await callback.message.answer(f"Hozirgi karta: `{current_card}`\n\nYangi karta raqami va egasini yuboring:")
    await state.set_state(AdminState.card)

@dp.message(AdminState.card)
async def save_card(message: types.Message, state: FSMContext):
    set_setting("card_number", message.text)
    await message.answer("✅ Karta muvaffaqiyatli yangilandi!")
    await state.clear()

# Balans Plus / Minus
@dp.callback_query(F.data == "adm_balance")
async def adm_balance(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Foydalanuvchining Telegram ID raqamini kiriting:")
    await state.set_state(AdminState.user_id)

@dp.message(AdminState.user_id)
async def adm_get_userid(message: types.Message, state: FSMContext):
    await state.update_data(user_id=message.text)
    await message.answer("Summani kiriting (Balansdan ayirish uchun oldiga `-` qo'ying, masalan: `-10000` yoki `50000`):")
    await state.set_state(AdminState.amount)

@dp.message(AdminState.amount)
async def adm_set_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    target_user = int(data['user_id'])
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("Faqat raqam kiriting!")
        return

    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user))
    conn.commit()
    conn.close()

    await message.answer(f"✅ Foydalanuvchi balansi o'zgartirildi ({amount:+} so'm)!")
    await state.clear()

# Majburiy obuna kanalini qo'shish
@dp.callback_query(F.data == "adm_add_channel")
async def adm_add_channel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("Kanal ID raqamini kiriting (masalan: `-100123456789`):")
    await state.set_state(AdminState.channel_id)

@dp.message(AdminState.channel_id)
async def get_ch_id(message: types.Message, state: FSMContext):
    await state.update_data(ch_id=message.text)
    await message.answer("Kanal havolasini (linkini) kiriting:")
    await state.set_state(AdminState.channel_link)

@dp.message(AdminState.channel_link)
async def get_ch_link(message: types.Message, state: FSMContext):
    await state.update_data(ch_link=message.text)
    await message.answer("Kanal nomini kiriting:")
    await state.set_state(AdminState.channel_name)

@dp.message(AdminState.channel_name)
async def get_ch_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = sqlite3.connect("store_bot.db")
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO channels (channel_id, channel_link, channel_name) VALUES (?, ?, ?)",
                   (data['ch_id'], data['ch_link'], message.text))
    conn.commit()
    conn.close()
    await message.answer("✅ Majburiy obuna kanali muvaffaqiyatli qo'shildi!")
    await state.clear()

# Orqaga qaytish
@dp.callback_query(F.data == "back_home")
async def back_to_home(callback: types.CallbackQuery):
    await show_main_menu(callback, edit=True)

if __name__ == "__main__":
    print("Bot dahshatli tezlikda ishga tushdi...")
    dp.run_polling(bot)
