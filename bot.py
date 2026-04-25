import asyncio
import logging
import random
from datetime import datetime
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, CommandObject, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import *
import database as db
from content import *
from keyboards import *

from scheduler import *

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()
router = Router()

TEST_MODE = False

# ══════════════════════════════════════════════════════════════
#  FSM
# ══════════════════════════════════════════════════════════════
class PhotoState(StatesGroup):
    waiting = State()


class RazborState(StatesGroup):
    waiting_for_photo = State()


class AdminReplyState(StatesGroup):
    waiting_for_reply = State()


class AdminWriteState(StatesGroup):
    waiting_for_msg = State()


class AdminBroadcastState(StatesGroup):
    waiting_for_text = State()
    confirm = State()


class AskQuestionState(StatesGroup):
    waiting_for_question = State()


class WebinarContactState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()


class WebinarSetupState(StatesGroup):
    waiting_for_text = State()
    waiting_for_link = State()
    waiting_for_datetime = State()


class FunnelEditState(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_btn_text = State()
    waiting_for_btn_url = State()


class RazborTemplateEditState(StatesGroup):
    waiting_for_text = State()


class RazborForm(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()


class DiagForm(StatesGroup):
    q1 = State()
    q2 = State()
    q3 = State()
    q4 = State()
    q5 = State()
    q6 = State()
    q7 = State()
    q8 = State()


class AdminReplyDiagState(StatesGroup):
    waiting = State()


class AdminWebinarState(StatesGroup):
    waiting_for_date = State()
    waiting_for_link = State()


# ══════════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ══════════════════════════════════════════════════════════════
def is_admin(chat_id: int, user_id: int) -> bool:
    return user_id == ADMIN_USER_ID or chat_id == ADMIN_GROUP_ID


# ══════════════════════════════════════════════════════════════
#  /cleardb — очистка БД + переотправка закрепа
# ══════════════════════════════════════════════════════════════
@router.message(Command("cleardb"))
async def cmd_cleardb(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_USER_ID:
        return
    old_msg_id = db.get_admin_msg_id()
    if old_msg_id:
        try:
            await bot.delete_message(ADMIN_GROUP_ID, old_msg_id)
        except Exception:
            pass
    db.clear_all_data()
    await state.clear()
    await message.answer("✅ База данных полностью очищена.")
    await _pin_admin_panel()


# ══════════════════════════════════════════════════════════════
#  ДЕНЬ 0 — отправка приветствия ветки
# ══════════════════════════════════════════════════════════════
async def send_day0(target: Message, tag: str):
    data = DAY0[tag]
    video_id = (data.get("video") or "").strip() if isinstance(data, dict) else ""
    text = data.get("text", "") if isinstance(data, dict) else str(data)

    if video_id:
        caption = VIDEO_CAPTIONS.get(tag, "")
        try:
            await bot.send_video(
                chat_id=target.chat.id, video=video_id,
                caption=caption
            )
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Day0 video: {e}")

    await target.answer(text, reply_markup=kb_day0_info(tag), parse_mode="HTML")


# ══════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════
@router.message(CommandStart())
async def cmd_start(message, state: FSMContext):
    await state.clear()
    await message.answer("👇 Выберите действие:", reply_markup=kb_persistent_main())
    await message.answer(WELCOME, reply_markup=kb_main_menu())

@router.message(F.text == "🔙 Главное меню")
async def handle_main_menu_btn(message, state: FSMContext):
    await state.clear()
    await message.answer(WELCOME, reply_markup=kb_main_menu())

@router.callback_query(F.data.startswith("branch:"))
async def cb_branch(callback: CallbackQuery):
    branch = callback.data.split(":")[1]
    if branch == "razbor":
        await callback.message.answer(PROBLEM_ASK, reply_markup=kb_problems())
    elif branch == "webinar":
        # Всегда показываем вебинарный оффер — без упоминания "не провожу"
        await callback.message.answer(WEBINAR_INVITE, reply_markup=kb_webinar_register())
    await callback.answer()


@router.callback_query(F.data.startswith("problem:"))
async def cb_problem(callback: CallbackQuery):
    tg_id = callback.from_user.id
    problem_key = callback.data.split(":")[1]
    tag = {"otoki": "отёки", "asimmetriya": "асимметрия", "oval": "овал", "bol": "боль"}.get(problem_key)
    db.upsert_user(tg_id, tag, callback.from_user.username, callback.from_user.full_name)
    await callback.message.answer(PROBLEM_REPLIES.get(problem_key, ""))
    await asyncio.sleep(1)
    video = VIDEO_OTEKI if problem_key == "otoki" else VIDEO_PODTYAZHKA
    await callback.message.answer_video(video=video)
    await asyncio.sleep(1)
    await callback.message.answer(RAZBOR_OFFER_PRELUDE, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Персональный разбор — 3000 ₽", callback_data="razbor_details")]]))
    await callback.answer()

@router.callback_query(F.data == "razbor_details")
async def cb_razbor_details(callback: CallbackQuery):
    tg_id = callback.from_user.id
    db.mark_razbor_pay_clicked(tg_id)
    await callback.message.answer(RAZBOR_PAY_INFO, reply_markup=kb_razbor_pay(tg_id))
    await callback.answer()


@router.callback_query(F.data == "fast_solve")
async def cb_fast_solve(callback: CallbackQuery):
    await callback.message.answer("Выберите, что вас беспокоит:", reply_markup=kb_problems())
    await callback.answer()


# ─── Информация о курсах ─────────────────────────────────────
@router.callback_query(F.data == "course_landing_info")
async def cb_course_landing_info(callback: CallbackQuery):
    await callback.message.answer(COURSE_LANDING_INFO,
                                  reply_markup=kb_course_landing(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "courses_info")
async def cb_courses_info(callback: CallbackQuery):
    await callback.message.answer(COURSES_INFO, reply_markup=kb_courses_links(),
                                  parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    await callback.message.answer(WELCOME, reply_markup=kb_main_menu())
    await callback.answer()


# ─── VIP ─────────────────────────────────────────────────────
@router.callback_query(F.data == "vip_info")
async def cb_vip_info(callback: CallbackQuery):
    tg_id = callback.from_user.id
    db.mark_vip_clicked(tg_id)
    await callback.message.answer(VIP_DESCRIPTION, reply_markup=kb_vip_buy(tg_id),
                                  parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "buy_vip")
async def cb_buy_vip(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    db.set_last_buy_intent(tg_id, "vip")
    user = db.get_user(tg_id)
    if user and user["phone"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💎 Занять место в VIP",
                                 url=f"{PAY_URL_VIP}?tg_id={tg_id}")
        ]])
        await callback.message.answer(VIP_ACCESS_READY, reply_markup=kb)
    else:
        await state.update_data(course_type="vip")
        await callback.message.answer(PHONE_REQUEST, reply_markup=kb_request_phone())
    await callback.answer()


# ─── Запись на курс / оплата ─────────────────────────────────
@router.callback_query(F.data.startswith("buy_request:"))
async def cb_buy_request(callback: CallbackQuery, state: FSMContext):
    course_type = callback.data.split(":")[1]
    tg_id = callback.from_user.id
    db.mark_buy_click(tg_id)
    db.set_last_buy_intent(tg_id, f"course_{course_type}")

    user = db.get_user(tg_id)
    if user and user["phone"]:
        if course_type == "self":
            kb = kb_pay_self(tg_id)
        elif course_type == "pro":
            kb = kb_pay_pro(tg_id)
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💎 Присоединиться",
                                     url=f"{PAY_URL}?tg_id={tg_id}")
            ]])
        await callback.message.answer(COURSE_ACCESS_READY, reply_markup=kb)
    else:
        await state.update_data(course_type=course_type)
        await callback.message.answer(PHONE_REQUEST, reply_markup=kb_request_phone())
    await callback.answer()


@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext):
    if not message.contact:
        return
    phone = message.contact.phone_number.replace("+", "").strip()
    tg_id = message.from_user.id
    db.update_phone(tg_id, phone)

    data = await state.get_data()
    course_type = data.get("course_type", "all")
    await state.clear()

    if course_type == "vip":
        url = f"{PAY_URL_VIP}?tg_id={tg_id}"
        btn_text = "💎 Занять место в VIP"
    elif course_type == "self":
        url = f"{PAY_URL_SELF}?tg_id={tg_id}"
        btn_text = "🌸 Присоединиться к ОстеоФейс"
    elif course_type == "pro":
        url = f"{PAY_URL_PRO}?tg_id={tg_id}"
        btn_text = "🎓 Присоединиться к ОстеоФейс ПРО"
    elif course_type == "razbor":
        url = f"{PAY_URL_RAZBOR}?tg_id={tg_id}"
        btn_text = "💎 Оплатить разбор — 3 000 ₽"
    else:
        url = f"{PAY_URL}?tg_id={tg_id}"
        btn_text = "💎 Присоединиться"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=btn_text, url=url)
    ]])
    await message.answer(CONTACT_SAVED, reply_markup=kb_persistent_main())
    await message.answer(CONTACT_PLACE_RESERVED, reply_markup=kb)


# ──────────────────────────────────────────────────────────────
#  РАЗБОР ЛИЦА — ПОЛУЧЕНИЕ ФОТО
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "razbor")
async def cb_razbor(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    u = db.get_user(user.id)

    if u and u["razbor_auto_replied"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💎 Записаться на индивидуальный разбор",
                                 callback_data="buy_razbor_personal")
        ]])
        await callback.message.answer(
            "🙌 Вы уже получали базовый разбор.\n\n"
            "Если нужен точный протокол — закажите индивидуальный разбор 👇",
            reply_markup=kb
        )
        return await callback.answer()

    if u and u["razbor_photo_sent"]:
        await callback.message.answer(RAZBOR_ALREADY_SENT, reply_markup=kb_channel())
        return await callback.answer()

    await callback.message.answer(RAZBOR_REQUEST)
    await state.set_state(RazborState.waiting_for_photo)
    await callback.answer()


@router.message(RazborState.waiting_for_photo)
async def receive_razbor_photo(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    if not message.photo and not message.video:
        await message.answer("⚠️ Пожалуйста, пришлите фотографию или видео лица.")
        return
    db.upsert_user(tg_id, "разбор", message.from_user.username, message.from_user.full_name)
    db.mark_razbor_photo_sent(tg_id)
    await state.clear()
    user_info = (
        f"📸 <b>Новое фото на разбор!</b>\n"
        f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
        f"🆔 <code>{tg_id}</code>"
    )
    try:
        if message.photo:
            await bot.send_photo(ADMIN_GROUP_ID, photo=message.photo[-1].file_id, caption=user_info, parse_mode="HTML", reply_markup=kb_admin_question(tg_id))
        elif message.video:
            await bot.send_video(ADMIN_GROUP_ID, video=message.video.file_id, caption=user_info, parse_mode="HTML", reply_markup=kb_admin_question(tg_id))
    except Exception as e:
        logger.error(f"Error: {e}")
    await bot.send_message(tg_id, RAZBOR_PHOTO_REPLY_1)
    await asyncio.sleep(1)
    await bot.send_message(tg_id, RAZBOR_PHOTO_REPLY_2)
    await asyncio.sleep(1)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💎 Персональный разбор — 3 000 ₽", callback_data="buy_razbor_personal")
    ]])
    await bot.send_message(tg_id, RAZBOR_PHOTO_REPLY_3, reply_markup=kb)
    # Апсэлл расширенного разбора 7000
    await asyncio.sleep(1)
    kb_upsell = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚀 Расширенный разбор — 7 000 ₽",
            callback_data="pay_protocol_click"
        )
    ]])
    await bot.send_message(tg_id, UPSELL_7000_IMMEDIATE, reply_markup=kb_upsell)
    db.mark_razbor_auto_replied(tg_id)
    asyncio.create_task(_fast_followup_razbor(tg_id))


async def _fast_followup_razbor(tg_id: int):
    delay1 = 10 if TEST_MODE else 120
    delay2 = 10 if TEST_MODE else 180
    await asyncio.sleep(delay1)
    u = db.get_user(tg_id)
    if u and not u["razbor_pay_clicked"] and not u["razbor_paid"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔍 Разобрать моё лицо", callback_data="buy_razbor_personal")
        ]])
        await bot.send_message(tg_id, RAZBOR_FOLLOWUP_1, reply_markup=kb)
    await asyncio.sleep(delay2)
    u = db.get_user(tg_id)
    if u and not u["razbor_pay_clicked"] and not u["razbor_paid"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎯 Получить разбор", callback_data="buy_razbor_personal")
        ]])
        await bot.send_message(tg_id, RAZBOR_FOLLOWUP_2, reply_markup=kb)


# ─── Клик «Персональный разбор» ──────────────────────────────
@router.callback_query(F.data == "buy_razbor_personal")
async def cb_buy_razbor_personal(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    db.mark_razbor_pay_clicked(tg_id)
    db.set_last_buy_intent(tg_id, "razbor")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💎 Оплатить — 3 000 ₽",
                             url=f"{PAY_URL_RAZBOR}?tg_id={tg_id}")
    ]])
    await callback.message.answer(RAZBOR_PAY_LINK_READY, reply_markup=kb)
    await callback.answer()
    asyncio.create_task(_abandoned_cart_razbor(tg_id))


async def _abandoned_cart_razbor(tg_id: int):
    delay = 10 if TEST_MODE else 900
    await asyncio.sleep(delay)
    u = db.get_user(tg_id)
    if u and u["razbor_pay_clicked"] and not u["razbor_paid"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Задать вопрос", callback_data="ask_question")
        ]])
        await bot.send_message(tg_id, RAZBOR_ABANDONED_CART, reply_markup=kb)


@router.callback_query(F.data == "pay_protocol_click")
async def cb_pay_protocol_click(callback: CallbackQuery):
    tg_id = callback.from_user.id
    db.mark_protocol_pay_click(tg_id)
    db.set_last_buy_intent(tg_id, "protocol")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить 7 000 ₽", url=f"{PAY_URL_PROTOCOL}?tg_id={tg_id}")]
    ])
    await callback.message.answer(f"🎯 Ссылка на оплату Мини-протокола (7 000 ₽):", reply_markup=kb)
    await callback.answer()


@router.message(F.text.lower() == "хочу")
async def handle_hochu(message: Message):
    tg_id = message.from_user.id
    u = db.get_user(tg_id)
    if u and u["razbor_paid"]:
        await message.answer(HOCHU_REPLY_1)
        await asyncio.sleep(1)
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💳 Оформить рассрочку / Купить курс",
                                 url=f"{PAY_URL_SELF}?tg_id={tg_id}")
        ]])
        await message.answer(HOCHU_REPLY_2, reply_markup=kb)
        asyncio.create_task(_doubt_upsell(tg_id))


# ─── Кодовые слова (скрытые ветки) ───────────────────────────
@router.message(F.text.lower().in_({"обучение", "обучение про", "про"}))
async def handle_keyword_obuchenie(message: Message):
    """Кодовое слово «обучение» — запускает ветку ОстеоФейс ПРО."""
    tg_id = message.from_user.id
    db.upsert_user(tg_id, "обучение", message.from_user.username, message.from_user.full_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Узнать про ОстеоФейс ПРО", url=PAY_URL_PRO)],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question")],
    ])
    await message.answer(OBUCHENIE_KEYWORD_MSG, reply_markup=kb, parse_mode="HTML")


@router.message(F.text.lower().in_({"икигай", "ikigai", "диагностика", "предназначение"}))
async def handle_keyword_ikigai(message: Message):
    """Кодовое слово «икигай» — запускает диагностику предназначения."""
    tg_id = message.from_user.id
    db.upsert_user(tg_id, "икигай", message.from_user.username, message.from_user.full_name)
    await message.answer(IKIGAI_KEYWORD_MSG, reply_markup=kb_diag_pay(), parse_mode="HTML")


async def _doubt_upsell(tg_id: int):
    delay = 10 if TEST_MODE else 1800
    await asyncio.sleep(delay)
    u = db.get_user(tg_id)
    if u and not u["is_paid"]:
        await bot.send_message(tg_id, DOUBT_UPSELL)


# ──────────────────────────────────────────────────────────────
#  ВОПРОС ОТ ПОЛЬЗОВАТЕЛЯ
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "ask_question")
async def cb_ask_question(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Напишите свой вопрос:")
    await state.set_state(AskQuestionState.waiting_for_question)
    await callback.answer()


@router.message(AskQuestionState.waiting_for_question)
async def receive_question(message: Message, state: FSMContext):
    user = message.from_user
    if not user:
        return
    header = (
        f"❓ <b>Вопрос от {user.full_name} (@{user.username})</b>\n"
        f"ID: <code>{user.id}</code>\n\n"
    )
    try:
        await bot.send_message(ADMIN_GROUP_ID, header + (message.text or ""),
                               reply_markup=kb_admin_question(user.id),
                               parse_mode="HTML")
        await message.answer("✅ Вопрос отправлен! Ответим в ближайшее время.")
    except Exception as e:
        logger.error(e)
    await state.clear()


# ──────────────────────────────────────────────────────────────
#  ВЕБИНАР
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "webinar:register")
async def cb_webinar_register(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    u = db.get_user(tg_id)

    if u and u["webinar_registered"]:
        await callback.answer("✅ Вы уже зарегистрированы!", show_alert=True)
        return

    # Начинаем сбор данных: имя → телефон
    await callback.message.answer(WEBINAR_COLLECT_NAME)
    await state.set_state(WebinarContactState.waiting_for_name)
    await callback.answer()


@router.message(WebinarContactState.waiting_for_name)
async def webinar_collect_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Напиши своё имя 👇")
        return
    await state.update_data(webinar_name=name)
    await message.answer(WEBINAR_COLLECT_PHONE)
    await state.set_state(WebinarContactState.waiting_for_phone)


@router.message(WebinarContactState.waiting_for_phone)
async def webinar_collect_phone(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    phone = (message.text or "").strip()
    if len(phone) < 5:
        await message.answer("Напиши номер телефона 👇")
        return

    data = await state.get_data()
    name = data.get("webinar_name", message.from_user.full_name)
    await state.clear()

    # Сохраняем пользователя с тегом webinar_reg
    db.upsert_user(tg_id, "webinar_reg", message.from_user.username, name)
    db.update_phone(tg_id, phone)
    db.mark_webinar_registered(tg_id)

    await message.answer(WEBINAR_COLLECT_DONE)

    # Уведомляем администратора
    webinar = db.get_webinar()
    date_str = webinar["webinar_date"] if webinar and webinar["webinar_date"] else "дата не назначена"
    admin_text = (
        f"🎓 <b>Новая запись на вебинар!</b>\n\n"
        f"👤 {name} (@{message.from_user.username})\n"
        f"📱 {phone}\n"
        f"🆔 <code>{tg_id}</code>\n"
        f"📅 Вебинар: {date_str}"
    )
    try:
        await bot.send_message(
            ADMIN_GROUP_ID, admin_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={tg_id}")
            ]]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"[webinar_register] admin notify: {e}")


# ══════════════════════════════════════════════════════════════
#  АДМИНИСТРАТИВНАЯ ПАНЕЛЬ
# ══════════════════════════════════════════════════════════════
async def _pin_admin_panel():
    old = db.get_admin_msg_id()
    if old:
        try:
            await bot.delete_message(ADMIN_GROUP_ID, old)
        except Exception:
            pass
    try:
        await bot.unpin_all_chat_messages(chat_id=ADMIN_GROUP_ID)
        msg = await bot.send_message(
            ADMIN_GROUP_ID,
            "🔧 <b>Панель OsteoFace</b>\n\nНажми нужную кнопку 👇",
            reply_markup=kb_admin_menu(TEST_MODE), parse_mode="HTML"
        )
        await bot.pin_chat_message(ADMIN_GROUP_ID, msg.message_id, disable_notification=True)
        db.set_admin_msg_id(msg.message_id)
    except Exception:
        pass


@router.message(Command("panel"))
async def cmd_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_USER_ID:
        return
    await state.clear()
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(
        "🔧 <b>Панель администратора OsteoFace</b>\n\nВыберите действие:",
        reply_markup=kb_admin_menu(TEST_MODE), parse_mode="HTML"
    )


@router.callback_query(F.data == "admin:panel")
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        return
    await state.clear()
    if callback.message.chat.id == ADMIN_GROUP_ID:
        await _pin_admin_panel()
    else:
        await callback.message.edit_text(
            "🔧 <b>Панель OsteoFace</b>",
            reply_markup=kb_admin_menu(TEST_MODE), parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "admin_cancel", StateFilter("*"))
async def cb_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if callback.message.chat.id == ADMIN_GROUP_ID:
        await _pin_admin_panel()
    else:
        try:
            await callback.message.delete()
        except Exception:
            pass
    await callback.answer()


# ─── Тест-режим ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:toggle_test")
async def cb_toggle_test(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    global TEST_MODE
    TEST_MODE = not TEST_MODE
    setup_scheduler(bot, TEST_MODE)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb_admin_menu(TEST_MODE))
    except Exception:
        pass
    await callback.answer(f"Режим: {'🔴 ТЕСТ' if TEST_MODE else '🟢 БОЕВОЙ'}", show_alert=True)


# ─── Статистика ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    s = db.get_stats()
    by_tag = "\n".join(f"  • {tag}: {cnt}" for tag, cnt in s["by_tag"].items()) or "  нет"
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{s['total']}</b>\n"
        f"💰 Оплатили курс (49к): <b>{s['paid']}</b>\n"
        f"💎 Разборы (3к): <b>{s['razbor_paid']}</b>\n"
        f"🎯 Мини-протокол (7к): <b>{s['protocol_paid']}</b>\n"
        f"🏆 VIP-сопровождение: <b>{s['vip_paid']}</b>\n"
        f"🧬 Диагностика (икигай): <b>{s['diag_paid']}</b>\n"
        f"🎓 Вебинар (зарег.): <b>{s['webinar_registered']}</b>\n"
        f"✅ Были на вебинаре: <b>{s['webinar_attended']}</b>\n"
        f"👆 Кликнули «Купить»: <b>{s['clicked_buy']}</b>\n\n"
        f"По веткам:\n{by_tag}"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  УПРАВЛЕНИЕ ВЕБИНАРАМИ
# ──────────────────────────────────────────────────────────────
@router.message(AdminWebinarState.waiting_for_link)
async def admin_webinar_link(message: Message, state: FSMContext):
    link = message.text.strip()
    data = await state.get_data()

    db.set_webinar(data["webinar_date"], link)
    db.reset_webinar_registrations()

    await state.clear()
    await message.answer("✅ Вебинар установлен!")


@router.callback_query(F.data == "admin:webinar_menu")
async def cb_webinar_menu(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.answer("🗓 <b>Управление вебинарами:</b>",
                                   reply_markup=kb_admin_webinar_menu(),
                                   parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:webinar_info")
async def cb_webinar_info(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    w = db.get_webinar()
    if w and w["is_active"]:
        text = (
            f"🗓 <b>Активный вебинар</b>\n\n"
            f"📅 {w['webinar_date']}\n"
            f"🔗 {w['webinar_link']}\n\n"
            f"Напоминания: "
            f"1д {'✅' if w['reminder_1d_sent'] else '⏳'} | "
            f"2ч {'✅' if w['reminder_2h_sent'] else '⏳'} | "
            f"15м {'✅' if w['reminder_15m_sent'] else '⏳'}"
        )
    else:
        text = "ℹ️ Нет активных вебинаров."
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:set_webinar")
async def cb_admin_set_webinar(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(WebinarSetupState.waiting_for_text)
    await callback.message.answer(
        "📝 <b>Шаг 1/3</b>\n\nВведите текст объявления о вебинаре:",
        reply_markup=kb_cancel_admin(), parse_mode="HTML"
    )
    await callback.answer()


@router.message(WebinarSetupState.waiting_for_text)
async def webinar_setup_text(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        await message.answer("⚠️ Введите текст:", reply_markup=kb_cancel_admin())
        return
    await state.update_data(webinar_broadcast_text=text)
    await state.set_state(WebinarSetupState.waiting_for_link)
    await message.answer("🔗 <b>Шаг 2/3</b>\n\nВведите ссылку на вебинар:",
                         reply_markup=kb_cancel_admin(), parse_mode="HTML")


@router.message(WebinarSetupState.waiting_for_link)
async def webinar_setup_link(message: Message, state: FSMContext):
    link = (message.text or "").strip()
    if not link.startswith("http"):
        await message.answer("⚠️ Ссылка должна начинаться с http://",
                             reply_markup=kb_cancel_admin())
        return
    await state.update_data(webinar_link=link)
    await state.set_state(WebinarSetupState.waiting_for_datetime)
    await message.answer(
        "📅 <b>Шаг 3/3</b>\n\nДата и время:\n"
        "Формат: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>",
        reply_markup=kb_cancel_admin(), parse_mode="HTML"
    )


@router.message(WebinarSetupState.waiting_for_datetime)
async def webinar_setup_datetime(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    try:
        webinar_dt = datetime.strptime(raw, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Пример: <code>15.04.2025 20:00</code>",
                             parse_mode="HTML")
        return
    data = await state.get_data()
    broadcast_text = data.get("webinar_broadcast_text", "")
    link = data.get("webinar_link", "")

    await state.update_data(
        webinar_dt_str=webinar_dt.strftime("%Y-%m-%d %H:%M:%S"),
        webinar_dt_display=raw
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Сохранить и разослать", callback_data="webinar_setup:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="webinar_setup:cancel"),
    ]])
    await message.answer(
        f"📋 <b>Подтверждение:</b>\n\n"
        f"📅 {raw}\n🔗 {link}\n\n"
        f"📢 <i>{broadcast_text}</i>",
        reply_markup=kb, parse_mode="HTML"
    )


@router.callback_query(F.data == "webinar_setup:confirm")
async def webinar_setup_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    data = await state.get_data()
    broadcast_text = data.get("webinar_broadcast_text", "")
    link = data.get("webinar_link", "")
    dt_str = data.get("webinar_dt_str", "")
    dt_display = data.get("webinar_dt_display", "")
    await state.clear()

    db.update_webinar(dt_str, link, broadcast_text)
    users = [u for u in db.get_all_users() if not u["is_paid"]]
    sent = 0
    for u in users:
        try:
            await bot.send_message(u["tg_id"], broadcast_text,
                                   reply_markup=kb_webinar_register())
            await asyncio.sleep(0.05)
            sent += 1
        except Exception:
            pass
    await callback.message.answer(
        f"✅ <b>Вебинар установлен!</b>\n\n📅 {dt_display}\n🔗 {link}\n\n"
        f"📢 Отправлено: {sent} пользователям",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "webinar_setup:cancel")
async def webinar_setup_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Отменено.")
    await callback.answer()


@router.callback_query(F.data == "admin:cancel_webinar")
async def cb_cancel_webinar(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    w = db.get_webinar()
    if w and w["is_active"]:
        await callback.message.answer(
            f"🗑 Отменить вебинар: <b>{w['webinar_date']}</b>?",
            reply_markup=kb_cancel_webinar_confirm(), parse_mode="HTML"
        )
    else:
        await callback.answer("Нет активных вебинаров.", show_alert=True)


@router.callback_query(F.data == "cancel_webinar_confirm")
async def cb_cancel_webinar_confirm(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    db.deactivate_webinar()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("✅ Вебинар отменён!", show_alert=True)


@router.callback_query(F.data == "cancel_webinar_abort")
async def cb_cancel_webinar_abort(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "webinar:join")
async def cb_webinar_join(callback: CallbackQuery):
    w = db.get_webinar()
    if not w or not w["is_active"]:
        await callback.answer("Вебинар недоступен.", show_alert=True)
        return
    db.mark_webinar_attended(callback.from_user.id)
    await callback.message.edit_reply_markup(reply_markup=kb_webinar_link(w["webinar_link"]))
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  ДИАГНОСТИКА ПРЕДНАЗНАЧЕНИЯ
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "diag_yes")
async def cb_diag_yes(callback: CallbackQuery):
    db.mark_diag_clicked(callback.from_user.id)
    await callback.message.answer(DIAG_INFO, reply_markup=kb_diag_pay(), parse_mode="HTML")
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  АНКЕТА РАЗБОР 3000
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "start_razbor_form")
async def start_razbor_form(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RazborForm.q1)
    await callback.message.answer("📝 <b>Вопрос 1/5:</b> Укажите ваш возраст:", parse_mode="HTML")
    await callback.answer()


@router.message(RazborForm.q1)
async def rf_q1(m: Message, state: FSMContext):
    await state.update_data(a1=m.text)
    await state.set_state(RazborForm.q2)
    await m.answer("📝 <b>Вопрос 2/5:</b> Чем занимаетесь?", parse_mode="HTML")


@router.message(RazborForm.q2)
async def rf_q2(m: Message, state: FSMContext):
    await state.update_data(a2=m.text)
    await state.set_state(RazborForm.q3)
    await m.answer("📝 <b>Вопрос 3/5:</b> Что больше всего не нравится в лице?", parse_mode="HTML")


@router.message(RazborForm.q3)
async def rf_q3(m: Message, state: FSMContext):
    await state.update_data(a3=m.text)
    await state.set_state(RazborForm.q4)
    await m.answer("📝 <b>Вопрос 4/5:</b> Есть ли боли в шее / спине?", parse_mode="HTML")


@router.message(RazborForm.q4)
async def rf_q4(m: Message, state: FSMContext):
    await state.update_data(a4=m.text)
    await state.set_state(RazborForm.q5)
    await m.answer("📝 <b>Вопрос 5/5:</b> Что хочешь получить в результате?", parse_mode="HTML")


@router.message(RazborForm.q5)
async def rf_q5(m: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await m.answer("✅ Анкета принята! Ожидайте видеоразбор в ближайшее время 🙏")

    text = (
        f"💎 <b>Анкета (Разбор 3000 ₽)</b>\n"
        f"👤 @{m.from_user.username} | ID: {m.from_user.id}\n\n"
        f"1. Возраст: {data['a1']}\n"
        f"2. Занятие: {data['a2']}\n"
        f"3. Что не нравится: {data['a3']}\n"
        f"4. Боли: {data['a4']}\n"
        f"5. Результат: {m.text}"
    )
    await bot.send_message(ADMIN_GROUP_ID, text,
                           reply_markup=kb_admin_question(m.from_user.id), parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
#  АНКЕТА ДИАГНОСТИКА 9900
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "start_diag_form")
async def start_diag_form(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DiagForm.q1)
    await callback.message.answer("📝 <b>Вопрос 1/8:</b> Ваше имя:", parse_mode="HTML")
    await callback.answer()


@router.message(DiagForm.q1)
async def df_q1(m: Message, state: FSMContext):
    await state.update_data(a1=m.text)
    await state.set_state(DiagForm.q2)
    await m.answer("📝 <b>Вопрос 2/8:</b> Ваш возраст:", parse_mode="HTML")


@router.message(DiagForm.q2)
async def df_q2(m: Message, state: FSMContext):
    await state.update_data(a2=m.text)
    await state.set_state(DiagForm.q3)
    await m.answer("📝 <b>Вопрос 3/8:</b> Чем занимаетесь?", parse_mode="HTML")


@router.message(DiagForm.q3)
async def df_q3(m: Message, state: FSMContext):
    await state.update_data(a3=m.text)
    await state.set_state(DiagForm.q4)
    await m.answer("📝 <b>Вопрос 4/8:</b> Ваш доход сейчас:", parse_mode="HTML")


@router.message(DiagForm.q4)
async def df_q4(m: Message, state: FSMContext):
    await state.update_data(a4=m.text)
    await state.set_state(DiagForm.q5)
    await m.answer("📝 <b>Вопрос 5/8:</b> Что не устраивает прямо сейчас, какая главная боль?",
                   parse_mode="HTML")


@router.message(DiagForm.q5)
async def df_q5(m: Message, state: FSMContext):
    await state.update_data(a5=m.text)
    await state.set_state(DiagForm.q6)
    await m.answer("📝 <b>Вопрос 6/8:</b> Чего хотите на самом деле?", parse_mode="HTML")


@router.message(DiagForm.q6)
async def df_q6(m: Message, state: FSMContext):
    await state.update_data(a6=m.text)
    await state.set_state(DiagForm.q7)
    await m.answer("📝 <b>Вопрос 7/8:</b> Где чувствуете, что «не на своём месте»?",
                   parse_mode="HTML")


@router.message(DiagForm.q7)
async def df_q7(m: Message, state: FSMContext):
    await state.update_data(a7=m.text)
    await state.set_state(DiagForm.q8)
    await m.answer("📝 <b>Вопрос 8/8:</b> Какая жизнь для вас идеальна через 1–3 года?",
                   parse_mode="HTML")


@router.message(DiagForm.q8)
async def df_q8(m: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await m.answer("✅ Анкета принята! Ожидайте результат диагностики в ближайшее время 🙏")

    text = (
        f"🧬 <b>Анкета (Диагностика 9900 ₽)</b>\n"
        f"👤 @{m.from_user.username} | ID: {m.from_user.id}\n\n"
        f"1. Имя: {data['a1']}\n"
        f"2. Возраст: {data['a2']}\n"
        f"3. Занятие: {data['a3']}\n"
        f"4. Доход: {data['a4']}\n"
        f"5. Главная боль: {data['a5']}\n"
        f"6. Чего хочу: {data['a6']}\n"
        f"7. Не на своём месте: {data['a7']}\n"
        f"8. Идеальная жизнь: {m.text}"
    )
    await bot.send_message(ADMIN_GROUP_ID, text,
                           reply_markup=kb_admin_diag_reply(m.from_user.id), parse_mode="HTML")


# ─── Ответ на диагностику с авто-апселлом ────────────────────
@router.callback_query(F.data.startswith("admin_reply_diag:"))
async def cb_admin_reply_diag(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    target_id = int(callback.data.split(":")[1])
    await state.update_data(target_id=target_id)
    await state.set_state(AdminReplyDiagState.waiting)
    await callback.message.answer(
        "🎤 Отправь результат диагностики:\n"
        "После отправки пользователю через 10 минут улетит апселл на курсы."
    )
    await callback.answer()


@router.message(AdminReplyDiagState.waiting)
async def admin_send_diag_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await state.clear()
        return

    try:
        await bot.send_message(target_id, "📩 Результат вашей диагностики:")
        await message.copy_to(chat_id=target_id)
        await message.answer("✅ Отправлено! Таймер авто-апселла (10 мин) запущен.")
        asyncio.create_task(_delayed_diag_upsell(target_id))
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


async def _delayed_diag_upsell(tg_id: int):
    delay = 10 if TEST_MODE else random.randint(300, 600)
    await asyncio.sleep(delay)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌸 Курс ОстеоФейс", callback_data="buy_request:self")],
        [InlineKeyboardButton(text="🏆 VIP-сопровождение", callback_data="vip_info")]
    ])
    try:
        await bot.send_message(tg_id, DIAG_UPSELL_AFTER, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
#  СПИСОК ПОЛЬЗОВАТЕЛЕЙ (пагинация)
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin:users:"))
async def cb_users_list(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    page = int(callback.data.split(":")[2])
    offset = page * db.USERS_PER_PAGE
    users, total = db.get_users_page(offset)

    if not users:
        await callback.message.answer("👥 Пользователей нет.")
        await callback.answer()
        return

    await callback.message.answer(
        f"👥 <b>Пользователи</b> (всего: {total})\n\nВыберите для просмотра 👇",
        reply_markup=kb_users_list(users, page, total),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("user_info:"))
async def cb_user_info(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    parts = callback.data.split(":")
    tg_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    u = db.get_user(tg_id)

    if not u:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    def yn(v): return "✅" if v else "❌"

    info = (
        f"👤 <b>{u['full_name'] or '—'}</b>\n"
        f"🔗 @{u['username'] or '—'} | ID: <code>{tg_id}</code>\n"
        f"📱 Телефон: {u['phone'] or '—'}\n"
        f"🏷 Ветка: {u['tag'] or '—'}\n"
        f"📅 Дата: {u['join_date'] or '—'}\n\n"
        f"💰 Оплатил курс: {yn(u['is_paid'])} {u['paid_date'] or ''}\n"
        f"💎 Разбор оплачен: {yn(u['razbor_paid'])}\n"
        f"🏆 VIP: {yn(u['vip_paid'])}\n\n"
        f"📧 Прогрев: день {u['last_warmup_sent'] or 0}/5\n"
        f"🎯 Вебинар зарег: {yn(u['webinar_registered'])}\n"
        f"✅ Был на вебинаре: {yn(u['webinar_attended'])}\n"
        f"👆 Кликнул купить: {yn(u['clicked_buy'])} {u['click_buy_time'] or ''}\n"
        f"📸 Фото разбора: {yn(u['razbor_photo_sent'])}\n"
        f"💎 Клик на разбор: {yn(u['razbor_pay_clicked'])}\n"
        f"🏆 Клик на VIP: {yn(u['vip_clicked'])}\n"
        f"🔕 Воронка остановлена: {yn(u['funnel_stopped'])}"
    )
    await callback.message.answer(info, reply_markup=kb_user_back(tg_id, page),
                                  parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_write:"))
async def cb_admin_write_btn(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    parts = callback.data.split(":")
    target_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    await state.update_data(target_id=target_id, page=page)
    await callback.message.answer(
        f"✍️ Введите сообщение для пользователя {target_id}:"
    )
    await state.set_state(AdminWriteState.waiting_for_msg)
    await callback.answer()


@router.message(AdminWriteState.waiting_for_msg)
async def admin_write_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_id")

    if not target_id:
        await state.clear()
        return

    try:
        await bot.send_message(target_id, message.text or "")
        await message.answer("✅ Сообщение отправлено!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  РЕДАКТОР ВОРОНКИ
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:edit_funnel_menu")
async def cb_edit_funnel_menu(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.answer(
        "✏️ <b>Редактор воронки</b>\n\nВыберите ветку:",
        reply_markup=kb_funnel_branch_menu(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fedit:"))
async def cb_fedit_branch(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    tag = callback.data.split(":")[1]
    await callback.message.answer(
        f"📅 Ветка <b>{tag}</b>\n\nВыберите день:",
        reply_markup=kb_funnel_day_menu(tag), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fedit_day:"))
async def cb_fedit_day(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, tag, day_str = callback.data.split(":")
    day = int(day_str)
    await state.update_data(fedit_tag=tag, fedit_day=day)

    override = db.get_funnel_content(tag, day)
    if override and override["text"]:
        current = f"📝 Текущий текст:\n\n{override['text']}\n\n"
        if override["media_file_id"]:
            current += f"🖼 Медиафайл: {override['media_type']}"
    else:
        raw = WARMUP.get(tag, {}).get(day, "")
        if isinstance(raw, dict):
            current = f"📝 Текущий текст (дефолт):\n\n{raw.get('text', '')}"
        else:
            current = f"📝 Текущий текст (дефолт):\n\n{raw}"

    await callback.message.answer(
        f"✏️ Ветка: <b>{tag}</b>, День: <b>{day}</b>\n\n"
        f"{current}\n\n"
        "📝 Введите <b>новый текст</b> для этого дня:",
        reply_markup=kb_cancel_admin(), parse_mode="HTML"
    )
    await state.set_state(FunnelEditState.waiting_for_text)
    await callback.answer()


@router.message(FunnelEditState.waiting_for_text)
async def fedit_receive_text(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        await message.answer("⚠️ Текст не может быть пустым:")
        return
    await state.update_data(fedit_text=text)
    await state.set_state(FunnelEditState.waiting_for_media)
    await message.answer(
        "🖼 Теперь отправьте <b>фото или видео</b> к этому дню.\n"
        "Или нажмите «Оставить без медиа».",
        reply_markup=kb_funnel_skip_media(), parse_mode="HTML"
    )


@router.callback_query(F.data == "fedit_skip_media")
async def fedit_skip_media(callback: CallbackQuery, state: FSMContext):
    await state.update_data(fedit_media_id="", fedit_media_type="")
    await state.set_state(FunnelEditState.waiting_for_btn_text)
    await callback.message.answer(
        "🔘 Отправьте <b>текст для кнопки</b> (или нажмите пропустить):",
        reply_markup=kb_funnel_skip_button(), parse_mode="HTML"
    )
    await callback.answer()


@router.message(FunnelEditState.waiting_for_media)
async def fedit_receive_media(message: Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    else:
        await message.answer("⚠️ Это не фото и не видео. Отправьте медиафайл или нажмите «Пропустить».")
        return

    await state.update_data(fedit_media_id=file_id, fedit_media_type=media_type)
    await state.set_state(FunnelEditState.waiting_for_btn_text)
    await message.answer(
        "🔘 Отправьте <b>текст для кнопки</b> (или нажмите пропустить):",
        reply_markup=kb_funnel_skip_button(), parse_mode="HTML"
    )


@router.message(FunnelEditState.waiting_for_btn_text)
async def fedit_receive_btn_text(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        return
    await state.update_data(fedit_btn_text=text.strip())
    await state.set_state(FunnelEditState.waiting_for_btn_url)
    await message.answer("🔗 Теперь отправьте <b>ссылку</b> для этой кнопки:", parse_mode="HTML")


@router.callback_query(F.data == "fedit_skip_btn")
async def fedit_skip_btn(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db.set_funnel_content(
        data["fedit_tag"], data["fedit_day"], data["fedit_text"],
        data.get("fedit_media_id", ""), data.get("fedit_media_type", ""), "", ""
    )
    await state.clear()
    await callback.message.answer(f"✅ День {data['fedit_day']} ветки «{data['fedit_tag']}» обновлён!")
    await callback.answer()


@router.message(FunnelEditState.waiting_for_btn_url)
async def fedit_receive_btn_url(message: Message, state: FSMContext):
    url = (message.text or "").strip()
    if not url.startswith("http"):
        await message.answer("⚠️ Ссылка должна начинаться с http://")
        return

    data = await state.get_data()
    db.set_funnel_content(
        data["fedit_tag"], data["fedit_day"], data["fedit_text"],
        data.get("fedit_media_id", ""), data.get("fedit_media_type", ""),
        data["fedit_btn_text"], url
    )
    await state.clear()
    await message.answer(f"✅ День {data['fedit_day']} ветки «{data['fedit_tag']}» обновлён с новой кнопкой!")


# ──────────────────────────────────────────────────────────────
#  РЕДАКТОР ШАБЛОНА РАЗБОРА
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:edit_razbor_template")
async def cb_edit_razbor_template(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    current = db.get_setting("razbor_template")
    await callback.message.answer(
        f"📝 <b>Текущий шаблон разбора лица:</b>\n\n{current}\n\n"
        "Введите <b>новый шаблон</b>:",
        reply_markup=kb_cancel_admin(), parse_mode="HTML"
    )
    await state.set_state(RazborTemplateEditState.waiting_for_text)
    await callback.answer()


@router.message(RazborTemplateEditState.waiting_for_text)
async def razbor_template_receive(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        await message.answer("⚠️ Текст не может быть пустым:")
        return
    db.set_setting("razbor_template", text)
    await state.clear()
    await message.answer("✅ Шаблон разбора лица обновлён!")


# ──────────────────────────────────────────────────────────────
#  РАССЫЛКА
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin:broadcast_menu")
async def cb_broadcast_menu(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.answer("📤 Выберите аудиторию:",
                                   reply_markup=kb_admin_broadcast_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:"))
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    audience = callback.data.split(":", 1)[1]
    await state.update_data(broadcast_audience=audience)
    await state.set_state(AdminBroadcastState.waiting_for_text)
    labels = {
        "all": "всем", "отёки": "отёки", "подтяжка": "подтяжка",
        "обучение": "обучение", "webinar_reg": "вебинар"
    }
    await callback.message.answer(
        f"✏️ Аудитория: <b>{labels.get(audience, audience)}</b>\n\n"
        "Отправьте текст рассылки:", parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminBroadcastState.waiting_for_text)
async def broadcast_get_text(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        await message.answer("⚠️ Текст не может быть пустым:")
        return
    data = await state.get_data()
    audience = data.get("broadcast_audience", "all")
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminBroadcastState.confirm)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить", callback_data="bcast_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="bcast_cancel"),
    ]])
    await message.answer(
        f"📋 Предпросмотр:\n\n{text}\n\nАудитория: <b>{audience}</b>\n\nПодтвердить?",
        reply_markup=kb, parse_mode="HTML"
    )


@router.callback_query(F.data == "bcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    data = await state.get_data()
    audience = data.get("broadcast_audience", "all")
    text = data.get("broadcast_text", "")
    await state.clear()

    if audience == "all":
        users = db.get_all_users()
    elif audience == "webinar_reg":
        users = db.get_webinar_registered()
    else:
        users = db.get_users_by_tag(audience)

    sent = 0
    for u in users:
        try:
            await bot.send_message(u["tg_id"], text)
            await asyncio.sleep(0.05)
            sent += 1
        except Exception:
            pass
    await callback.message.answer(f"✅ Готово. Отправлено: {sent}/{len(users)}")
    await callback.answer()


@router.callback_query(F.data == "bcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()


# ──────────────────────────────────────────────────────────────
#  ОТВЕТ АДМИНИСТРАТОРА
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin_reply:"))
async def cb_admin_reply_btn(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    target_id = int(callback.data.split(":")[1])
    await state.update_data(target_id=target_id)
    await state.set_state(AdminReplyState.waiting_for_reply)
    await callback.message.answer(
        f"🎤 Ответ пользователю ID {target_id}.\n"
        "Отправь текст, голосовое, видео или кружок:"
    )
    await callback.answer()


@router.message(AdminReplyState.waiting_for_reply)
async def admin_send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    target_id = data.get("target_id")
    if not target_id:
        await state.clear()
        return
    try:
        await bot.send_message(target_id, "📩 Ответ от мастера:")
        await message.copy_to(chat_id=target_id)
        await message.answer("✅ Ответ отправлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()


# ══════════════════════════════════════════════════════════════
#  ВЕБХУК (резервный)
# ══════════════════════════════════════════════════════════════
async def payment_webhook_handler(request: web.Request) -> web.Response:
    if request.headers.get("X-Webhook-Secret", "") != WEBHOOK_SECRET:
        return web.Response(status=403)
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400)

    tg_id_raw = data.get("tg_id") or data.get("metadata", {}).get("tg_id")
    status = data.get("status", "")

    if tg_id_raw and str(status).lower() in ("paid", "success", "completed"):
        try:
            tg_id = int(tg_id_raw)
            user = db.get_user(tg_id)
            if user and not user["is_paid"]:
                db.mark_paid(tg_id)
                await bot.send_message(tg_id, PAYMENT_SUCCESS_COURSE,
                                       reply_markup=kb_payment_success(),
                                       parse_mode="HTML")
        except Exception as e:
            logger.error(f"[webhook] {e}")

    return web.Response(text="ok")


# ══════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════
async def main():
    db.init_db()
    db.init_media_table()
    dp.include_router(router)
    setup_scheduler(bot, TEST_MODE)
    await _upload_media_folder()
    await _pin_admin_panel()
    logger.info(f"Bot started. Mode: {'TEST' if TEST_MODE else 'PRODUCTION'}")
    await dp.start_polling(bot)


async def _upload_media_folder():
    """
    При старте бота загружает все картинки из папки media/ в Telegram
    и сохраняет file_id в БД. Повторно не загружает уже известные файлы.

    Структура папки:
        media/
            oteki_result.jpg        — кейс отёки день 3
            oteki_anatomy.jpg       — анатомия отёки день 4
            podtyazhka_result.jpg   — кейс подтяжка день 3
            webinar_result.jpg      — кейс пост-вебинар шаг 3
            (любые другие .jpg/.png — загрузятся автоматически)
    """
    import os
    media_dir = os.path.join(os.path.dirname(__file__), "media")
    if not os.path.isdir(media_dir):
        logger.info("[media] Папка media/ не найдена — пропускаем загрузку.")
        return

    ADMIN_UPLOAD_CHAT = ADMIN_USER_ID  # загружаем себе в ЛС

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    files = [f for f in os.listdir(media_dir)
             if os.path.splitext(f)[1].lower() in exts]

    if not files:
        logger.info("[media] Папка media/ пуста.")
        return

    uploaded, skipped = 0, 0
    for filename in sorted(files):
        existing = db.get_media_file_id(filename)
        if existing:
            skipped += 1
            continue
        filepath = os.path.join(media_dir, filename)
        try:
            from aiogram.types import FSInputFile
            photo = FSInputFile(filepath, filename=filename)
            msg = await bot.send_photo(
                chat_id=ADMIN_UPLOAD_CHAT,
                photo=photo,
                caption=f"📁 <b>Медиа загружено:</b> {filename}"
            )
            file_id = msg.photo[-1].file_id
            db.set_media_file_id(filename, file_id)
            logger.info(f"[media] Загружено: {filename} → {file_id[:20]}...")
            uploaded += 1
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"[media] Ошибка загрузки {filename}: {e}")

    logger.info(f"[media] Готово: загружено {uploaded}, пропущено {skipped} из {len(files)}.")


@router.message(F.pinned_message, F.chat.id == ADMIN_GROUP_ID)
async def delete_pin_notification(message: Message):
    try:
        await message.delete()
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(main())