"""
Plan Generator Telegram Bot - Fixed for Render.com webhook
"""

import os
import sys
import logging
import random
import asyncio
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler
)

from plan_generator import PlanGenerator, Category, Difficulty

# ======== CONFIG ========
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", "8443"))

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable required!")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)
generator = PlanGenerator()
application = None

# Conversation states
SELECTING_CATEGORY, SELECTING_DIFFICULTY, CONFIRMING = range(3)

# ======== HANDLERS (Same as before) ========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Plan Generator Bot!\n\n"
        "Commands:\n/plan - Generate plan\n/quick - Quick plan\n/help - Help"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Commands: /plan, /quick, /help")

def format_plan(plan):
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
        f"⏱️ Total: {plan.total_duration} min ({len(plan.steps)} steps)\n\n"
        f"*Steps:*\n"
    )
    for i, step in enumerate(plan.steps, 1):
        message += f"{i}. {step.name} ({step.duration_minutes}m)\n"
    return message

async def quick_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan = generator.generate()
    await update.message.reply_text(format_plan(plan), parse_mode='Markdown')

async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📚 Study", callback_data='study')],
        [InlineKeyboardButton("💪 Fitness", callback_data='fitness')],
        [InlineKeyboardButton("💻 Coding", callback_data='coding')],
        [InlineKeyboardButton("🎨 Creative", callback_data='creative')],
        [InlineKeyboardButton("⚡ Productivity", callback_data='productivity')],
        [InlineKeyboardButton("🎲 Random", callback_data='random')],
    ]
    await update.message.reply_text("What category?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_CATEGORY

async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await query.edit_message_text(
        f"Category: {query.data.title()}\n\nSelect difficulty:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_DIFFICULTY

async def difficulty_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    cat_str = context.user_data.get('category', 'random')
    diff_str = query.data

    category_map = {
        'study': Category.STUDY, 'fitness': Category.FITNESS,
        'coding': Category.CODING, 'creative': Category.CREATIVE,
        'productivity': Category.PRODUCTIVITY, 'random': None
    }
    difficulty_map = {
        'easy': Difficulty.EASY, 'medium': Difficulty.MEDIUM,
        'hard': Difficulty.HARD, 'random_diff': None
    }

    plan = generator.generate(
        category=category_map.get(cat_str),
        difficulty=difficulty_map.get(diff_str)
    )
    
    keyboard = [[InlineKeyboardButton("🔄 Again", callback_data='again')]]
    await query.edit_message_text(
        format_plan(plan), 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )
    return CONFIRMING

async def again_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await plan_start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Send /plan to start.")
    return ConversationHandler.END

# ======== SETUP ========

def setup_application():
    global application
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("quick", quick_plan))
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("plan", plan_start)],
        states={
            SELECTING_CATEGORY: [CallbackQueryHandler(category_selected, 
                pattern='^(study|fitness|coding|creative|productivity|random)$')],
            SELECTING_DIFFICULTY: [CallbackQueryHandler(difficulty_selected, 
                pattern='^(easy|medium|hard|random_diff)$')],
            CONFIRMING: [CallbackQueryHandler(again_handler, pattern='^again$')],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    return application

# ======== FLASK ROUTES - CRITICAL FIX ========

@flask_app.route('/')
def index():
    return jsonify({
        "status": "alive",
        "bot_initialized": application is not None
    })

@flask_app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    """Fixed: Proper async handling"""
    global application
    
    try:
        if application is None:
            setup_application()
        
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        
        # CRITICAL FIX: Use run_async to properly await async function
        application.run_async(application.process_update(update))
        
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@flask_app.route('/setwebhook', methods=['GET'])
def set_webhook():
    global application
    
    try:
        if application is None:
            setup_application()
        
        if not RENDER_URL:
            return jsonify({"error": "RENDER_EXTERNAL_URL not set"}), 400
        
        webhook_url = f"{RENDER_URL}/webhook/{TOKEN}"
        success = application.bot.set_webhook(url=webhook_url)
        
        return jsonify({
            "status": "webhook set" if success else "failed",
            "url": webhook_url
        })
    except Exception as e:
        logger.error(f"Set webhook error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ======== MAIN ========

if __name__ == "__main__":
    setup_application()
    
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/webhook/{TOKEN}"
        application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set: {webhook_url}")
    
    # IMPORTANT: Use threaded=False for Telegram bot
    flask_app.run(host="0.0.0.0", port=PORT, threaded=False)
