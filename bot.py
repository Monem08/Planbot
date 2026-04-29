"""
Plan Generator Telegram Bot - Webhook version for Render.com
"""

import os
import sys
import logging
import random
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler
)

# Import your plan generator
from plan_generator import PlanGenerator, Category, Difficulty

# ======== CONFIG ========
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Auto-set by Render
PORT = int(os.environ.get("PORT", "8443"))
WEBHOOK_PATH = f"/webhook/{TOKEN}"

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable required!")

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for webhook
flask_app = Flask(__name__)

# Plan generator instance
generator = PlanGenerator()

# Conversation states
SELECTING_CATEGORY, SELECTING_DIFFICULTY, CONFIRMING = range(3)


# ======== TELEGRAM HANDLERS ========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "👋 Welcome to Plan Generator Bot!\n\n"
        "I create structured plans for:\n"
        "• 📚 Study\n• 💪 Fitness\n• 💻 Coding\n"
        "• 🎨 Creative\n• ⚡ Productivity\n\n"
        "Use /plan to generate a plan\n"
        "Use /stats to see your usage\n"
        "Use /help for more info"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "🤖 *Plan Generator Bot Commands*\n\n"
        "/start - Welcome message\n"
        "/plan - Generate new plan (interactive)\n"
        "/quick - Quick random plan\n"
        "/stats - Your generation stats\n"
        "/cancel - Cancel current operation\n\n"
        "The bot uses AI-weighted selection "
        "for smarter plan generation!",
        parse_mode='Markdown'
    )


async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start plan generation - select category"""
    keyboard = [
        [InlineKeyboardButton("📚 Study", callback_data='study')],
        [InlineKeyboardButton("💪 Fitness", callback_data='fitness')],
        [InlineKeyboardButton("💻 Coding", callback_data='coding')],
        [InlineKeyboardButton("🎨 Creative", callback_data='creative')],
        [InlineKeyboardButton("⚡ Productivity", callback_data='productivity')],
        [InlineKeyboardButton("🎲 Random", callback_data='random')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "What category?",
        reply_markup=reply_markup
    )
    return SELECTING_CATEGORY


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Category selected - now select difficulty"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['category'] = query.data
    
    keyboard = [
        [
            InlineKeyboardButton("🟢 Easy", callback_data='easy'),
            InlineKeyboardButton("🟡 Medium", callback_data='medium'),
        ],
        [
            InlineKeyboardButton("🔴 Hard", callback_data='hard'),
            InlineKeyboardButton("🎲 Random", callback_data='random_diff'),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Category: {query.data.title()}\n\nSelect difficulty:",
        reply_markup=reply_markup
    )
    return SELECTING_DIFFICULTY


async def difficulty_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and display plan"""
    query = update.callback_query
    await query.answer()
    
    # Parse inputs
    cat_str = context.user_data.get('category', 'random')
    diff_str = query.data
    
    # Convert to enums
    category_map = {
        'study': Category.STUDY, 'fitness': Category.FITNESS,
        'coding': Category.CODING, 'creative': Category.CREATIVE,
        'productivity': Category.PRODUCTIVITY, 'random': None
    }
    difficulty_map = {
        'easy': Difficulty.EASY, 'medium': Difficulty.MEDIUM,
        'hard': Difficulty.HARD, 'random_diff': None
    }
    
    category = category_map.get(cat_str)
    difficulty = difficulty_map.get(diff_str)
    
    # Generate plan
    plan = generator.generate(category=category, difficulty=difficulty)
    
    # Format output
    emoji_map = {
        'study': '📚', 'fitness': '💪', 'coding': '💻',
        'creative': '🎨', 'productivity': '⚡'
    }
    emoji = emoji_map.get(plan.category.lower(), '📋')
    
    message = (
        f"{emoji} *Plan #{plan.id}*\n"
        f"Category: {plan.category}\n"
        f"Difficulty: {plan.difficulty}\n\n"
        f"🎯 *{plan.goal}*\n\n"
        f"⏱️ Total: {plan.total_duration} minutes "
        f"({len(plan.steps)} steps)\n\n"
        f"*Steps:*\n"
    )
    
    for i, step in enumerate(plan.steps, 1):
        message += f"{i}. {step.name} ({step.duration_minutes}m)\n"
    
    # Add "Generate again" button
    keyboard = [[InlineKeyboardButton("🔄 Generate Again", callback_data='again')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return CONFIRMING


async def quick_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate quick random plan"""
    plan = generator.generate()
    
    emoji_map = {
        'study': '📚', 'fitness': '💪', 'coding': '💻',
        'creative': '🎨', 'productivity': '⚡'
    }
    emoji = emoji_map.get(plan.category.lower(), '📋')
    
    message = (
        f"{emoji} *Quick Plan #{plan.id}*\n"
        f"_{plan.category}_ | _{plan.difficulty}_\n\n"
        f"🎯 {plan.goal}\n"
        f"⏱️ {plan.total_duration} min\n\n"
        f"*Steps:*\n" + 
        '\n'.join([f"• {s.name} ({s.duration_minutes}m)" for s in plan.steps])
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show stats"""
    # In real bot, load from database
    await update.message.reply_text(
        "📊 *Your Stats*\n\n"
        "Plans generated today: 0\n"
        "Total plans: 0\n"
        "Favorite category: --\n\n"
        "_Stats coming soon!_",
        parse_mode='Markdown'
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("Cancelled. Use /plan to start again.")
    return ConversationHandler.END


async def keep_alive_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'again' button"""
    query = update.callback_query
    await query.answer()
    return await plan_start(update, context)


# ======== FLASK WEBHOOK ENDPOINTS ========

@flask_app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({
        "status": "alive",
        "service": "plan-generator-bot",
        "timestamp": str(datetime.now())
    })


@flask_app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    """Telegram webhook endpoint"""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.process_update(update)
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ======== MAIN ========

def init_bot():
    """Initialize bot with handlers"""
    global application
    
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("quick", quick_plan))
    application.add_handler(CommandHandler("stats", stats))
    
    # Conversation handler for /plan
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("plan", plan_start)],
        states={
            SELECTING_CATEGORY: [
                CallbackQueryHandler(category_selected, 
                    pattern='^(study|fitness|coding|creative|productivity|random)$')
            ],
            SELECTING_DIFFICULTY: [
                CallbackQueryHandler(difficulty_selected, 
                    pattern='^(easy|medium|hard|random_diff)$')
            ],
            CONFIRMING: [
                CallbackQueryHandler(keep_alive_check, pattern='^again$')
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    
    return application


def set_webhook():
    """Set Telegram webhook"""
    webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    application.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to: {webhook_url}")


if __name__ == "__main__":
    from datetime import datetime
    
    # Initialize bot
    application = init_bot()
    
    # Set webhook on startup
    if RENDER_URL:
        set_webhook()
    
    # Start Flask server
    flask_app.run(host="0.0.0.0", port=PORT)