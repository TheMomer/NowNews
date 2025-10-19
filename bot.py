import asyncio
import logging
import os
import hashlib
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message,
    InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InputMediaAnimation
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN", "")
ALLOWED_USERS = [int(u.strip()) for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()]
LOGIN = os.getenv("LOGIN", "")
PASSWORD_HASH = os.getenv("PASSWORD_HASH", "")
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL", "")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "")
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "")
SEPARATOR = os.getenv("SEPARATOR", " | ")
SHOW_AUTHOR = os.getenv("SHOW_AUTHOR", "true")
SUBSCRIBE_BUTTON_TEXT = os.getenv("SUBSCRIBE_BUTTON_TEXT", "Subscribe")

MEDIA_GROUP_TIMEOUT = 1.5
authenticated_users = set()
media_groups = {}

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

class AuthStates(StatesGroup):
    waiting_login = State()
    waiting_password = State()

def merge_text_and_suffix(text: str, suffix: str) -> str:
    return (text or "") + suffix

def check_password(plain_password: str) -> bool:
    return hashlib.sha256(plain_password.encode()).hexdigest() == PASSWORD_HASH

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        return await message.reply("You do not have access to this bot.")
    await message.reply("Enter login:")
    await state.set_state(AuthStates.waiting_login)

@dp.message(AuthStates.waiting_login)
async def handle_login(message: Message, state: FSMContext):
    await state.update_data(entered_login=message.text)
    await message.reply("Now enter password:")
    await state.set_state(AuthStates.waiting_password)

@dp.message(AuthStates.waiting_password)
async def handle_password(message: Message, state: FSMContext):
    data = await state.get_data()
    login_ok = data.get("entered_login") == LOGIN
    password_ok = check_password(message.text)

    if login_ok and password_ok:
        authenticated_users.add(message.from_user.id)
        await message.reply("Successfully logged in! Now you can send messages.")
    else:
        await message.reply("Incorrect login or password.")
    await state.clear()

@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.reply("Authentication canceled.")

async def send_media_group(media_group_id: str):
    group = media_groups.pop(media_group_id, [])
    if not group:
        return

    suffix = f'\n\n{CHANNEL_NAME} {SEPARATOR} <a href="{CHANNEL_LINK}">{SUBSCRIBE_BUTTON_TEXT}</a>\n\n#news'

    media = []
    for i, msg in enumerate(group):
        caption = (msg.caption or "") + suffix if i == 0 else None
        if msg.photo:
            media.append(InputMediaPhoto(media=msg.photo[-1].file_id, caption=caption))
        elif msg.video:
            media.append(InputMediaVideo(media=msg.video.file_id, caption=caption))
        elif msg.document:
            media.append(InputMediaDocument(media=msg.document.file_id, caption=caption))
        elif msg.audio:
            media.append(InputMediaAudio(media=msg.audio.file_id, caption=caption))
        elif msg.animation:
            media.append(InputMediaAnimation(media=msg.animation.file_id, caption=caption))

    if media:
        try:
            await bot.send_media_group(chat_id=TARGET_CHANNEL, media=media)
        except Exception as e:
            logging.error(f"Error sending media group: {e}")

async def delayed_send(user_id: int, media_group_id: str, state):
    await asyncio.sleep(MEDIA_GROUP_TIMEOUT)
    await send_media_group(user_id, media_group_id, state)

@dp.message(F.text | F.photo | F.video | F.document | F.audio | F.voice | F.animation)
async def forward(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in authenticated_users:
        return await message.reply("First, log in via /start")

    sender_name = message.from_user.full_name

    suffix = f'\n\n{CHANNEL_NAME} {SEPARATOR} <a href="{CHANNEL_LINK}">{SUBSCRIBE_BUTTON_TEXT}</a>\n\n#news'
    if SHOW_AUTHOR == "true":
        suffix += f'\n\nby <b>{sender_name}</b>'

    try:
        if message.media_group_id:
            media_groups.setdefault(message.media_group_id, []).append(message)
            asyncio.create_task(delayed_send(user_id, message.media_group_id, state))
            return

        if message.text:
            new_text = merge_text_and_suffix(message.text, suffix)
            await bot.send_message(chat_id=TARGET_CHANNEL, text=new_text)
        elif message.photo:
            caption = merge_text_and_suffix(message.caption or "", suffix)
            await bot.send_photo(chat_id=TARGET_CHANNEL, photo=message.photo[-1].file_id, caption=caption)
        elif message.document:
            caption = merge_text_and_suffix(message.caption or "", suffix)
            await bot.send_document(chat_id=TARGET_CHANNEL, document=message.document.file_id, caption=caption)
        elif message.video:
            caption = merge_text_and_suffix(message.caption or "", suffix)
            await bot.send_video(chat_id=TARGET_CHANNEL, video=message.video.file_id, caption=caption)
        elif message.audio:
            caption = merge_text_and_suffix(message.caption or "", suffix)
            await bot.send_audio(chat_id=TARGET_CHANNEL, audio=message.audio.file_id, caption=caption)
        elif message.voice:
            caption = merge_text_and_suffix(message.caption or "", suffix)
            await bot.send_voice(chat_id=TARGET_CHANNEL, voice=message.voice.file_id, caption=caption)
        elif message.animation:
            caption = merge_text_and_suffix(message.caption or "", suffix)
            await bot.send_animation(chat_id=TARGET_CHANNEL, animation=message.animation.file_id, caption=caption)
        else:
            await message.reply("Message type not supported (yet).")

    except Exception as e:
        await message.reply(f"Error sending: {e}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
