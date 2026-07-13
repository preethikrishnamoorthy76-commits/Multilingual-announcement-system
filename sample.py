from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# /start command - shows both types of buttons
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Inline keyboard (menu-style)
    inline_keyboard = [
        [InlineKeyboardButton("Inline Option 1", callback_data='inline_1')],
        [InlineKeyboardButton("Inline Option 2", callback_data='inline_2')]
    ]
    inline_markup = InlineKeyboardMarkup(inline_keyboard)

    # Reply keyboard (quick reply)
    reply_keyboard = [["Reply Yes", "Reply No"]]
    reply_markup = ReplyKeyboardMarkup(
        reply_keyboard, one_time_keyboard=True, resize_keyboard=True
    )

    await update.message.reply_text(
        "Choose an inline option below:", reply_markup=inline_markup
    )

    await update.message.reply_text(
        "Or choose a reply option below:", reply_markup=reply_markup
    )

# Handle inline button clicks
async def inline_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # acknowledge click
    await query.edit_message_text(f"You clicked: {query.data}")

# Handle reply button responses
async def reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text(f"You replied with: {user_text}")

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8327968816:AAHAV5BCDfG3IERUr5IPne_1wJyCJTQTiBY")

    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(inline_button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_handler))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()