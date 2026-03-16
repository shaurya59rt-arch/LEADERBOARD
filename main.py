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

# ================= CONFIGURATION =================
BOT_TOKEN = "8752893076:AAHAX6qStla7ktu52jc6FFAJ6ElO25I0DGE"
ADMIN_USER_IDS = [6450199112, 7117775366]
DATA_FILE = 'user_db.json'
db_lock = threading.Lock() 
# =================================================

server = Flask('')

@server.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    server.run(host='0.0.0.0', port=port)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "leaderboard_size": 10,
    "leaderboard_header": "🏆 *MONKXZ GLOBAL LEADERBOARD* 🏆", 
    "support_message": "📞 *Support:* @YourSupportUsername",
    "start_message": "🚀 *Welcome to MONKXZ LEADERBOARD BOT!*\n\nEarn points by completing tasks and climb the global rank.",
    "tasks_message": "📝 *VALID TASKS TO EARN POINTS:*\n\n1. Subscribe our Channel\n2. Share with 5 Friends\n3. Use our official bot daily!"
}

fast_add_cache = {} 
auto_merge_db = {} # Format: {source_id: target_id}

# --- Helper Logic ---
def get_final_target(uid):
    return auto_merge_db.get(str(uid), str(uid))

# --- Database Management ---
def load_user_data():
    with db_lock:
        if not os.path.exists(DATA_FILE): return {"_settings": DEFAULT_SETTINGS}
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                if "_settings" not in data: data["_settings"] = DEFAULT_SETTINGS
                return data
        except Exception as e:
            logger.error(f"Error loading DB: {e}")
            return {"_settings": DEFAULT_SETTINGS}

def save_user_data(data):
    with db_lock:
        try:
            with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=4)
        except Exception as e: logger.error(f"Error saving DB: {e}")

def get_user_rank(user_id, data):
    users = {k: v for k, v in data.items() if k != "_settings"}
    sorted_users = sorted(users.items(), key=lambda x: x[1].get('points', 0), reverse=True)
    for index, (uid, info) in enumerate(sorted_users, 1):
        if uid == str(user_id): return index
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
    balance = round(user_info.get('points', 0), 2)
    msg = f"👤 *USER ACCOUNT INFO*\n━━━━━━━━━━━━━━━━━━\n🆔 *ID:* `{user_id}`\n💰 *Balance:* `{balance} Pts`\n🏆 *Global Rank:* `{rank}`\n👥 *Total Users:* `{total_users}`"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_user_data()
    settings = data["_settings"]
    users = {k: v for k, v in data.items() if k != "_settings"}
    if not users: return await update.message.reply_text("⚠️ *Leaderboard is currently empty!*", parse_mode='Markdown')
    sorted_u = sorted(users.items(), key=lambda x: x[1].get('points', 0), reverse=True)[:settings["leaderboard_size"]]
    msg = f"{settings['leaderboard_header']}\n━━━━━━━━━━━━━━━━━━\n"
    for i, (uid, info) in enumerate(sorted_u, 1):
        name = info.get('username') or info.get('first_name') or f"User {uid}"
        msg += f"*{i}.* {name} — `{round(info.get('points', 0), 2)} Pts`\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- Admin Handlers ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_USER_IDS: return
    kb = [
        [KeyboardButton("🚀 Fast Add"), KeyboardButton("✨ Special Add")],
        [KeyboardButton("🔗 Set Auto-Merge"), KeyboardButton("🔗 Remove Auto-Merge")],
        [KeyboardButton("🔗 Check Auto-Merge Status")],
        [KeyboardButton("📢 Broadcast"), KeyboardButton("➕ Add Points")],
        [KeyboardButton("➖ Remove Points"), KeyboardButton("📝 Edit Tasks")],
        [KeyboardButton("📞 Edit Support"), KeyboardButton("⭐ Edit Start")],
        [KeyboardButton("📝 Edit Header"), KeyboardButton("🔙 Close Admin Panel")]
    ]
    await update.message.reply_text("👑 *ADMIN PANEL*", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode='Markdown')

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    if admin_id not in ADMIN_USER_IDS: return
    text, data, mode = update.message.text, load_user_data(), context.user_data.get('mode')

    # --- Auto Merge Handlers ---
    if text == "🔗 Set Auto-Merge":
        context.user_data['mode'] = 'set_merge'
        return await update.message.reply_text("Format: `id1-id2-id3--targetid`")
    elif mode == 'set_merge':
        try:
            sources, target = text.split('--')
            src_list = [s.strip() for s in sources.split('-')]
            conflicts = [s for s in src_list if s in auto_merge_db]
            if conflicts: await update.message.reply_text(f"⚠️ Conflict! IDs already in merge: {conflicts}")
            else:
                for s in src_list: auto_merge_db[s] = target.strip()
                await update.message.reply_text(f"✅ Merged: {src_list} -> {target}")
        except: await update.message.reply_text("❌ Format Error! Use `id1-id2--targetid`")
        context.user_data.clear(); return await admin_panel(update, context)
    
    elif text == "🔗 Check Auto-Merge Status":
        if not auto_merge_db: return await update.message.reply_text("⚠️ No active merges.")
        msg = "📊 *ACTIVE MERGES*\n━━━━━━━━━━━━━━━━━━\n"
        for s, t in auto_merge_db.items(): msg += f"🔗 `{s}` -> `Target: {t}`\n"
        return await update.message.reply_text(msg, parse_mode='Markdown')

    elif text == "🔗 Remove Auto-Merge":
        context.user_data['mode'] = 'rem_merge'
        return await update.message.reply_text("Enter Source ID to remove:")
    elif mode == 'rem_merge':
        if text in auto_merge_db:
            del auto_merge_db[text]
            await update.message.reply_text(f"✅ Merge for {text} removed.")
        else: await update.message.reply_text("❌ ID not found.")
        context.user_data.clear(); return await admin_panel(update, context)

    # --- Special/Fast/Manual Add ---
    if text == "✨ Special Add":
        context.user_data['mode'] = 'special_add'
        return await update.message.reply_text("Paste your list (ID Points):\nExample:\n`7880740015 3.33`")
    elif mode == 'special_add':
        lines = text.split('\n')
        count = 0
        for line in lines:
            try:
                parts = line.split()
                if len(parts) >= 2:
                    target = get_final_target(parts[0])
                    pts = float(parts[1])
                    if target not in data: data[target] = {'points': 0, 'username': f"User {target}", 'first_name': "N/A"}
                    data[target]['points'] += pts
                    count += 1
            except: continue
        save_user_data(data)
        await update.message.reply_text(f"✅ Special Add Success: Updated {count} entries."); context.user_data.clear(); return await admin_panel(update, context)

    elif text == "🚀 Fast Add":
        context.user_data['mode'] = 'fa_pts'
        return await update.message.reply_text("🔢 *Points to add?*")
    
    elif mode == 'fa_pts':
        try:
            fast_add_cache[admin_id] = {"points": float(text), "ids": set()}
            context.user_data['mode'] = 'fa_collect'
            await update.message.reply_text("📥 Forward messages or type IDs, then click Done.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Done (Process)")]], resize_keyboard=True))
        except: await update.message.reply_text("Enter valid number!")
    
    elif mode == 'fa_collect' and text != "✅ Done (Process)":
        found = re.findall(r'(\d+)', text)
        for f in found: fast_add_cache[admin_id]['ids'].add(f)
        await update.message.reply_text(f"📥 Unique Entries: {len(fast_add_cache[admin_id]['ids'])}")
    
    elif text == "✅ Done (Process)":
        if admin_id in fast_add_cache:
            info = fast_add_cache[admin_id]
            for raw_entry in info['ids']:
                target = get_final_target(raw_entry)
                if target not in data: data[target] = {'points': 0, 'username': f"User {target}", 'first_name': "N/A"}
                data[target]['points'] += info['points']
            save_user_data(data); await update.message.reply_text("✅ Success: Updated users."); del fast_add_cache[admin_id]; context.user_data.clear(); return await admin_panel(update, context)

    # --- Manual Add/Remove ---
    elif text in ["➕ Add Points", "➖ Remove Points"]:
        context.user_data['mode'] = 'manual_pts'
        context.user_data['op'] = 'add' if text == "➕ Add Points" else 'sub'
        return await update.message.reply_text("Send: `UserID Points`")
    elif mode == 'manual_pts':
        try:
            uid_raw, pts = text.split(); pts = float(pts)
            target = get_final_target(uid_raw)
            if target not in data: data[target] = {'points': 0, 'username': f"User {target}", 'first_name': "N/A"}
            if context.user_data['op'] == 'add': data[target]['points'] += pts
            else: data[target]['points'] = max(0, data[target]['points'] - pts)
            save_user_data(data); await update.message.reply_text("✅ Updated."); context.user_data.clear(); return await admin_panel(update, context)
        except: await update.message.reply_text("❌ Error! Format: `UserID Points`")

    # --- Broadcast & Settings ---
    elif text == "📢 Broadcast":
        context.user_data['mode'] = 'bc_input'
        return await update.message.reply_text("📢 *Enter message to broadcast:*")
    elif mode == 'bc_input':
        context.user_data['bc_msg'] = text; context.user_data['mode'] = 'bc_confirm'
        await update.message.reply_text(f"📢 *PREVIEW:*\n\n*{text}*", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Confirm & Send")]], resize_keyboard=True))
    elif mode == 'bc_confirm' and text == "✅ Confirm & Send":
        msg = f"*{context.user_data.get('bc_msg')}*"
        count = 0
        for u in [k for k in data.keys() if k != "_settings"]:
            try: await context.bot.send_message(u, msg, parse_mode='Markdown'); count += 1
            except: pass
        await update.message.reply_text(f"✅ Sent to {count} users!"); context.user_data.clear(); return await admin_panel(update, context)

    elif text == "🔙 Close Admin Panel": context.user_data.clear(); await start(update, context)
    elif text == "📝 Edit Tasks": context.user_data['mode'] = 'et'; await update.message.reply_text("New Tasks:")
    elif text == "📞 Edit Support": context.user_data['mode'] = 'es'; await update.message.reply_text("New Support:")
    elif text == "⭐ Edit Start": context.user_data['mode'] = 'e_st'; await update.message.reply_text("New Start Msg:")
    elif text == "📝 Edit Header": context.user_data['mode'] = 'e_hd'; await update.message.reply_text("New Header:")
    elif mode in ['et', 'es', 'e_st', 'e_hd']:
        if mode == 'et': data["_settings"]["tasks_message"] = text
        elif mode == 'es': data["_settings"]["support_message"] = text
        elif mode == 'e_st': data["_settings"]["start_message"] = text
        elif mode == 'e_hd': data["_settings"]["leaderboard_header"] = text
        save_user_data(data); await update.message.reply_text("✅ Updated!"); context.user_data.clear(); await admin_panel(update, context)

# --- Main ---
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.Regex(r'💳 My Account'), my_account))
    app.add_handler(MessageHandler(filters.Regex(r'🏆 Leaderboard'), show_leaderboard))
    app.add_handler(MessageHandler(filters.Regex(r'✅ Tasks'), lambda u, c: u.message.reply_text(load_user_data()["_settings"]["tasks_message"], parse_mode='Markdown')))
    app.add_handler(MessageHandler(filters.Regex(r'📞 Support'), lambda u, c: u.message.reply_text(load_user_data()["_settings"]["support_message"], parse_mode='Markdown')))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.User(ADMIN_USER_IDS), handle_admin_actions))
    print("✅ Bot is Online with Full Features!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
