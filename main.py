import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8798512929:AAGqfPH7T80bgKI1jxxDxkSrfTDZ-aaYy3k"

class ChatStates(StatesGroup):
    menu = State()
    searching = State()
    in_chat = State()

router = Router()

waiting_queue = []
active_chats = {}

# Клавиатуры под интерфейс из скриншота
menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Найти собеседника")],
        [KeyboardButton(text="👥 Поиск по полу")]
    ],
    resize_keyboard=True
)

search_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отменить поиск")]],
    resize_keyboard=True
)

chat_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⏭ Следующий собеседник"), KeyboardButton(text="⏹ Закончить диалог")]
    ],
    resize_keyboard=True
)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(ChatStates.menu)
    await message.answer(
        "Нажмите /search или кнопку ниже, чтобы искать собеседника",
        reply_markup=menu_kb
    )

@router.message(Command("search"))
@router.message(ChatStates.menu, F.text == "🔍 Найти собеседника")
@router.message(ChatStates.in_chat, F.text == "⏭ Следующий собеседник")
async def start_search(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id

    old_companion = active_chats.pop(user_id, None)
    if old_companion:
        active_chats.pop(old_companion, None)
        await bot.send_message(old_companion, "Собеседник завершил общение.", reply_markup=menu_kb)
        await bot.set_state(old_companion, ChatStates.menu)

    if waiting_queue:
        companion_id = waiting_queue.pop(0)
        
        if companion_id == user_id:
            waiting_queue.append(user_id)
            await state.set_state(ChatStates.searching)
            await message.answer("Ищем собеседника...", reply_markup=search_kb)
            return

        active_chats[user_id] = companion_id
        active_chats[companion_id] = user_id

        await state.set_state(ChatStates.in_chat)
        await message.answer(
            "Собеседник найден!\n\n/next - искать следующего\n/stop - завершить диалог", 
            reply_markup=chat_kb
        )

        await bot.send_message(
            companion_id, 
            "Собеседник найден!\n\n/next - искать следующего\n/stop - завершить диалог", 
            reply_markup=chat_kb
        )
    else:
        if user_id not in waiting_queue:
            waiting_queue.append(user_id)
        await state.set_state(ChatStates.searching)
        await message.answer("Ищем собеседника...", reply_markup=search_kb)

@router.message(F.text == "👥 Поиск по полу")
async def search_by_gender(message: Message):
    await message.answer("Функция поиска по полу доступна в разработке. Используйте стандартный поиск: /search")

@router.message(ChatStates.searching, F.text == "❌ Отменить поиск")
async def cancel_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
    
    await state.set_state(ChatStates.menu)
    await message.answer("Поиск отменен.", reply_markup=menu_kb)

@router.message(Command("stop"))
@router.message(ChatStates.in_chat, F.text == "⏹ Закончить диалог")
async def stop_chat(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    companion_id = active_chats.pop(user_id, None)

    if companion_id:
        active_chats.pop(companion_id, None)
        await bot.send_message(companion_id, "Собеседник завершил общение.", reply_markup=menu_kb)
        # Возвращаем состояние второму участнику в меню
        # (в продакшн-режиме через FSM storage)

    await state.set_state(ChatStates.menu)
    await message.answer("Диалог завершен.", reply_markup=menu_kb)

@router.message(Command("next"))
async def cmd_next(message: Message, state: FSMContext, bot: Bot):
    # Команда /next дублирует кнопку поиска следующего
    await start_search(message, state, bot)

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

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
