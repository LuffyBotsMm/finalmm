#!/usr/bin/env python3
"""
FinalMM Pro Edition — LB Escrow Bot
Fully automatic, 24×7, styled Telegram escrow manager
"""

import os, time, random, sqlite3, logging, threading, requests
from functools import wraps
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler

# ───── CONFIG ─────
BOT_TOKEN = "8273619720:AAEbCOxf1Ycx4OTFS8ZzFbJimw1tba0V8Y0"
OWNER_ID = 6847499628
LOG_CHANNEL = -1003089374759
PW_BY = "@LuffyBots"
DB_FILE = "finalmm.db"
# ─────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ───── DATABASE ─────
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id TEXT UNIQUE,
        buyer TEXT,
        seller TEXT,
        amount REAL,
        escrower TEXT,
        status TEXT,
        created_at INTEGER,
        closed_at INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )""")
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
    conn.commit()
    conn.close()

def db_exec(q, p=(), fetch=False):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(q, p)
    data = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return data

init_db()

# ───── UTILITIES ─────
def is_admin(uid): 
    if uid == OWNER_ID: return True
    return bool(db_exec("SELECT 1 FROM admins WHERE user_id=?", (uid,), fetch=True))

def admin_only(func):
    @wraps(func)
    def wrap(update, context, *a, **kw):
        if not update.effective_user: return
        if not is_admin(update.effective_user.id):
            update.message.reply_text("⚠️ Only Admins can use this command.")
            return
        return func(update, context, *a, **kw)
    return wrap

def owner_only(func):
    @wraps(func)
    def wrap(update, context, *a, **kw):
        if not update.effective_user: return
        if update.effective_user.id != OWNER_ID:
            update.message.reply_text("❌ Only Owner can use this command.")
            return
        return func(update, context, *a, **kw)
    return wrap

def trade_id(): return f"TID{random.randint(100000,999999)}"

def send_log(context, text):
    try: context.bot.send_message(LOG_CHANNEL, text, parse_mode=ParseMode.HTML)
    except: pass

# ───── COMMANDS ─────
def start(update, context):
    update.message.reply_text(
        "✨ <b>LB FinalMM Escrow Bot</b> is live!\n\n"
        "Use /add <amount> <@buyer> <@seller> to create a deal.\n"
        "Use /close <tid> or /close <amount> <@buyer> <@seller> to close.\n\n"
        "For help: /adminlist /status /stats /mydeals /topuser",
        parse_mode=ParseMode.HTML)

@admin_only
def add(update, context):
    args = context.args
    if len(args) < 3:
        update.message.reply_text("Usage: /add <amount> <@buyer> <@seller>")
        return
    amount, buyer, seller = args[0], args[1], args[2]
    tid = trade_id()
    escrower = "@" + (update.effective_user.username or str(update.effective_user.id))
    db_exec("INSERT INTO deals (trade_id,buyer,seller,amount,escrower,status,created_at) VALUES (?,?,?,?,?,?,?)",
        (tid, buyer, seller, amount, escrower, "OPEN", int(time.time())))
    msg = (f"💼 <b>𝗡𝗘𝗪 𝗗𝗘𝗔𝗟 𝗖𝗥𝗘𝗔𝗧𝗘𝗗</b>\n\n"
           f"💰 <b>Amount:</b> ₹{amount}\n🤝 <b>Buyer:</b> {buyer}\n🏷️ <b>Seller:</b> {seller}\n"
           f"🧾 <b>Trade ID:</b> #{tid}\n👑 <b>Escrowed By:</b> {escrower}\n\n"
           f"✅ Payment Received\nContinue your deal safely 🔥\n\n🧭 <b>PW BY:</b> {PW_BY}")
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    send_log(context, f"🆕 Deal Created {tid} • {amount} by {escrower}")

@admin_only
def close(update, context):
    args = context.args
    if not args:
        update.message.reply_text("Usage: /close <TID> or /close <amount> <@buyer> <@seller>")
        return
    tid = args[0].upper()
    row = db_exec("SELECT * FROM deals WHERE trade_id=?", (tid,), fetch=True)
    if not row:
        update.message.reply_text("❌ Trade not found.")
        return
    db_exec("UPDATE deals SET status=?, closed_at=? WHERE trade_id=?", ("CLOSED", int(time.time()), tid))
    deal = row[0]
    msg = (f"🔒 <b>𝗗𝗘𝗔𝗟 𝗖𝗟𝗢𝗦𝗘𝗗</b> ✅\n\n"
           f"💰 ₹{deal[4]}\n🧾 #{deal[1]}\n🤝 {deal[2]} → {deal[3]}\n"
           f"👑 Escrowed By: {deal[5]}\n\n✅ Transaction Completed Securely\n🧭 <b>PW BY:</b> {PW_BY}")
    update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    send_log(context, f"✅ Deal Closed {tid}")

def history(update, context):
    rows = db_exec("SELECT trade_id,amount,buyer,seller,status FROM deals ORDER BY id DESC LIMIT 10", fetch=True)
    if not rows:
        update.message.reply_text("No recent deals.")
        return
    text = "🕒 <b>Recent Deals</b>\n\n" + "\n".join([f"#{r[0]} • ₹{r[1]} • {r[4]}" for r in rows])
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

@owner_only
def broadcast(update, context):
    if not context.args:
        update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    rows = db_exec("SELECT DISTINCT buyer FROM deals", fetch=True)
    for r in rows:
        try: context.bot.send_message(r[0], msg)
        except: pass
    update.message.reply_text("✅ Broadcast sent.")

def stats(update, context):
    total = db_exec("SELECT COUNT(*), SUM(amount) FROM deals", fetch=True)[0]
    open_d = db_exec("SELECT COUNT(*) FROM deals WHERE status='OPEN'", fetch=True)[0][0]
    closed_d = db_exec("SELECT COUNT(*) FROM deals WHERE status='CLOSED'", fetch=True)[0][0]
    text = (f"📊 <b>Global Stats</b>\n\n"
            f"Total Deals: {total[0]}\n"
            f"Closed Deals: {closed_d}\n"
            f"Open Deals: {open_d}\n"
            f"Total Volume: ₹{total[1] or 0}\n\n"
            f"🧭 <b>PW BY:</b> {PW_BY}")
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

@owner_only
def addadmin(update, context):
    if not context.args: return update.message.reply_text("Usage: /addadmin <user_id>")
    uid = int(context.args[0])
    db_exec("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (uid,))
    update.message.reply_text(f"✅ Added admin {uid}")

@owner_only
def removeadmin(update, context):
    if not context.args: return update.message.reply_text("Usage: /removeadmin <user_id>")
    uid = int(context.args[0])
    db_exec("DELETE FROM admins WHERE user_id=?", (uid,))
    update.message.reply_text(f"🗑 Removed admin {uid}")

@owner_only
def adminlist(update, context):
    rows = db_exec("SELECT user_id FROM admins", fetch=True)
    text = "👮 <b>Admin List</b>\n\n" + "\n".join([str(r[0]) for r in rows])
    update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ───── KEEPALIVE ─────
def keep_alive():
    while True:
        try:
            requests.get("https://choreo.dev")
        except:
            pass
        time.sleep(300)

# ───── MAIN ─────
def main():
    init_db()
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add))
    dp.add_handler(CommandHandler("close", close))
    dp.add_handler(CommandHandler("history", history))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("addadmin", addadmin))
    dp.add_handler(CommandHandler("removeadmin", removeadmin))
    dp.add_handler(CommandHandler("adminlist", adminlist))

    threading.Thread(target=keep_alive, daemon=True).start()
    updater.start_polling()
    logger.info("✅ FinalMM Bot started successfully")
    updater.idle()

if __name__ == "__main__":
    main()
