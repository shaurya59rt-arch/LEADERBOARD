import json
import logging
import asyncio
import time
import re
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ================= CONFIGURATION (HARDCODED) =================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Apna Token yahan daalein
ADMIN_USER_IDS = [123456789, 987654321]  # Apni Admin IDs yahan daalein
# =============================================================

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DATA_FILE = 'user_db.json'
DEFAULT_SETTINGS = {
    "leaderboard_size": 10,
    "leaderboard_header": "🏆 *MONKXZ GLOBAL LEADERBOARD* 🏆", 
    "support_message": "📞 *Support:* @YourSupportUsername",
    "start_message": "🚀 *Welcome to MONKXZ LEADERBOARD BOT!*\n\nEarn points by completing tasks and climb the global rank.",
    "tasks_message": "📝 *VALID TASKS TO EARN POINTS:*\n\n1. Subscribe our Channel\n2. Share with 5 Friends\n3. Use our official bot daily!"
}

fast_add_cache = {} 

# --- Database Management ---
def load_user_data():
    if not os.path.exists(DATA_FILE):
        return {"_settings": DEFAULT_SETTINGS}
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            if "_settings" not in data: 
                data["_settings"] = DEFAULT_SETTINGS
            return data
    except Exception as e:
        logger.error(f"Error loading DB: {e}")
        return {"_settings": DEFAULT_SETTINGS}

def save_user_data(data):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving DB: {e}")

def get_user_rank(user_id, data):
    users = {k: v for k, v in data.items() if k != "_settings"}
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('points', 0), reverse=True)
    for index, (uid, info) in enumerate(sorted_users, 1):
        if uid == str(user_id): 
            return index
    return "N/A"

# --- Core Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = str(user.id)
    data = load_user_data()
    
    if user_id not in data and user.id not in ADMIN_USER_IDS:
        data[user_id] = {
            'points': 0,
            'username': user.username or user.first_name,
            'first_name': user.first_name
        }
        save_user_data(data)

    kb = [
        [KeyboardButton("💳 My Account")],
        [KeyboardButton("🏆 Leaderboard"), KeyboardButton("✅ Tasks")],
        [KeyboardButton("📞 Support")]
    ]
    
    msg = data["_settings"].get("start_message", DEFAULT_SETTINGS["start_message"])
    await update.message.reply_text(
        msg, 
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), 
        parse_mode='Markdown'
    )

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    data = load_user_data()
    user_info = data.get(user_id, {'points': 0})
    rank = get_user_rank(user_id, data)
    total_users = len([k for k in data.keys() if k != "_settings"])

    msg = (
        f"👤 *USER ACCOUNT INFO*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 *ID:* `{user_id}`\n"
        f"💰 *Balance:* `{user_info['points']} Pts`\n"
        f"🏆 *Global Rank:* `{rank}`\n"
        f"👥 *Total Users:* `{total_users}`"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_user_data()
    settings = data["_settings"]
    users = {k: v for k, v in data.items() if k != "_settings" and v.get('points', 0) > 0}
    
    if not users:
        await update.message.reply_text("⚠️ *Leaderboard is currently empty!*", parse_mode='Markdown')
        return

    sorted_u = sorted(users.items(), key=lambda x: x[1].get('points', 0), reverse=True)[:settings["leaderboard_size"]]
    
    msg = f"{settings['leaderboard_header']}\n━━━━━━━━━━━━━━━━━━\n"
    for i, (uid, info) in enumerate(sorted_u, 1):
        name = info.get('username') or info.get('first_name') or f"User {uid}"
        msg += f"*{i}.* {name} — `{info['points']} Pts`\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- Admin Engine ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_USER_IDS: return
    
    kb = [
        [KeyboardButton("🚀 Fast Add"), KeyboardButton("📢 Broadcast")],
        [KeyboardButton("➕ Add Points"), KeyboardButton("➖ Remove Points")],
        [KeyboardButton("📝 Edit Tasks"), KeyboardButton("📞 Edit Support")],
        [KeyboardButton("⭐ Edit Start"), KeyboardButton("📝 Edit Header")],
        [KeyboardButton("🔙 Close Admin Panel")]
    ]
    await update.message.reply_text(
        "👑 *ADMIN COMMAND CENTRE*\n\n"
        "• `/database` : View all users\n"
        "• `/add_id <id> <pts>` : Manual add",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), 
        parse_mode='Markdown'
    )

async def show_full_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_USER_IDS: return
    data = load_user_data()
    users = {k: v for k, v in data.items() if k != "_settings"}
    
    if not users:
        await update.message.reply_text("📭 Database is empty.")
        return

    header = "📂 *USER DATABASE EXPORT*\n━━━━━━━━━━━━━━━━━━\n"
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('points', 0), reverse=True)
    
    current_msg = header
    for uid, info in sorted_users:
        line = f"• `{uid}` | `{info.get('points', 0)}` Pts\n"
        if len(current_msg) + len(line) > 4000:
            await update.message.reply_text(current_msg, parse_mode='Markdown')
            current_msg = ""
        current_msg += line
    
    if current_msg:
        await update.message.reply_text(current_msg, parse_mode='Markdown')

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_USER_IDS: return
    
    text = update.message.text
    data = load_user_data()
    mode = context.user_data.get('mode')

    # Fast Add Initiation
    if text == "🚀 Fast Add":
        context.user_data['mode'] = 'fa_pts'
        await update.message.reply_text("🔢 *Points to add?* (Send number only)")
        return
    
    elif text == "✅ Done (Process)":
        if admin_id in fast_add_cache:
            info = fast_add_cache[admin_id]
            for uid in info['ids']:
                if uid not in data: data[uid] = {'points': 0, 'username': f"User {uid}", 'first_name': "N/A"}
                data[uid]['points'] += info['points']
            save_user_data(data)
            await update.message.reply_text(f"✅ Successfully added `{info['points']}` points to `{len(info['ids'])}` users.")
            del fast_add_cache[admin_id]
            context.user_data.clear()
            await admin_panel(update, context)
        return

    # Processing Input Modes
    if mode == 'fa_pts':
        try:
            fast_add_cache[admin_id] = {"points": int(text), "ids": set()}
            context.user_data['mode'] = 'fa_collect'
            await update.message.reply_text(f"💰 Points set to `{text}`. Now forward the messages.\n\nClick **Done** when finished.", 
                                           reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Done (Process)")]], resize_keyboard=True))
        except: await update.message.reply_text("❌ Please send a valid number.")
        return

    if mode == 'fa_collect' and text != "✅ Done (Process)":
        found = re.findall(r'(\d{8,12})', text)
        if found:
            for fid in found: fast_add_cache[admin_id]['ids'].add(fid)
            await update.message.reply_text(f"📥 Found: `{len(found)}` | Total Unique: `{len(fast_add_cache[admin_id]['ids'])}`")
        return

    # Menu Actions
    if text == "🔙 Close Admin Panel":
        context.user_data.clear()
        await start(update, context)
    elif text == "📝 Edit Tasks": context.user_data['mode'] = 'e_tasks'; await update.message.reply_text("Send new Tasks text:")
    elif text == "📞 Edit Support": context.user_data['mode'] = 'e_supp'; await update.message.reply_text("Send new Support text:")
    elif text == "⭐ Edit Start": context.user_data['mode'] = 'e_start'; await update.message.reply_text("Send new Start message:")
    elif text == "📝 Edit Header": context.user_data['mode'] = 'e_head'; await update.message.reply_text("Send new Header text:")
    elif text == "📢 Broadcast": context.user_data['mode'] = 'bc'; await update.message.reply_text("Send message to broadcast:")
    
    elif mode:
        m = context.user_data.pop('mode')
        if m == 'e_tasks': data["_settings"]["tasks_message"] = text
        elif m == 'e_supp': data["_settings"]["support_message"] = text
        elif m == 'e_start': data["_settings"]["start_message"] = text
        elif m == 'e_head': data["_settings"]["leaderboard_header"] = text
        elif m == 'bc':
            for u in [k for k in data.keys() if k != "_settings"]:
                try: await context.bot.send_message(u, text, parse_mode='Markdown')
                except: pass
        save_user_data(data)
        await update.message.reply_text("✅ Setting Updated Successfully!")
        await admin_panel(update, context)

# --- Main App ---
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: Please set your BOT_TOKEN in the code!")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("database", show_full_database))
    
    # Keyboard Buttons
    app.add_handler(MessageHandler(filters.Regex(r'💳 My Account'), my_account))
    app.add_handler(MessageHandler(filters.Regex(r'🏆 Leaderboard'), show_leaderboard))
    app.add_handler(MessageHandler(filters.Regex(r'✅ Tasks'), lambda u, c: u.message.reply_text(load_user_data()["_settings"]["tasks_message"], parse_mode='Markdown')))
    app.add_handler(MessageHandler(filters.Regex(r'📞 Support'), lambda u, c: u.message.reply_text(load_user_data()["_settings"]["support_message"], parse_mode='Markdown')))

    # Admin Filtered Logic
    admin_filter = (filters.ChatType.PRIVATE & filters.User(ADMIN_USER_IDS))
    app.add_handler(MessageHandler(admin_filter, handle_admin_actions))

    print("✅ Bot is Online and Professional!")
    app.run_polling()

if __name__ == "__main__":
    main()
