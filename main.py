import json
import logging
import asyncio
import time
import re
import os
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ================= CONFIGURATION (HARDCODED) =================
BOT_TOKEN = "8752893076:AAHAX6qStla7ktu52jc6FFAJ6ElO25I0DGE"
ADMIN_USER_IDS = [6450199112, 7117775366]
# =============================================================

# --- Flask Server for Render Port Binding ---
server = Flask('')

@server.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    server.run(host='0.0.0.0', port=port)

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
        data[user_id] = {'points': 0, 'username': user.username or user.first_name, 'first_name': user.first_name}
        save_user_data(data)

    kb = [[KeyboardButton("💳 My Account")], [KeyboardButton("🏆 Leaderboard"), KeyboardButton("✅ Tasks")], [KeyboardButton("📞 Support")]]
    msg = data["_settings"].get("start_message", DEFAULT_SETTINGS["start_message"])
    await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    data = load_user_data()
    user_info = data.get(user_id, {'points': 0})
    rank = get_user_rank(user_id, data)
    total_users = len([k for k in data.keys() if k != "_settings"])
    msg = f"👤 *USER ACCOUNT INFO*\n━━━━━━━━━━━━━━━━━━\n🆔 *ID:* `{user_id}`\n💰 *Balance:* `{user_info['points']} Pts`\n🏆 *Global Rank:* `{rank}`\n👥 *Total Users:* `{total_users}`"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_user_data()
    settings = data["_settings"]
    users = {k: v for k, v in data.items() if k != "_settings" and v.get('points', 0) > 0}
    if not users: return await update.message.reply_text("⚠️ *Leaderboard is currently empty!*", parse_mode='Markdown')
    sorted_u = sorted(users.items(), key=lambda x: x[1].get('points', 0), reverse=True)[:settings["leaderboard_size"]]
    msg = f"{settings['leaderboard_header']}\n━━━━━━━━━━━━━━━━━━\n"
    for i, (uid, info) in enumerate(sorted_u, 1):
        msg += f"*{i}.* {info.get('username') or info.get('first_name')} — `{info['points']} Pts`\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- Admin Handlers ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_USER_IDS: return
    kb = [[KeyboardButton("🚀 Fast Add"), KeyboardButton("📢 Broadcast")], [KeyboardButton("➕ Add Points"), KeyboardButton("➖ Remove Points")], [KeyboardButton("📝 Edit Tasks"), KeyboardButton("📞 Edit Support")], [KeyboardButton("⭐ Edit Start"), KeyboardButton("📝 Edit Header")], [KeyboardButton("🔙 Close Admin Panel")]]
    await update.message.reply_text("👑 *ADMIN PANEL*", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def show_full_database(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_USER_IDS: return
    data = load_user_data()
    users = {k: v for k, v in data.items() if k != "_settings"}
    if not users: return await update.message.reply_text("📭 Empty.")
    msg = "📂 *USER DATABASE*\n"
    for uid, info in sorted(users.items(), key=lambda x: x[1].get('points', 0), reverse=True):
        line = f"• `{uid}` | `{info.get('points', 0)}` Pts\n"
        if len(msg) + len(line) > 4000:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
        msg += line
    if msg: await update.message.reply_text(msg, parse_mode='Markdown')



async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_USER_IDS: return
    text, data, mode = update.message.text, load_user_data(), context.user_data.get('mode')

    # Fast Add Initiation
    if text == "🚀 Fast Add":
        context.user_data['mode'] = 'fa_pts'
        return await update.message.reply_text("🔢 *Points to add?*")
    elif text == "✅ Done (Process)":
        if admin_id in fast_add_cache:
            info = fast_add_cache[admin_id]
            for uid in info['ids']:
                if uid not in data: data[uid] = {'points': 0, 'username': f"User {uid}", 'first_name': "N/A"}
                data[uid]['points'] += info['points']
            save_user_data(data)
            await update.message.reply_text(f"✅ Success: Updated {len(info['ids'])} users.")
            del fast_add_cache[admin_id]
            context.user_data.clear()
            return await admin_panel(update, context)

    # Manual Add/Remove Buttons
    elif text == "➕ Add Points": context.user_data['mode'] = 'manual_add'; return await update.message.reply_text("Send: `UserID Points`")
    elif text == "➖ Remove Points": context.user_data['mode'] = 'manual_rem'; return await update.message.reply_text("Send: `UserID Points`")

    # Broadcast Start
    elif text == "📢 Broadcast":
        context.user_data['mode'] = 'bc_input'
        return await update.message.reply_text("📢 *Enter the message to broadcast:*")

    # Broadcast Confirm Logic
    elif mode == 'bc_input':
        context.user_data['bc_msg'] = text
        context.user_data['mode'] = 'bc_confirm'
        await update.message.reply_text(f"📢 *PREVIEW:*\n\n*{text}*\n\n✅ Confirm to send?", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Confirm & Send")], [KeyboardButton("🔙 Close Admin Panel")]], resize_keyboard=True), parse_mode='Markdown')
        return

    elif mode == 'bc_confirm':
        if text == "✅ Confirm & Send":
            msg_to_send = f"*{context.user_data.get('bc_msg')}*"
            count = 0
            for u in [k for k in data.keys() if k != "_settings"]:
                try: await context.bot.send_message(u, msg_to_send, parse_mode='Markdown'); count += 1
                except: pass
            await update.message.reply_text(f"✅ *Broadcast Sent to {count} users!*", parse_mode='Markdown')
            context.user_data.clear()
            return await admin_panel(update, context)

    # Processing Modes
    if mode == 'fa_pts':
        try:
            fast_add_cache[admin_id] = {"points": int(text), "ids": set()}
            context.user_data['mode'] = 'fa_collect'
            await update.message.reply_text("📥 Forward messages then click Done.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Done (Process)")]], resize_keyboard=True))
        except: await update.message.reply_text("Enter number!")
    elif mode == 'fa_collect' and text != "✅ Done (Process)":
        for fid in re.findall(r'(\d{8,12})', text): fast_add_cache[admin_id]['ids'].add(fid)
        await update.message.reply_text(f"📥 Total Unique IDs: {len(fast_add_cache[admin_id]['ids'])}")
    
    elif mode in ['manual_add', 'manual_rem']:
        try:
            uid, pts = text.split()
            pts = int(pts)
            if uid not in data: data[uid] = {'points': 0, 'username': f"User {uid}", 'first_name': "N/A"}
            if mode == 'manual_add': data[uid]['points'] += pts
            else: data[uid]['points'] = max(0, data[uid]['points'] - pts)
            save_user_data(data)
            await update.message.reply_text(f"✅ User `{uid}` updated. New Balance: `{data[uid]['points']}`", parse_mode='Markdown')
            context.user_data.clear()
            await admin_panel(update, context)
        except: await update.message.reply_text("❌ Galat format! Use: `UserID Points`")

    elif text == "🔙 Close Admin Panel": context.user_data.clear(); await start(update, context)
    elif text == "📝 Edit Tasks": context.user_data['mode'] = 'et'; await update.message.reply_text("New Tasks:")
    elif text == "📞 Edit Support": context.user_data['mode'] = 'es'; await update.message.reply_text("New Support:")
    elif text == "⭐ Edit Start": context.user_data['mode'] = 'e_st'; await update.message.reply_text("New Start Msg:")
    elif text == "📝 Edit Header": context.user_data['mode'] = 'e_hd'; await update.message.reply_text("New Header:")
    elif mode and mode not in ['bc_input', 'bc_confirm']:
        m = context.user_data.pop('mode')
        if m == 'et': data["_settings"]["tasks_message"] = text
        elif m == 'es': data["_settings"]["support_message"] = text
        elif m == 'e_st': data["_settings"]["start_message"] = text
        elif m == 'e_hd': data["_settings"]["leaderboard_header"] = text
        save_user_data(data)
        await update.message.reply_text("✅ Updated Successfully!")
        await admin_panel(update, context)

# --- Main ---
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("database", show_full_database))
    app.add_handler(MessageHandler(filters.Regex(r'💳 My Account'), my_account))
    app.add_handler(MessageHandler(filters.Regex(r'🏆 Leaderboard'), show_leaderboard))
    app.add_handler(MessageHandler(filters.Regex(r'✅ Tasks'), lambda u, c: u.message.reply_text(load_user_data()["_settings"]["tasks_message"], parse_mode='Markdown')))
    app.add_handler(MessageHandler(filters.Regex(r'📞 Support'), lambda u, c: u.message.reply_text(load_user_data()["_settings"]["support_message"], parse_mode='Markdown')))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.User(ADMIN_USER_IDS), handle_admin_actions))
    print("✅ Bot is Online!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
