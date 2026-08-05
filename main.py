import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

# Вставь свой токен сюда
TOKEN = "8798512929:AAGqfPH7T8ObgKI1jxxDxkSrfTDZ-aaYy3k"

# Состояния пользователя в боте
class ChatStates(StatesGroup):
    menu = State()          # Главное меню
    searching = State()     # Ищет собеседника
    in_chat = State()       # Общается с кем-то

router = Router()

# Среда хранения в памяти (для простоты)
waiting_queue = []          # Очередь пользователей, ищущих собеседника
active_chats = {}           # Словарь активных пар: {user_id: companion_id}

# Клавиатуры
menu_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔍 Найти собеседника")]],
    resize_keyboard=True
)

search_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отменить поиск")]],
    resize_keyboard=True
)

chat_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏹ Остановить диалог"), KeyboardButton(text="⏭ Следующий")]
    ],
    resize_keyboard=True
)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(ChatStates.menu)
    await message.answer(
        "Привет! Это анонимный чат-бот.\nНажми кнопку ниже, чтобы найти собеседника.",
        reply_markup=menu_kb
    )

@router.message(ChatStates.menu, F.text == "🔍 Найти собеседника")
@router.message(ChatStates.in_chat, F.text == "⏭ Следующий")
async def start_search(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id

    # Если пользователь уже был с кем-то в чате и нажал "Следующий", разрываем старую связь
    old_companion = active_chats.pop(user_id, None)
    if old_companion:
        active_chats.pop(old_companion, None)
        await bot.send_message(old_companion, "Собеседник завершил диалог.", reply_markup=menu_kb)
        # Возвращаем бывшего собеседника в меню
        await bot.set_state(old_companion, ChatStates.menu) # Упрощенно через хранилище состояния в памяти (для примера)

    # Проверяем, есть ли кто-то в очереди
    if waiting_queue:
        companion_id = waiting_queue.pop(0)
        
        # Если случайно достали самого себя (на всякий случай)
        if companion_id == user_id:
            waiting_queue.append(user_id)
            await state.set_state(ChatStates.searching)
            await message.answer("Ищем собеседника...", reply_markup=search_kb)
            return

        # Связываем пользователей
        active_chats[user_id] = companion_id
        active_chats[companion_id] = user_id

        # Меняем состояния
        await state.set_state(ChatStates.in_chat)
        await message.answer("Собеседник найден! Можете общаться.", reply_markup=chat_kb)

        # Уведомляем второго участника
        await bot.send_message(companion_id, "Собеседник найден! Можете общаться.", reply_markup=chat_kb)
        # Важно: в реальном проекте состояние второго участника тоже переключается через FSM storage
    else:
        # Добавляем в очередь
        if user_id not in waiting_queue:
            waiting_queue.append(user_id)
        await state.set_state(ChatStates.searching)
        await message.answer("Ищем собеседника...", reply_markup=search_kb)

@router.message(ChatStates.searching, F.text == "❌ Отменить поиск")
async def cancel_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
    
    await state.set_state(ChatStates.menu)
    await message.answer("Поиск отменен.", reply_markup=menu_kb)

@router.message(ChatStates.in_chat, F.text == "⏹ Остановить диалог")
async def stop_chat(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    companion_id = active_chats.pop(user_id, None)

    if companion_id:
        active_chats.pop(companion_id, None)
        await bot.send_message(companion_id, "Собеседник покинул чат.", reply_markup=menu_kb)

    await state.set_state(ChatStates.menu)
    await message.answer("Диалог завершен.", reply_markup=menu_kb)

# Пересылка любых сообщений (текст, фото, видео, голосовые, стикеры) собеседнику
@router.message(ChatStates.in_chat)
async def forward_message(message: Message, bot: Bot):
    user_id = message.from_user.id
    companion_id = active_chats.get(user_id)

    if companion_id:
        await message.copy_to(companion_id)
    else:
        await message.answer("Ошибка: собеседник не найден.", reply_markup=menu_kb)
        await state.set_state(ChatStates.menu)

async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Пропуск старых апдейтов при запуске
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
