import telebot
from telebot import types
import json
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import threading
import logging
from server import run_flask
threading.Thread(target=run_flask, daemon=True).start()
import os
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Читаем переменную окружения

bot = telebot.TeleBot(BOT_TOKEN)

# Включаем возможность бесплатного пробного периода
free_period = True

# Файл для хранения данных пользователей
USERS_FILE = 'users.json'

# Настройка логирования
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Загрузка данных пользователей с обработкой ошибок
users_data = {}
try:
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        users_data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    logging.error(f"Ошибка при загрузке данных из файла {USERS_FILE}: {e}")
    users_data = {}  # Инициализируем пустой словарь, если файла нет или он поврежден

# Функция сохранения данных с обработкой ошибок
def save_users_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ошибка при сохранении данных в файл {USERS_FILE}: {e}")

# Блокировка для синхронизации доступа к order_data
order_lock = threading.Lock()
order_data = {}  # Глобальный словарь для хранения данных заказа

def get_user_data(user_id):
    """
    Возвращает данные пользователя, создавая запись по умолчанию, если её нет,
    и проверяет актуальность подписки (expired = True, если подписка истекла).
    """
    user_id_str = str(user_id)
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            "subscription_end": "",
            "tariff": "",
            "key": "",
            "address": "",
            "expired": True,
            "free_period_used": False
        }
        save_users_data()
    user = users_data[user_id_str]
    if user["subscription_end"]:
        try:
            sub_end = datetime.strptime(user["subscription_end"], "%Y-%m-%d")
            user["expired"] = sub_end < datetime.now()
        except Exception as e:
            logging.error(f"Ошибка при парсинге даты подписки для пользователя {user_id}: {e}")
            user["expired"] = True
    else:
        user["expired"] = True
    save_users_data()
    return user

def update_user_subscription(user_id, period_months, devices, price):
    """
    Обновляет данные пользователя после успешной оплаты.
    Если подписка ещё активна, новый период прибавляется к оставшемуся времени.
    Тариф сохраняется в виде словаря для удобства.
    """
    user = get_user_data(user_id)
    current_time = datetime.now()
    if user["subscription_end"]:
        try:
            sub_end = datetime.strptime(user["subscription_end"], "%Y-%m-%d")
            base_time = sub_end if sub_end > current_time else current_time
        except Exception as e:
            logging.error(f"Ошибка при парсинге даты подписки для пользователя {user_id}: {e}")
            base_time = current_time
    else:
        base_time = current_time

    new_end = base_time + relativedelta(months=period_months)

    user["subscription_end"] = new_end.strftime("%Y-%m-%d")
    user["tariff"] = {
        "months": period_months,
        "devices": devices,
        "price": price
    }
    user["key"] = "DUMMY_KEY_123456"  # В будущем заменить на уникальный ключ
    user["address"] = "vpn.example.com"
    user["expired"] = False
    save_users_data()

def update_user_subscription_free(user_id, free_trial_days):
    """
    Обновляет данные пользователя для бесплатного пробного периода.
    """
    user = get_user_data(user_id)
    current_time = datetime.now()
    if user["subscription_end"]:
        try:
            sub_end = datetime.strptime(user["subscription_end"], "%Y-%m-%d")
            base_time = sub_end if sub_end > current_time else current_time
        except Exception as e:
            logging.error(f"Ошибка при парсинге даты подписки для пользователя {user_id}: {e}")
            base_time = current_time
    else:
        base_time = current_time
    new_end = base_time + timedelta(days=free_trial_days)
    user["subscription_end"] = new_end.strftime("%Y-%m-%d")
    user["tariff"] = {"trial": True, "days": free_trial_days, "price": 0}
    user["key"] = "DUMMY_KEY_123456"  # В будущем заменить на уникальный ключ
    user["address"] = "vpn.example.com"
    user["expired"] = False
    user["free_period_used"] = True
    save_users_data()

def get_main_menu(user_first_name, user_id):
    """
    Формирует главное сообщение с инлайн-кнопками и информацией о пробном периоде.
    """
    user_data = get_user_data(user_id)
    trial_message = ""
    
    if free_period and not user_data["free_period_used"]:
        trial_message = "\n🎁 Как новому пользователю, тебе доступен бесплатный пробный период на 7 дней.\nДля получения выбери его при покупке.\n"

    text = f"""
👋 Привет, {user_first_name}! 🚀 Добро пожаловать в BytePortVPN!

Подключайся и забудь про проблемы с доступом! 🔗
{trial_message}
🎹 Выберите действие:"""
    
    markup = types.InlineKeyboardMarkup()
    btn_buy = types.InlineKeyboardButton("💰 Купить", callback_data="buy")
    btn_profile = types.InlineKeyboardButton("👤 Профиль", callback_data="profile")
    btn_info = types.InlineKeyboardButton("📑 Подробнее о нашем VPN", callback_data="info")
    btn_install = types.InlineKeyboardButton("🔧 Установить", callback_data="install")
    markup.add(btn_buy, btn_profile, btn_install)
    btn_tkg = types.InlineKeyboardButton("📜 ТГК (Отзывы, Новости)", url="http://example.com/tkg")
    btn_support = types.InlineKeyboardButton("🆘 Поддержка", url="http://example.com/support")
    markup.add(btn_info, btn_tkg, btn_support)
    return text, markup

@bot.message_handler(commands=['start'])
def start(message):
    user_first_name = message.from_user.first_name
    user_id = message.from_user.id
    text, markup = get_main_menu(user_first_name, user_id)
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def handle_back_main(call):
    user_first_name = call.from_user.first_name
    user_id = call.from_user.id
    text, markup = get_main_menu(user_first_name, user_id)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# Список допустимых callback_data
valid_callbacks = [
    "buy", "profile", "info", "install", "back_main",
    "period_1", "period_3", "period_6", "period_free",
    "devices_1", "devices_3", "devices_5", "pay",
    "back_buy", "back_devices"
]

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    # Проверка на допустимость callback_data
    if call.data not in valid_callbacks:
        bot.answer_callback_query(call.id, "Некорректный запрос")
        logging.warning(f"Пользователь {user_id} отправил некорректный запрос: {call.data}")
        return

    if call.data == "info":
        text = """
📑 Информация о BytePortVPN\n\n🚀 **Быстрый. Современный. Стабильный.**
BytePortVPN — Это твой пропуск в свободный интернет. Никаких лагов, никаких запретов.

🔒 *Безопасность* — Твои данные под замком, мы даже не ведём логов.
⚡ *Скорость* — Стримы, игры, видео, минимальные потери скорости.
🌍 *Доступ* — Контент из любой точки мира, как должно было быть всегда!
💰 *Цена* — Минимальные цены доступные каждому. Всего *100руб./мес.* - сейчас, это не деньги.
🌐 *Поддержка* — Мы на связи.

Просто подключайся и забудь о границах. *Сводобный интернет доступен каждому!* 🚀🔗
"""
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        btn_buy = types.InlineKeyboardButton("💰 Купить", callback_data="buy")
        markup.add(btn_back, btn_buy)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="markdown")

    elif call.data == "buy":
        text = "💳 Выберите период подписки:\n\n(✳ Чем больше месяцев вы выбираете, тем дешевле подписка в сумме)\nСтоимость одного месяца - 100руб."
        markup = types.InlineKeyboardMarkup()
        btn_1 = types.InlineKeyboardButton("1 месяц", callback_data="period_1")
        btn_3 = types.InlineKeyboardButton("3 месяца (-5%)", callback_data="period_3")
        btn_6 = types.InlineKeyboardButton("6 месяцев (-10%)", callback_data="period_6")
        markup.add(btn_1, btn_3)
        markup.add(btn_6)
        user_data = get_user_data(user_id)
        if free_period and not user_data.get("free_period_used", False):
            btn_free = types.InlineKeyboardButton("🆓 Пробный период (7 дней) [БЕСПЛАТНО]", callback_data="period_free")
            markup.add(btn_free)
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        markup.add(btn_back)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

    elif call.data in ["period_1", "period_3", "period_6", "period_free"]:
        if call.data == "period_free":
            free_trial_duration = 7  # 7 дней пробного периода
            update_user_subscription_free(user_id, free_trial_duration)
            user = get_user_data(user_id)
            text = (f"✅ Бесплатный пробный период активирован!\n\n"
                    f"Подписка до: {user['subscription_end']}\n"
                    f"Ключ: {user['key']}\n"
                    f"Адрес: {user['address']}"
                    "\n\nПриятного использования нашего VPN!")
            markup = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
            btn_install = types.InlineKeyboardButton("🔧 Установить", callback_data="install")
            markup.add(btn_back, btn_install)
            bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)
            logging.info(f"Пользователь {user_id} активировал пробный период")
        else:
            period = int(call.data.split("_")[1])
            discount = 0
            if period == 3:
                discount = 0.05
            elif period == 6:
                discount = 0.10
            with order_lock:
                order_data[user_id] = {"period": period, "discount": discount}
            text = "📱 Выберите количество устройств для подключения:"
            markup = types.InlineKeyboardMarkup()
            btn_1dev = types.InlineKeyboardButton("1 устройство", callback_data="devices_1")
            btn_3dev = types.InlineKeyboardButton("3 устройства", callback_data="devices_3")
            btn_5dev = types.InlineKeyboardButton("5 устройств", callback_data="devices_5")
            btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_buy")
            markup.add(btn_1dev, btn_3dev, btn_5dev)
            markup.add(btn_back)
            bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

    elif call.data in ["devices_1", "devices_3", "devices_5"]:
        devices = int(call.data.split("_")[1])
        with order_lock:
            if user_id not in order_data:
                order_data[user_id] = {}
            order_data[user_id].update({
                "devices": devices,
                "period": order_data.get(user_id, {}).get("period", 1),
                "discount": order_data.get(user_id, {}).get("discount", 0)
            })
            base_price = 100
            total_price = base_price * order_data[user_id]["period"] * devices
            total_price = int(total_price * (1 - order_data[user_id]["discount"]))
            order_data[user_id]["price"] = total_price

        text = (
            f"💰 Итого: {total_price} руб.\n\n"
            f"*Вы покупаете:*\n"
            f"- Период: {order_data[user_id]['period']} месяц(ев)\n"
            f"- Устройства: {devices}\n"
            f"- Цена: {total_price} руб.\n\n"
            "⬇ Нажмите для перенаправления к оплате."
        )
        markup = types.InlineKeyboardMarkup()
        btn_pay = types.InlineKeyboardButton("✅ Оплатить", callback_data="pay")
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_devices")
        markup.add(btn_pay)
        markup.add(btn_back)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="markdown")

    elif call.data == "pay":
        with order_lock:
            if user_id in order_data:
                period = order_data[user_id].get("period", 1)
                devices = order_data[user_id].get("devices", 1)
                price = order_data[user_id].get("price", 100)
                update_user_subscription(user_id, period, devices, price)
                text = (
                    f"✅ Оплата прошла успешно!\n\n"
                    f"📅 Подписка продлена до: {users_data[str(user_id)]['subscription_end']}\n"
                    f"🔑 Ключ: {users_data[str(user_id)]['key']}\n"
                    f"🌐 Адрес: {users_data[str(user_id)]['address']}\n\n"
                    "Приятного использования нашего VPN!"
                )
                markup = types.InlineKeyboardMarkup()
                btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
                btn_install = types.InlineKeyboardButton("🔧 Установить", callback_data="install")
                markup.add(btn_back, btn_install)
                bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)
                logging.info(f"Пользователь {user_id} совершил оплату: {order_data[user_id]}")
                del order_data[user_id]

    elif call.data == "profile":
        user_data = get_user_data(user_id)
        if isinstance(user_data.get("tariff"), dict):
            tariff = user_data["tariff"]
            if tariff.get("trial"):
                tariff_text = f"Пробный период: {tariff.get('days', 'N/A')} дней, {tariff.get('price', 'N/A')} руб."
            else:
                tariff_text = f"{tariff.get('months', 'N/A')} месяц(ев), {tariff.get('devices', 'N/A')} устройств, {tariff.get('price', 'N/A')} руб."
        else:
            tariff_text = user_data.get("tariff", "Отсутствует")
        text = (f"👤 Профиль пользователя ID-{user_id}:\n\n"
                f"📅 Подписка до: {user_data['subscription_end'] or 'Не оформлена'}\n"
                f"📝 Тариф: {tariff_text}\n\n"
                f"🔑 Ключ: {user_data['key'] or 'Нет'}\n"
                f"🌐 Адрес: {user_data['address'] or 'Нет'}")
        if user_data.get("expired", True):
            text += "\n\n⚠️ Подписка истекла. Купите подписку заново, для возобновления доступа."
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        markup.add(btn_back)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

    elif call.data == "install":
        text = ("🔧 Инструкция по подключению к VPN:\n\n"
                "1️⃣ Скачайте прокси-клиент WireGuard.\n"
                "2️⃣ Добавьте новый туннель с полученными данными.\n"
                "3️⃣ Подключитесь к туннелю и наслаждайтесь безопасным соединением!\n\n"
                "💡 При возникновении вопросов обращайтесь в поддержку.")
        markup = types.InlineKeyboardMarkup()
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        btn_support = types.InlineKeyboardButton("🆘 Поддержка", url="http://example.com/support")
        markup.add(btn_back, btn_support)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

    elif call.data == "back_buy":
        text = "💳 Выберите период подписки:\n\n(✳ Чем больше месяцев вы выбираете, тем дешевле подписка в сумме)"
        markup = types.InlineKeyboardMarkup()
        btn_1 = types.InlineKeyboardButton("1 месяц", callback_data="period_1")
        btn_3 = types.InlineKeyboardButton("3 месяца (-5%)", callback_data="period_3")
        btn_6 = types.InlineKeyboardButton("6 месяцев (-10%)", callback_data="period_6")
        markup.add(btn_1, btn_3, btn_6)
        user_data = get_user_data(user_id)
        if free_period and not user_data.get("free_period_used", False):
            btn_free = types.InlineKeyboardButton("🆓 Пробный период (7 дней) [БЕСПЛАТНО]", callback_data="period_free")
            markup.add(btn_free)
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
        markup.add(btn_back)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

    elif call.data == "back_devices":
        text = "📱 Выберите количество устройств для подключения:"
        markup = types.InlineKeyboardMarkup()
        btn_1dev = types.InlineKeyboardButton("1 устройство", callback_data="devices_1")
        btn_3dev = types.InlineKeyboardButton("3 устройства", callback_data="devices_3")
        btn_5dev = types.InlineKeyboardButton("5 устройств", callback_data="devices_5")
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="back_buy")
        markup.add(btn_1dev, btn_3dev, btn_5dev)
        markup.add(btn_back)
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

    bot.answer_callback_query(call.id)

if __name__ == '__main__':
    bot.polling(none_stop=True)
