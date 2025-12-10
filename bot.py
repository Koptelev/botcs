"""Telegram-бот для игры 'Тайный Санта'."""
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from config import BOT_TOKEN, ADMIN_USER_ID
from database import Database

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
FULL_NAME, WISH = range(2)

# Инициализация базы данных
db = Database()

# Описание активности
ABOUT_TEXT = """🎄 Тайный Санта — это весёлая новогодняя традиция, где каждый участник тайно дарит подарок другому!

💝 Стоимость подарка — от 1500 рублей.

Если хочешь — можешь потратить больше, но это необязательно!"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    
    if db.is_registered(user.id):
        participant = db.get_participant(user.id)
        await update.message.reply_text(
            f"Привет, {participant['full_name']}! 👋\n\n"
            "Ты уже зарегистрирован в игре «Тайный Санта».\n\n"
            f"Твоё имя: {participant['full_name']}\n"
            f"Твой желаемый подарок: {participant['wish']}\n\n"
            "Если хочешь обновить данные, начни регистрацию заново командой /register"
        )
    else:
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n\n"
            f"{ABOUT_TEXT}\n\n"
            "Для участия в игре нужно зарегистрироваться.\n"
            "Введи команду /register чтобы начать регистрацию."
        )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /about."""
    await update.message.reply_text(ABOUT_TEXT)


async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начать процесс регистрации."""
    user = update.effective_user
    
    if db.is_registered(user.id):
        await update.message.reply_text(
            "Ты уже зарегистрирован! Если хочешь обновить данные, "
            "продолжай — твои данные будут обновлены.\n\n"
            "Введи своё полное ФИО:"
        )
    else:
        await update.message.reply_text(
            "Отлично! Давай зарегистрируем тебя в игре.\n\n"
            "Введи своё полное ФИО:"
        )
    
    return FULL_NAME


async def register_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить ФИО и запросить желаемый подарок."""
    full_name = update.message.text.strip()
    
    if len(full_name) < 3:
        await update.message.reply_text(
            "ФИО слишком короткое. Пожалуйста, введи полное имя (минимум 3 символа):"
        )
        return FULL_NAME
    
    context.user_data["full_name"] = full_name
    await update.message.reply_text(
        "Отлично! Теперь опиши свой желаемый подарок:"
    )
    
    return WISH


async def register_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить желаемый подарок и завершить регистрацию."""
    wish = update.message.text.strip()
    
    if len(wish) < 5:
        await update.message.reply_text(
            "Описание подарка слишком короткое. Пожалуйста, опиши подробнее (минимум 5 символов):"
        )
        return WISH
    
    user = update.effective_user
    full_name = context.user_data.get("full_name")
    
    # Сохранить в базу данных
    db.register_participant(
        user_id=user.id,
        username=user.username or "",
        full_name=full_name,
        wish=wish
    )
    
    await update.message.reply_text(
        f"🎉 Регистрация завершена!\n\n"
        f"Твоё имя: {full_name}\n"
        f"Твой желаемый подарок: {wish}\n\n"
        "Жди начала распределения! Когда администратор запустит распределение, "
        "ты получишь информацию о том, кому нужно подарить подарок."
    )
    
    context.user_data.clear()
    return ConversationHandler.END


async def register_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменить регистрацию."""
    context.user_data.clear()
    await update.message.reply_text("Регистрация отменена.")
    return ConversationHandler.END


async def assign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Административная команда для распределения участников."""
    user = update.effective_user
    
    # Проверка прав администратора
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ У тебя нет прав для выполнения этой команды.")
        return
    
    # Проверка, выполнено ли уже распределение
    if db.is_assignment_done():
        await update.message.reply_text(
            "⚠️ Распределение уже выполнено. Повторное распределение невозможно."
        )
        return
    
    # Проверка количества участников
    participant_count = db.get_participant_count()
    if participant_count < 2:
        await update.message.reply_text(
            f"❌ Недостаточно участников для распределения. "
            f"Сейчас зарегистрировано: {participant_count}. Нужно минимум 2."
        )
        return
    
    # Получить всех участников
    participants = db.get_all_participants()
    user_ids = [p["user_id"] for p in participants]
    
    # Генерация случайного распределения без самоподарков
    # Используем алгоритм, который гарантирует отсутствие самоподарков
    assignments = []
    max_attempts = 100
    
    for attempt in range(max_attempts):
        receivers = user_ids.copy()
        random.shuffle(receivers)
        assignments = []
        valid = True
        
        for i, giver_id in enumerate(user_ids):
            receiver_id = receivers[i]
            if giver_id == receiver_id:
                valid = False
                break
            assignments.append((giver_id, receiver_id))
        
        if valid:
            break
    
    # Если не удалось найти валидное распределение за max_attempts попыток,
    # используем детерминированный алгоритм
    if not valid or len(assignments) != len(user_ids):
        assignments = []
        receivers = user_ids.copy()
        # Сдвигаем список на 1 позицию
        receivers = receivers[1:] + receivers[:1]
        for i, giver_id in enumerate(user_ids):
            assignments.append((giver_id, receivers[i]))
    
    # Сохранить распределения
    db.save_assignments(assignments)
    db.mark_assignment_done()
    
    # Отправить сообщения участникам
    sent_count = 0
    failed_count = 0
    
    for giver_id, receiver_id in assignments:
        receiver = next(p for p in participants if p["user_id"] == receiver_id)
        
        try:
            await context.bot.send_message(
                chat_id=giver_id,
                text=f"🎁 Ты — Тайный Санта для: {receiver['full_name']}\n\n"
                     f"Он(а) хочет: {receiver['wish']}\n\n"
                     f"Удачи! 🎁"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {giver_id}: {e}")
            failed_count += 1
    
    await update.message.reply_text(
        f"✅ Распределение выполнено!\n\n"
        f"Участников: {participant_count}\n"
        f"Сообщений отправлено: {sent_count}\n"
        f"Ошибок: {failed_count}"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус игры."""
    user = update.effective_user
    
    participant_count = db.get_participant_count()
    is_assigned = db.is_assignment_done()
    
    if user.id == ADMIN_USER_ID:
        status_text = (
            f"📊 Статус игры:\n\n"
            f"Зарегистрировано участников: {participant_count}\n"
            f"Распределение выполнено: {'Да' if is_assigned else 'Нет'}\n\n"
        )
        
        if participant_count > 0:
            participants = db.get_all_participants()
            status_text += "Участники:\n"
            for p in participants:
                status_text += f"• {p['full_name']}\n"
        
        await update.message.reply_text(status_text)
    else:
        if db.is_registered(user.id):
            participant = db.get_participant(user.id)
            assignment = db.get_assignment(user.id)
            
            status_text = (
                f"Твоя регистрация:\n"
                f"Имя: {participant['full_name']}\n"
                f"Желаемый подарок: {participant['wish']}\n\n"
            )
            
            if assignment:
                status_text += (
                    f"🎁 Ты даришь подарок: {assignment['full_name']}\n"
                    f"Он(а) хочет: {assignment['wish']}"
                )
            else:
                status_text += "Распределение ещё не выполнено."
            
            await update.message.reply_text(status_text)
        else:
            await update.message.reply_text(
                "Ты ещё не зарегистрирован. Используй /register для регистрации."
            )


async def export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Административная команда для выгрузки таблицы участников."""
    user = update.effective_user
    
    # Проверка прав администратора
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ У тебя нет прав для выполнения этой команды.")
        return
    
    participants = db.get_all_participants()
    
    if not participants:
        await update.message.reply_text("❌ Нет зарегистрированных участников.")
        return
    
    # Формируем таблицу
    table_text = "📋 ВЫГРУЗКА УЧАСТНИКОВ\n\n"
    table_text += "┌" + "─" * 58 + "┐\n"
    table_text += f"│ {'№':<3} │ {'ФИО':<25} │ {'Желаемый подарок':<25} │\n"
    table_text += "├" + "─" * 58 + "┤\n"
    
    for idx, p in enumerate(participants, 1):
        full_name = p['full_name'][:24] if len(p['full_name']) > 24 else p['full_name']
        wish = p['wish'][:24] if len(p['wish']) > 24 else p['wish']
        table_text += f"│ {idx:<3} │ {full_name:<25} │ {wish:<25} │\n"
    
    table_text += "└" + "─" * 58 + "┘\n"
    table_text += f"\n📊 Всего участников: {len(participants)}\n"
    
    # Если распределение выполнено, добавляем информацию о парах
    if db.is_assignment_done():
        table_text += "\n\n🎁 РАСПРЕДЕЛЕНИЕ ПОДАРКОВ:\n"
        table_text += "┌" + "─" * 58 + "┐\n"
        table_text += f"│ {'Даритель':<28} │ {'Получатель':<28} │\n"
        table_text += "├" + "─" * 58 + "┤\n"
        
        for p in participants:
            assignment = db.get_assignment(p['user_id'])
            if assignment:
                giver_name = p['full_name'][:27] if len(p['full_name']) > 27 else p['full_name']
                receiver_name = assignment['full_name'][:27] if len(assignment['full_name']) > 27 else assignment['full_name']
                table_text += f"│ {giver_name:<28} │ {receiver_name:<28} │\n"
        
        table_text += "└" + "─" * 58 + "┘\n"
    
    # Отправляем таблицу (разбиваем на части, если слишком длинная)
    max_length = 4096  # Максимальная длина сообщения в Telegram
    if len(table_text) <= max_length:
        await update.message.reply_text(f"<pre>{table_text}</pre>", parse_mode="HTML")
    else:
        # Отправляем первую часть
        first_part = table_text[:max_length]
        await update.message.reply_text(f"<pre>{first_part}</pre>", parse_mode="HTML")
        # Отправляем вторую часть, если есть
        if len(table_text) > max_length:
            second_part = table_text[max_length:]
            await update.message.reply_text(f"<pre>{second_part}</pre>", parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню помощи с командами."""
    user = update.effective_user
    is_admin = user.id == ADMIN_USER_ID
    
    help_text = "📚 МЕНЮ КОМАНД\n\n"
    help_text += "Доступные команды:\n\n"
    
    help_text += "🔹 /start - Начать работу с ботом\n"
    help_text += "🔹 /about - Описание игры и правил\n"
    help_text += "🔹 /register - Зарегистрироваться в игре\n"
    help_text += "🔹 /status - Показать статус регистрации\n"
    help_text += "🔹 /help - Показать это меню\n"
    help_text += "🔹 /cancel - Отменить текущую регистрацию\n"
    
    if is_admin:
        help_text += "\n\n👑 АДМИНИСТРАТОРСКИЕ КОМАНДЫ:\n\n"
        help_text += "🔹 /assign - Запустить распределение участников\n"
        help_text += "🔹 /export - Выгрузить таблицу участников и подарков\n"
        help_text += "🔹 /status - Показать общий статус игры\n"
    
    help_text += "\n\n💡 Подсказка: Используй команды с символом / в начале сообщения."
    
    # Создаём inline клавиатуру для быстрого доступа
    keyboard = []
    
    # Первая строка кнопок
    keyboard.append([
        InlineKeyboardButton("📖 О игре", callback_data="help_about"),
        InlineKeyboardButton("📝 Регистрация", callback_data="help_register"),
    ])
    
    # Вторая строка кнопок
    keyboard.append([
        InlineKeyboardButton("📊 Мой статус", callback_data="help_status"),
    ])
    
    if is_admin:
        # Третья строка для админа
        keyboard.append([
            InlineKeyboardButton("👑 Админ-панель", callback_data="help_admin"),
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, reply_markup=reply_markup)


async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки в меню помощи."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    is_admin = user.id == ADMIN_USER_ID
    
    if query.data == "help_about":
        await query.edit_message_text(ABOUT_TEXT)
    elif query.data == "help_register":
        if db.is_registered(user.id):
            participant = db.get_participant(user.id)
            text = (
                f"Ты уже зарегистрирован!\n\n"
                f"Имя: {participant['full_name']}\n"
                f"Желаемый подарок: {participant['wish']}\n\n"
                "Чтобы обновить данные, используй /register"
            )
        else:
            text = (
                "Для регистрации используй команду /register\n\n"
                "Тебе нужно будет ввести:\n"
                "1. Своё полное ФИО\n"
                "2. Описание желаемого подарка"
            )
        await query.edit_message_text(text)
    elif query.data == "help_status":
        participant_count = db.get_participant_count()
        is_assigned = db.is_assignment_done()
        
        if is_admin:
            text = (
                f"📊 Статус игры:\n\n"
                f"Участников: {participant_count}\n"
                f"Распределение: {'Выполнено ✅' if is_assigned else 'Не выполнено ⏳'}\n\n"
                "Используй /status для подробной информации"
            )
        else:
            if db.is_registered(user.id):
                participant = db.get_participant(user.id)
                assignment = db.get_assignment(user.id)
                text = (
                    f"Твоя регистрация:\n"
                    f"Имя: {participant['full_name']}\n"
                    f"Подарок: {participant['wish']}\n\n"
                )
                if assignment:
                    text += f"🎁 Ты даришь: {assignment['full_name']}"
                else:
                    text += "Распределение ещё не выполнено."
            else:
                text = "Ты ещё не зарегистрирован. Используй /register"
        await query.edit_message_text(text)
    elif query.data == "help_admin":
        if is_admin:
            text = (
                "👑 АДМИНИСТРАТОРСКИЕ КОМАНДЫ:\n\n"
                "🔹 /assign - Запустить распределение участников\n"
                "🔹 /export - Выгрузить таблицу участников и подарков\n"
                "🔹 /status - Показать общий статус игры\n\n"
                "Используй эти команды для управления игрой."
            )
        else:
            text = "❌ У тебя нет прав администратора."
        await query.edit_message_text(text)


def main():
    """Запуск бота."""
    # Создать приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчик регистрации
    register_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register_start)],
        states={
            FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_full_name)],
            WISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_wish)],
        },
        fallbacks=[CommandHandler("cancel", register_cancel)],
    )
    
    # Добавить обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", help_command))  # Альтернативная команда для меню
    application.add_handler(register_handler)
    application.add_handler(CommandHandler("assign", assign))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("export", export))
    application.add_handler(CallbackQueryHandler(help_button, pattern="^help_"))
    
    # Запустить бота (long polling)
    logger.info("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

