"""
Plan Generator Telegram Bot - Complete Single File Version
Deploy to Render.com with webhook support
"""

import os
import sys
import logging
import random
import asyncio
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple

from flask import Flask, request, jsonify
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, ApplicationBuilder
)

# ======== CONFIGURATION ========
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL") or "https://planbot-juf8.onrender.com"
PORT = int(os.environ.get("PORT", "8443"))

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable required!")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ======== PLAN GENERATOR CORE ========

class Category(Enum):
    STUDY = "study"
    FITNESS = "fitness"
    CODING = "coding"
    CREATIVE = "creative"
    PRODUCTIVITY = "productivity"


class Difficulty(Enum):
    EASY = (1, "Easy", 20)
    MEDIUM = (2, "Medium", 35)
    HARD = (3, "Hard", 50)
    
    def __init__(self, num: int, label: str, duration_base: int):
        self._value_ = num
        self.label = label
        self.duration_base = duration_base


STEP_POOLS = {
    Category.STUDY: [
        ("Review previous material", 2), ("Learn new concepts", 3),
        ("Practice with exercises", 2), ("Summarize key points", 1),
        ("Test your knowledge", 2), ("Watch tutorial", 1),
    ],
    Category.FITNESS: [
        ("Dynamic warm-up", 3), ("Main lift/strength work", 3),
        ("Cardio circuit", 2), ("Accessory work", 2),
        ("Cool-down stretches", 3), ("Foam rolling", 1),
    ],
    Category.CODING: [
        ("Review requirements", 2), ("Write failing test", 2),
        ("Implement feature", 3), ("Refactor code", 2),
        ("Document changes", 1), ("Deploy/verify", 1),
    ],
    Category.CREATIVE: [
        ("Gather inspiration", 2), ("Rough sketch/outline", 2),
        ("First draft", 3), ("Iterate/refine", 2), ("Final polish", 2),
    ],
    Category.PRODUCTIVITY: [
        ("Set priorities", 3), ("Deep work block", 3),
        ("Quick wins", 2), ("Review/adjust", 1), ("Prep for tomorrow", 2),
    ],
}

GOALS = {
    Category.STUDY: ["Master the topic", "Complete chapter", "Pass assessment"],
    Category.FITNESS: ["Build strength", "Improve endurance", "Mobility work"],
    Category.CODING: ["Ship feature", "Fix critical bug", "Learn new tech"],
    Category.CREATIVE: ["Finish draft", "Explore new style", "Complete project"],
    Category.PRODUCTIVITY: ["Clear backlog", "Organize workspace", "Plan week"],
}


@dataclass
class Step:
    name: str
    duration_minutes: int
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    id: int
    category: str
    difficulty: str
    goal: str
    steps: List[Step]
    created_at: str = ""
    
    @property
    def total_duration(self) -> int:
        return sum(s.duration_minutes for s in self.steps)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "difficulty": self.difficulty,
            "goal": self.goal,
            "total_duration": self.total_duration,
            "created_at": self.created_at,
            "steps": [s.to_dict() for s in self.steps],
        }


class PlanGenerator:
    _counter = 0
    
    def _weighted_choice(self, options: List[Tuple[str, int]]) -> str:
        items, weights = zip(*options)
        return random.choices(items, weights=weights, k=1)[0]
    
    def _calculate_duration(self, difficulty: Difficulty, position: int, 
                          total: int) -> int:
        base = difficulty.duration_base
        if position == 0 or position == total - 1:
            return base // 2
        return int(base * random.uniform(0.8, 1.3))
    
    def generate(
        self,
        category: Optional[Category] = None,
        difficulty: Optional[Difficulty] = None,
        num_steps: Optional[int] = None,
    ) -> Plan:
        cat = category or random.choice(list(Category))
        diff = difficulty or random.choice(list(Difficulty))
        
        available = STEP_POOLS[cat]
        steps_count = min(num_steps or random.randint(3, 5), len(available))
        
        selected = []
        temp = available.copy()
        for _ in range(steps_count):
            choice = self._weighted_choice(temp)
            selected.append(choice)
            temp = [x for x in temp if x[0] != choice]
        
        steps = []
        for i, name in enumerate(selected):
            dur = self._calculate_duration(diff, i, steps_count)
            steps.append(Step(name=name, duration_minutes=dur))
        
        PlanGenerator._counter += 1
        
        return Plan(
            id=PlanGenerator._counter,
            category=cat.value,
            difficulty=diff.label,
            goal=random.choice(GOALS[cat]),
            steps=steps,
            created_at=datetime.now().isoformat(),
        )


# ======== FLASK APP SETUP ========
app = Flask(__name__)
generator = PlanGenerator()

# Create bot instance
bot = Bot(token=TOKEN)
application = None

# Conversation states
SELECTING_CATEGORY, SELECTING_DIFFICULTY, CONFIRMING = range(3)


# ======== TELEGRAM HANDLERS ========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    logger.info(f"Start from {user.id}")
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        "Welcome to Plan Generator Bot!\n\n"
        "📋 *Commands:*\n"
        "/plan - Generate structured plan\n"
        "/quick - Quick random plan\n"
        "/help - Show help\n\n"
        "Let's plan something great!",
        parse_mode='Markdown'
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Plan Generator Bot*\n\n"
        "*/plan* - Interactive plan generator\n"
        "Choose category → difficulty → get plan!\n\n"
        "*/quick* - Instant random plan\n\n"
        "Categories: Study, Fitness, Coding, Creative, Productivity",
        parse_mode='Markdown'
    )


def format_plan(plan: Plan) -> str:
    """Format plan for display"""
    emoji_map = {
        'study': '📚', 'fitness': '💪', 'coding': '💻',
        'creative': '🎨', 'productivity': '⚡'
    }
    emoji = emoji_map.get(plan.category.lower(), '📋')
    
    message = (
        f"{emoji} *Plan #{plan.id}*\n"
        f"Category: {plan.category.title()}\n"
        f"Difficulty: {plan.difficulty}\n\n"
        f"🎯 *{plan.goal}*\n\n"
        f"⏱️ Total: *{plan.total_duration} min* ({len(plan.steps)} steps)\n\n"
        f"*Steps:*\n"
    )
    
    for i, step in enumerate(plan.steps, 1):
        message += f"{i}. {step.name} ({step.duration_minutes}m)\n"
    
    return message


async def quick_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick random plan"""
    plan = generator.generate()
    await update.message.reply_text(format_plan(plan), parse_mode='Markdown')


async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start interactive plan selection"""
    keyboard = [
        [InlineKeyboardButton("📚 Study", callback_data='study')],
        [InlineKeyboardButton("💪 Fitness", callback_data='fitness')],
        [InlineKeyboardButton("💻 Coding", callback_data='coding')],
        [InlineKeyboardButton("🎨 Creative", callback_data='creative')],
        [InlineKeyboardButton("⚡ Productivity", callback_data='productivity')],
        [InlineKeyboardButton("🎲 Random", callback_data='random')],
    ]
    
    await update.message.reply_text(
        "What category do you want?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_CATEGORY


async def category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Category selected, now choose difficulty"""
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
    
    category_name = query.data.title() if query.data != 'random' else 'Random'
    
    await query.edit_message_text(
        f"Category: {category_name}\n\nSelect difficulty:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECTING_DIFFICULTY


async def difficulty_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and show plan"""
    query = update.callback_query
    await query.answer()
    
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
    
    # Add "Again" button
    keyboard = [[InlineKeyboardButton("🔄 Generate Again", callback_data='again')]]
    
    await query.edit_message_text(
        format_plan(plan),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CONFIRMING


async def again_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle again button"""
    query = update.callback_query
    await query.answer()
    return await plan_start(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text(
        "❌ Cancelled. Send /plan to start again."
    )
    return ConversationHandler.END


# ======== SETUP APPLICATION ========

def setup_application():
    """Initialize Telegram application"""
    global application
    
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("quick", quick_plan))
    
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
                CallbackQueryHandler(again_handler, pattern='^again$')
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    
    return application


# ======== FLASK ROUTES ========

@app.route('/')
def index():
    """Health check"""
    try:
        webhook_info = bot.get_webhook_info()
        return jsonify({
            "status": "alive",
            "service": "plan-generator-bot",
            "webhook_set": webhook_info.url != "",
            "webhook_url": webhook_info.url,
            "pending_updates": webhook_info.pending_update_count
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/health')
def health():
    return "OK"


@app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    """
    Process Telegram webhook updates
    CRITICAL: Must return 200 OK quickly
    """
    try:
        # Get JSON data
        json_data = request.get_json(force=True)
        
        if not json_data:
            logger.warning("Empty request received")
            return jsonify({"error": "No data"}), 400
        
        logger.info(f"Update received: {json_data.get('update_id', 'unknown')}")
        
        # Create Update object
        update = Update.de_json(json_data, bot)
        
        # Process update asynchronously
        asyncio.run(process_telegram_update(update))
        
        # Return 200 OK immediately
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        # Still return 200 to prevent Telegram retries
        return jsonify({"status": "error_handled"}), 200


async def process_telegram_update(update: Update):
    """Process update with application"""
    try:
        if application is None:
            setup_application()
        
        # Initialize and process
        await application.initialize()
        await application.process_update(update)
        
    except Exception as e:
        logger.error(f"Process update error: {e}", exc_info=True)


# ======== WEBHOOK MANAGEMENT ========

def set_webhook():
    """Set webhook with Telegram"""
    webhook_url = f"{RENDER_URL}/webhook/{TOKEN}"
    
    try:
        # Delete old webhook and pending updates
        logger.info("Deleting old webhook...")
        bot.delete_webhook(drop_pending_updates=True)
        
        # Set new webhook
        logger.info(f"Setting webhook to: {webhook_url}")
        success = bot.set_webhook(url=webhook_url)
        
        if success:
            logger.info("Webhook set successfully!")
        else:
            logger.error("Failed to set webhook")
        
        return success, webhook_url
        
    except Exception as e:
        logger.error(f"Webhook setup error: {e}")
        return False, str(e)


@app.route('/setup-webhook', methods=['GET'])
def manual_setup():
    """Manual webhook setup"""
    success, result = set_webhook()
    
    if success:
        return jsonify({
            "status": "success",
            "message": "Webhook set",
            "url": result
        })
    else:
        return jsonify({
            "status": "error",
            "message": result
        }), 500


@app.route('/delete-webhook', methods=['GET'])
def delete_webhook_route():
    """Delete webhook"""
    try:
        bot.delete_webhook(drop_pending_updates=True)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======== MAIN ========

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Plan Generator Bot Starting")
    logger.info("=" * 60)
    
    # Setup application
    setup_application()
    
    # Set webhook on startup
    success, url = set_webhook()
    logger.info(f"Webhook: {success} at {url}")
    
    # Start Flask server
    logger.info(f"Starting server on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=False)
