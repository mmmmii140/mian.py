#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ----------------------------
# إعداد تسجيل الأخطاء
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ----------------------------
# الإعدادات العامة
# ----------------------------
MANDATORY_CHANNEL = "@bay_un"
DATABASE_NAME = "bot.db"

# ----------------------------
# دوال قاعدة البيانات
# ----------------------------
def get_db_connection():
    return sqlite3.connect(DATABASE_NAME, check_same_thread=False)

def initialize_database():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            mandatory_message TEXT DEFAULT 'يرجى الاشتراك في القناة.',
            vote_emoji TEXT DEFAULT '❤️',
            vote_notification_enabled INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT,
            chat_id INTEGER,
            message_id INTEGER,
            vote_count INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            voter_id INTEGER,
            submission_id INTEGER,
            UNIQUE(voter_id, submission_id)
        )
    """)
    conn.commit()
    conn.close()

def ensure_user_settings(user_id: int):
    conn = get_db_connection()
    conn.execute(
        "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)",
        (user_id,)
    )
    conn.commit()
    conn.close()

def fetch_user_settings(user_id: int):
    ensure_user_settings(user_id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT vote_emoji, channel_id, mandatory_message, vote_notification_enabled
          FROM user_settings
         WHERE user_id = ?
    """, (user_id,))
    row = cur.fetchone()
    conn.close()
    return row  # (emoji, channel_id, mandatory_message, notif_flag)

# ----------------------------
# فحص الاشتراك بالقناة
# ----------------------------
async def is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(MANDATORY_CHANNEL, user_id)
        return member.status in ("member", "creator", "administrator")
    except Exception:
        return False

def build_subscription_prompt():
    kb = [
        [InlineKeyboardButton(
            "🔗 الاشتراك في القناة",
            url=f"https://t.me/{MANDATORY_CHANNEL.lstrip('@')}"
        )],
        [InlineKeyboardButton("✅ تحقق الاشتراك", callback_data="check_sub")]
    ]
    text = (
        f"للاستخدام، يجب أولاً الاشتراك في قناتنا: {MANDATORY_CHANNEL}\n\n"
        "بعد الانضمام، اضغط «✅ تحقق الاشتراك»."
    )
    return text, InlineKeyboardMarkup(kb)

# ----------------------------
# بناء القوائم وأزرار الإجراءات
# ----------------------------
def build_main_menu(first_name, emoji, channel_id, msg, notif_flag):
    text = (
        f"· مرحبًا بك {first_name}!\n\n"
        f"- الإيموجي: {emoji}\n"
        f"- قناة النشر: <code>{channel_id or 'لم يتم التعيين'}</code>\n"
        f"- رسالة الاشتراك: {msg}\n\n"
        "· أرسل نصًا أو وسائط للنشر"
    )
    kb = [
        [InlineKeyboardButton("✏️ كليشة الاشتراك", callback_data="set_msg")],
        [
            InlineKeyboardButton("🔗 ربط القناة", callback_data="set_chan"),
            InlineKeyboardButton("😊 تعيين إيموجي", callback_data="set_emoji"),
        ],
        [
            InlineKeyboardButton(
                f"🔔 إشعار تصويت {'✅' if notif_flag else '❌'}",
                callback_data="toggle_notif",
            )
        ],
    ]
    return text, InlineKeyboardMarkup(kb)

# ----------------------------
# معالجات التحديثات
# ----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await is_subscribed(context.bot, user.id):
        text, markup = build_subscription_prompt()
        await update.effective_message.reply_text(text, reply_markup=markup)
        return

    emoji, chan, msg, notif = fetch_user_settings(user.id)
    text, markup = build_main_menu(user.first_name, emoji, chan, msg, notif)
    await update.effective_message.reply_text(text, reply_markup=markup, parse_mode="HTML")

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if await is_subscribed(context.bot, user.id):
        await query.message.delete()
        await start(update, context)
    else:
        await query.answer(
            "لم يتم العثور على اشتراك. يرجى الانضمام أولاً ثم إعادة المحاولة.",
            show_alert=True
        )

# نقطة البداية وتشغيل البوت
app = Flask(__name__)

@app.route('/')
def index():
    return "البوت يعمل!"

@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = Update.de_json(json_str, application.bot)
    application.process_update(update)
    return "ok", 200

if __name__ == "__main__":
    # إعداد البوت
    initialize_database()
    application = Application.builder().token("8033592945:AAGKTB23ILjz3dGqG3nIVyF5GqyluO3wns0").build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_subscription, pattern="^check_sub$"))
    # أضف باقي المعالجات هنا مثل handle_menu_query و handle_message

    # تشغيل البوت
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))