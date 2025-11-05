#!/usr/bin/env python3
# FinalMM v3.1 – 24x7 Escrow Bot | Developed for Aarohi by Ashra

import os, time, random, sqlite3, logging, threading, requests
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ===== CONFIG =====
BOT_TOKEN = "8273619720:AAEbCOxf1Ycx4OTFS8ZzFbJimw1tba0V8Y0"
OWNER_ID = 6847499628
LOG_CHANNEL = -1003089374759
PW_BY = "@LuffyBots"
DB_FILE = "finalmm.db"
KEEP_ALIVE_URL = "https://choreo.dev"  # for uptime ping (optional)

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ===== DATABASE =====
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS deals (
 trade_id TEXT PRIMARY KEY,
 chat_id INTEGER,
 amount REAL,
 buyer TEXT,
 seller TEXT,
 escrower TEXT,
 status TEXT,
 created_at INTEGER,
 closed_at INTEGER
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)""")
conn.commit()

# ===== UTILS =====
def gen_tid(): return "TID" + str(random.randint(100000, 999999))
def now(): return int(time.time())
def is_owner(uid): return uid == OWNER_ID
def is_admin(uid):
    if uid == OWNER_ID: return True
    cur.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,))
    return bool(cur.fetchone())

def fmt(header, amt, buyer, seller, esc, tid, status):
    msg = (
        f"{header}\n\n"
        f"💰 Amount: ₹{amt}\n"
        f"🤝 Buyer: {buyer}\n"
        f"🏷️ Seller: {seller}\n"
        f"🧾 Trade ID: #{tid}\n"
        f"👑 Escrowed By: {esc}\n\n"
        f"🧭 PW BY: {PW_BY}\n"
    )
    if status == "OPEN": msg += "\n✅ Payment Received\nContinue your deal safely 🔥"
    elif status == "CLOSED": msg += "\n🎯 Deal Completed Successfully!"
    elif status == "REFUNDED": msg += "\n💸 Funds Returned to Buyer"
    elif status == "CANCELLED": msg += "\n❌ Deal Cancelled"
    return msg

# ===== CORE COMMANDS =====
def start(update, ctx):
    update.message.reply_text("🤖 LBMM Escrow Bot is active 24×7.\nUse /command to view all admin commands.")

def id_cmd(update, ctx): update.message.reply_text(f"🪪 Your ID: {update.effective_user.id}")

def add(update, ctx):
    m = update.message
    if not m.reply_to_message or len(ctx.args) < 1:
        m.reply_text("Reply to seller and use: /add <amount>")
        return
    try: amt = float(ctx.args[0])
    except: m.reply_text("Invalid amount"); return
    buyer = f"@{m.from_user.username}" if m.from_user.username else m.from_user.first_name
    seller = f"@{m.reply_to_message.from_user.username}" if m.reply_to_message.from_user.username else m.reply_to_message.from_user.first_name
    esc = buyer
    tid = gen_tid()
    msg = fmt("💼 𝗡𝗘𝗪 𝗗𝗘𝗔𝗟 𝗖𝗥𝗘𝗔𝗧𝗘𝗗", amt, buyer, seller, esc, tid, "OPEN")
    m.reply_text(msg, parse_mode=ParseMode.HTML)
    cur.execute("INSERT INTO deals VALUES (?,?,?,?,?,?,?,?,?)", (tid, m.chat_id, amt, buyer, seller, esc, "OPEN", now(), 0)); conn.commit()
    ctx.bot.send_message(LOG_CHANNEL, f"🧾 New Deal Created #{tid} | ₹{amt}")

def _update_status(update, ctx, new_status, header):
    m = update.message
    if len(ctx.args) < 1: m.reply_text(f"Usage: /{new_status.lower()} <amount>"); return
    amt = float(ctx.args[0])
    cur.execute("SELECT trade_id,buyer,seller,escrower FROM deals WHERE amount=? AND status='OPEN'", (amt,))
    r = cur.fetchone()
    if not r: m.reply_text("No open deal found"); return
    tid, b, s, e = r
    msg = fmt(header, amt, b, s, e, tid, new_status)
    m.reply_text(msg, parse_mode=ParseMode.HTML)
    cur.execute("UPDATE deals SET status=?, closed_at=? WHERE trade_id=?", (new_status, now(), tid)); conn.commit()
    ctx.bot.send_message(LOG_CHANNEL, f"🔄 {new_status} #{tid}")

def close(update, ctx): _update_status(update, ctx, "CLOSED", "✅ 𝗗𝗘𝗔𝗟 𝗖𝗟𝗢𝗦𝗘𝗗")
def refund(update, ctx): _update_status(update, ctx, "REFUNDED", "💸 𝗗𝗘𝗔𝗟 𝗥𝗘𝗙𝗨𝗡𝗗𝗘𝗗")
def cancel(update, ctx): _update_status(update, ctx, "CANCELLED", "❌ 𝗗𝗘𝗔𝗟 𝗖𝗔𝗡𝗖𝗘𝗟𝗟𝗘𝗗")

def status(update, ctx):
    if not ctx.args: update.message.reply_text("Usage: /status <TradeID>"); return
    tid = ctx.args[0].upper().replace("#", "")
    cur.execute("SELECT amount,buyer,seller,status,created_at,closed_at FROM deals WHERE trade_id=?", (tid,))
    r = cur.fetchone()
    if not r: update.message.reply_text("Trade not found."); return
    amt,b,s,st,c,x = r
    update.message.reply_text(f"📊 #{tid}\n💰 ₹{amt}\n🤝 {b}\n🏷️ {s}\n📌 Status: {st}\n🕒 {time.ctime(c)}")

def history(update, ctx):
    cur.execute("SELECT trade_id,status,amount FROM deals ORDER BY created_at DESC LIMIT 10")
    rows = cur.fetchall()
    if not rows: update.message.reply_text("No deals yet."); return
    text = "\n".join([f"#{r[0]} | ₹{r[2]} | {r[1]}" for r in rows])
    update.message.reply_text("🕓 **Recent Deals:**\n" + text, parse_mode=ParseMode.MARKDOWN)

def ongoing(update, ctx):
    cur.execute("SELECT trade_id,amount,buyer,seller FROM deals WHERE status='OPEN'")
    rows = cur.fetchall()
    if not rows: update.message.reply_text("No ongoing deals."); return
    text = "\n".join([f"#{r[0]} | ₹{r[1]} | {r[2]} ➜ {r[3]}" for r in rows])
    update.message.reply_text("🔥 **Ongoing Deals:**\n" + text, parse_mode=ParseMode.MARKDOWN)

def broadcast(update, ctx):
    if not is_admin(update.effective_user.id): return
    text = " ".join(ctx.args)
    if not text: update.message.reply_text("Usage: /broadcast <message>"); return
    cur.execute("SELECT DISTINCT buyer FROM deals")
    users = cur.fetchall()
    sent = 0
    for u in users:
        try:
            ctx.bot.send_message(u[0], text)
            sent += 1
        except: pass
    update.message.reply_text(f"📢 Broadcast sent to {sent} users.")

def adminlist(update, ctx):
    cur.execute("SELECT user_id FROM admins"); rows = cur.fetchall()
    if not rows: update.message.reply_text("No admins added."); return
    text = "\n".join([f"👤 {r[0]}" for r in rows])
    update.message.reply_text("🧠 Admin List:\n" + text)

def addadmin(update, ctx):
    if not is_owner(update.effective_user.id): return
    uid = int(ctx.args[0]); cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (uid,)); conn.commit()
    update.message.reply_text(f"✅ Added admin: {uid}")

def removeadmin(update, ctx):
    if not is_owner(update.effective_user.id): return
    uid = int(ctx.args[0]); cur.execute("DELETE FROM admins WHERE user_id=?", (uid,)); conn.commit()
    update.message.reply_text(f"🗑️ Removed admin: {uid}")

def topuser(update, ctx):
    cur.execute("SELECT escrower,COUNT(*) as deals FROM deals GROUP BY escrower ORDER BY deals DESC LIMIT 5")
    rows = cur.fetchall()
    if not rows: update.message.reply_text("No users yet."); return
    text = "\n".join([f"🏆 {r[0]} – {r[1]} deals" for r in rows])
    update.message.reply_text("⭐ **Top Escrow Users:**\n" + text, parse_mode=ParseMode.MARKDOWN)

def command(update, ctx):
    uid = update.effective_user.id
    if not is_admin(uid): return
    text = (
        "🤖 𝗔𝗱𝗺𝗶𝗻 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀 𝗟𝗶𝘀𝘁\n\n"
        "💼 Deals:\n"
        "/add /close /refund /cancel /status /history /ongoing /mydeals\n\n"
        "📊 Stats:\n"
        "/stats /stat /gstats /topuser\n\n"
        "🧠 Admin Tools:\n"
        "/addadmin /removeadmin /adminlist /broadcast\n\n"
        "⏰ Utility:\n"
        "/notify /id /command\n\n"
        "🧭 PW BY: " + PW_BY
    )
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ===== KEEP ALIVE =====
def keep_alive():
    while True:
        try: requests.get(KEEP_ALIVE_URL)
        except: pass
        time.sleep(300)

threading.Thread(target=keep_alive, daemon=True).start()

# ===== MAIN =====
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("id", id_cmd))
    dp.add_handler(CommandHandler("add", add))
    dp.add_handler(CommandHandler("close", close))
    dp.add_handler(CommandHandler("refund", refund))
    dp.add_handler(CommandHandler("cancel", cancel))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("history", history))
    dp.add_handler(CommandHandler("ongoing", ongoing))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    dp.add_handler(CommandHandler("adminlist", adminlist))
    dp.add_handler(CommandHandler("addadmin", addadmin))
    dp.add_handler(CommandHandler("removeadmin", removeadmin))
    dp.add_handler(CommandHandler("topuser", topuser))
    dp.add_handler(CommandHandler("command", command))

    logger.info("✅ FinalMM v3.1 started successfully.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
