import os
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ENV VARIABLES
TOKEN = os.getenv("TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))

logging.basicConfig(level=logging.INFO)

# message tracking
message_map = {}
user_state = {}

# UI buttons
keyboard = ReplyKeyboardMarkup(
    [["💰 I Paid", "❓ Ask Question"]],
    resize_keyboard=True
)

# START MESSAGE
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Support\n\n"
        "After payment, click '💰 I Paid' and send TXID.\n"
        "Or click '❓ Ask Question' for help.",
        reply_markup=keyboard
    )

# send message to all admins
async def notify_admins(context, text):
    for admin in ADMIN_IDS:
        await context.bot.send_message(admin, text)

# forward to all admins
async def forward_to_admins(context, user_id, message_id):
    forwarded_ids = []
    for admin in ADMIN_IDS:
        msg = await context.bot.forward_message(admin, user_id, message_id)
        forwarded_ids.append(msg.message_id)
    return forwarded_ids

# HANDLE USER
async def handle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    text = update.message.text

    # I PAID FLOW
    if text == "💰 I Paid":
        user_state[user_id] = "awaiting_payment"
        await update.message.reply_text("Send your TXID or wallet details.")
        return

    # QUESTION FLOW
    if text == "❓ Ask Question":
        user_state[user_id] = "question"
        await update.message.reply_text("Type your question.")
        return

    # PAYMENT SUBMISSION
    if user_state.get(user_id) == "awaiting_payment":
        forwarded_ids = await forward_to_admins(
            context, user_id, update.message.message_id
        )

        for fid in forwarded_ids:
            message_map[fid] = user_id

        await update.message.reply_text("✅ Payment received. Verifying shortly.")

        # reminder after 10 mins
        async def reminder():
            await asyncio.sleep(600)
            for fid in forwarded_ids:
                if fid in message_map:
                    await notify_admins(
                        context,
                        f"⚠️ Pending payment from user {user_id}"
                    )
                    break

        asyncio.create_task(reminder())
        return

    # QUESTION SUBMISSION
    if user_state.get(user_id) == "question":
        forwarded_ids = await forward_to_admins(
            context, user_id, update.message.message_id
        )

        for fid in forwarded_ids:
            message_map[fid] = user_id

        await update.message.reply_text("📩 Sent to support.")
        return

    # DEFAULT (forward everything)
    forwarded_ids = await forward_to_admins(
        context, user_id, update.message.message_id
    )

    for fid in forwarded_ids:
        message_map[fid] = user_id

# ADMIN REPLY → USER
async def handle_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if update.message.reply_to_message:
        msg_id = update.message.reply_to_message.message_id

        if msg_id in message_map:
            user_id = message_map[msg_id]

            await context.bot.send_message(user_id, update.message.text)

            del message_map[msg_id]

# MANUAL MESSAGE COMMAND
# /msg user_id message
async def manual_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    try:
        user_id = int(context.args[0])
        text = " ".join(context.args[1:])
        await context.bot.send_message(user_id, text)
    except:
        await update.message.reply_text("Usage: /msg user_id message")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("msg", manual_msg))

    # admin replies
    app.add_handler(
        MessageHandler(filters.REPLY & filters.User(ADMIN_IDS), handle_admin)
    )

    # user messages
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE, handle_user))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()