import asyncio
import logging
import random
from datetime import datetime

from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, CommandObject, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import kb_funnel_skip_button, kb_course_landing
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    BOT_TOKEN, ADMIN_USER_ID, ADMIN_GROUP_ID,
    WEBHOOK_SECRET, WEBHOOK_HOST, WEBHOOK_PORT, TIMEZONE,
    PAY_URL_SELF, PAY_URL_PRO, PAY_URL, PAY_URL_RAZBOR, PAY_URL_VIP,
)
import database as db
from content import (
    WELCOME, DAY0, RAZBOR_REQUEST, RAZBOR_ALREADY_SENT, RAZBOR_RECEIVED,
    WEBINAR_REGISTERED_OK, WEBINAR_NOT_ACTIVE,
    COURSES_INFO, VIP_DESCRIPTION, VIP_UPSELL_AFTER_RAZBOR,
    PAYMENT_SUCCESS_COURSE, PAYMENT_SUCCESS_RAZBOR, PAYMENT_SUCCESS_VIP,
    WARMUP,
)
from keyboards import (
    kb_main_menu, kb_day0_info, kb_channel,
    kb_courses_links, kb_vip_buy, kb_pay,
    kb_pay_self, kb_pay_pro,
    kb_webinar_register, kb_payment_success,
    kb_request_phone, kb_cancel_admin,
    kb_admin_menu, kb_admin_webinar_menu, kb_admin_broadcast_menu, kb_admin_question,
    kb_cancel_webinar_confirm, kb_after_razbor_paid,
    kb_razbor_personal_pay,
    kb_users_list, kb_user_back,
    kb_funnel_branch_menu, kb_funnel_day_menu, kb_funnel_skip_media, kb_webinar_link, kb_start_razbor_form, kb_start_diag_form, 
    kb_diag_pay, kb_admin_diag_reply
)
from scheduler import (
    job_daily_warmup, job_daily_post_webinar,
    job_buy_reminders, job_razbor_reminders, job_vip_reminders,
    job_webinar_reminders, job_check_payments, job_diag_reminders,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
router = Router()

TEST_MODE = False
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

TAG_MAP = {"otoki": "отёки", "podtyazhka": "подтяжка", "obuchenie": "обучение"}


# ══════════════════════════════════════════════════════════════
#  FSM
# ══════════════════════════════════════════════════════════════
class RazborState(StatesGroup):
    waiting_for_photo = State()


class AdminReplyState(StatesGroup):
    waiting_for_reply = State()

class AdminWriteState(StatesGroup):
    waiting_for_msg = State()

class AdminBroadcastState(StatesGroup):
    waiting_for_text = State()
    confirm          = State()

class AskQuestionState(StatesGroup):
    waiting_for_question = State()

class WebinarSetupState(StatesGroup):
    waiting_for_text     = State()
    waiting_for_link     = State()
    waiting_for_datetime = State()

class FunnelEditState(StatesGroup):
    waiting_for_text  = State()
    waiting_for_media = State()
    waiting_for_btn_text = State()
    waiting_for_btn_url  = State()

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


def setup_scheduler():
    scheduler.remove_all_jobs()
    if TEST_MODE:
        scheduler.add_job(job_daily_warmup,       "interval", seconds=10, args=[bot, True])
        scheduler.add_job(job_daily_post_webinar, "interval", seconds=10, args=[bot, True])
        scheduler.add_job(job_webinar_reminders,  "interval", seconds=10, args=[bot, True])
        scheduler.add_job(job_buy_reminders,      "interval", seconds=10, args=[bot, True])
        scheduler.add_job(job_razbor_reminders,   "interval", seconds=10, args=[bot, True])
        scheduler.add_job(job_vip_reminders,      "interval", seconds=10, args=[bot, True])
        scheduler.add_job(job_diag_reminders,     "interval", seconds=10, args=[bot, True])  # <-- ДОБАВИТЬ
        scheduler.add_job(job_check_payments,     "interval", seconds=10, args=[bot])
        logger.info("Scheduler: TEST MODE")
    else:
        scheduler.add_job(job_daily_warmup,       "interval", hours=1,    args=[bot, False])
        scheduler.add_job(job_daily_post_webinar, "interval", hours=1,    args=[bot, False])
        scheduler.add_job(job_webinar_reminders,  "interval", minutes=10, args=[bot, False])
        scheduler.add_job(job_buy_reminders,      "interval", minutes=30, args=[bot, False])
        scheduler.add_job(job_razbor_reminders,   "interval", minutes=30, args=[bot, False])
        scheduler.add_job(job_vip_reminders,      "interval", minutes=30, args=[bot, False])
        scheduler.add_job(job_diag_reminders,     "interval", minutes=30, args=[bot, False])  # <-- ДОБАВИТЬ
        scheduler.add_job(job_check_payments,     "interval", minutes=2,  args=[bot])
        logger.info("Scheduler: PRODUCTION MODE")


@router.message(Command("cleardb"))
async def cmd_cleardb(message: Message, state: FSMContext):
    if not is_admin(message.chat.id, message.from_user.id):
        return
    db.clear_all_data()
    await state.clear()
    await message.answer("✅ База данных полностью очищена.")

# ══════════════════════════════════════════════════════════════
#  ДЕНЬ 0 — отправка приветствия ветки
# ══════════════════════════════════════════════════════════════
async def send_day0(target: Message, tag: str):
    data     = DAY0[tag]
    video_id = (data.get("video") or "").strip() if isinstance(data, dict) else ""
    text     = data.get("text", "") if isinstance(data, dict) else str(data)

    if video_id:
        captions = {
            "отёки":    "Посмотрите это видео — важно для понимания причин 👆",
            "подтяжка": "Видео о том, почему ткани теряют опору и как это исправить 👆",
        }
        try:
            await bot.send_video(
                chat_id=target.chat.id, video=video_id,
                caption=captions.get(tag, "")
            )
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Day0 video: {e}")

    await target.answer(text, reply_markup=kb_day0_info(tag))


# ══════════════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════════════
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    user = message.from_user
    if not user:
        return

    if message.chat.type in ("group", "supergroup"):
        me = await bot.get_me()
        try:
            await message.reply(f"👋 Напишите мне в личку: @{me.username}")
        except Exception:
            pass
        return

    args  = command.args or ""
    tg_id = user.id

    if args in TAG_MAP:
        tag = TAG_MAP[args]
        db.upsert_user(tg_id, tag, user.username, user.full_name)
        await send_day0(message, tag)
    else:
        await message.answer(WELCOME, reply_markup=kb_main_menu())


# ─── Выбор ветки ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("tag:"))
async def cb_tag_select(callback: CallbackQuery):
    user   = callback.from_user
    choice = callback.data.split(":")[1]
    if choice not in TAG_MAP:
        await callback.answer()
        return
    tag = TAG_MAP[choice]
    db.upsert_user(user.id, tag, user.username, user.full_name)
    await callback.answer()
    await send_day0(callback.message, tag)


# ─── Информация о курсах ─────────────────────────────────────
@router.callback_query(F.data == "course_landing_info")
async def cb_course_landing_info(callback: CallbackQuery):
    text = (
        "🌸 <b>Курс ОстеоФейс</b>\n\n"
        "Система естественного омоложения и восстановления лица без уколов и операций.\n\n"
        "На курсе вы узнаете как:\n"
        "✅ Снимать отеки и восстанавливать лимфоток\n"
        "✅ Подтягивать овал лица и убирать брыли\n"
        "✅ Работать с фасциями и мышцами для стойкого результата\n\n"
        "Узнайте все подробности и программу на нашем сайте 👇"
    )
    await callback.message.answer(text, reply_markup=kb_course_landing(), parse_mode="HTML")
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
        await callback.message.answer("Доступ к VIP-сопровождению сформирован. Жду вас внутри 👇", reply_markup=kb)
    else:
        await state.update_data(course_type="vip")
        await callback.message.answer(
            "Чтобы закрепить за вами место, оставьте номер телефона 👇",
            reply_markup=kb_request_phone()
        )
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
        await callback.message.answer("Доступ готов. Сделайте шаг к изменениям прямо сейчас 👇", reply_markup=kb)
    else:
        await state.update_data(course_type=course_type)
        await callback.message.answer(
            "Чтобы закрепить за вами место, оставьте номер телефона 👇",
            reply_markup=kb_request_phone()
        )
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
        btn_text = "💎 Присоединиться к ОстеоФейс"
    elif course_type == "pro":
        url = f"{PAY_URL_PRO}?tg_id={tg_id}"
        btn_text = "💎 Присоединиться к ОстеоФейс ПРО"
    else:
        url = f"{PAY_URL}?tg_id={tg_id}"
        btn_text = "💎 Присоединиться"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=btn_text, url=url)
    ]])
    await message.answer("✅ Контакт сохранён!", reply_markup=ReplyKeyboardRemove())
    await message.answer("Ваше место закреплено. Оформить участие можно по кнопке ниже 👇", reply_markup=kb)


# ──────────────────────────────────────────────────────────────
#  РАЗБОР ЛИЦА — ПОЛУЧЕНИЕ ФОТО
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "razbor")
async def cb_razbor(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    u = db.get_user(user.id)
    
    if u and u["razbor_auto_replied"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💎 Записаться на индивидуальный разбор", callback_data="buy_razbor_personal")
        ]])
        await callback.message.answer(
            "Вы уже получали базовый разбор.\nЕсли нужен точный протокол — закажите индивидуальный разбор 👇",
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
    user = message.from_user
    if not user:
        return
    if not message.photo:
        await message.answer("⚠️ Это не фото! Пожалуйста, пришлите фотографию лица.")
        return

    tg_id = user.id
    db.upsert_user(tg_id, "разбор", user.username, user.full_name)
    db.mark_razbor_photo_sent(tg_id)

    await message.answer(RAZBOR_RECEIVED)
    await state.clear()

    # Задержка 1: от отправки фото до сообщения "Я посмотрел..."
    # В тесте: 10 секунд. В бою: случайное время от 15 до 45 минут (900-2700 сек)
    delay = 10 if TEST_MODE else random.randint(900, 2700)
    asyncio.create_task(_auto_razbor_reply(tg_id, delay))


async def _auto_razbor_reply(tg_id: int, delay_seconds: int):
    await asyncio.sleep(delay_seconds)

    user = db.get_user(tg_id)
    if not user or user["razbor_auto_replied"]:
        return

    template = db.get_setting("razbor_template")
    kb_razbor_offer = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, хочу разбор за 3000 ₽", callback_data="buy_razbor_personal")],
        [InlineKeyboardButton(text="⏸ Пока нет", callback_data="noop")]
    ])
    try:
        await bot.send_message(tg_id, template, reply_markup=kb_razbor_offer)
        db.mark_razbor_auto_replied(tg_id)

        # Задержка 2: от "Я посмотрел..." до предложения "Диагностики предназначения"
        # В тесте: 15 секунд. В бою: случайное время от 5 до 15 минут (300-900 сек)
        diag_delay = 15 if TEST_MODE else random.randint(300, 900)
        await asyncio.sleep(diag_delay)
        
        kb_diag = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, хочу узнать", callback_data="diag_yes")],
            [InlineKeyboardButton(text="⏸ Нет, спасибо", callback_data="noop")]
        ])
        await bot.send_message(
            tg_id, 
            "Кстати 💡\n\nЯ вижу не только лицо, но и глубже — состояние человека.\n"
            "Иногда причина внешних проблем — не на своём месте в жизни.\n\n"
            "Хочешь, разберу твоё предназначение?", 
            reply_markup=kb_diag
        )
    except Exception as e:
        logger.warning(f"[auto_razbor] user {tg_id}: {e}")


# ─── Клик «Персональный разбор» ──────────────────────────────
@router.callback_query(F.data == "buy_razbor_personal")
async def cb_buy_razbor_personal(callback: CallbackQuery, state: FSMContext):
    tg_id = callback.from_user.id
    db.mark_razbor_pay_clicked(tg_id)
    db.set_last_buy_intent(tg_id, "razbor")

    user = db.get_user(tg_id)
    if user and user["phone"]:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💎 Заказать персональный разбор",
                                 url=f"{PAY_URL_RAZBOR}?tg_id={tg_id}")
        ]])
        await callback.message.answer("Заявка сформирована. Как только всё будет готово, я приступлю к разбору 👇", reply_markup=kb)
    else:
        await state.update_data(course_type="razbor")
        await callback.message.answer(
            "Чтобы оформить заказ, оставьте номер телефона 👇",
            reply_markup=kb_request_phone()
        )
    await callback.answer()


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
async def cb_webinar_register(callback: CallbackQuery):
    webinar = db.get_webinar()
    if not webinar or not webinar["is_active"]:
        await callback.message.answer(WEBINAR_NOT_ACTIVE, reply_markup=kb_channel())
        await callback.answer()
        return
    
    u = db.get_user(callback.from_user.id)
    if u and u["webinar_registered"]:
        await callback.answer("✅ Вы уже зарегистрированы!", show_alert=True)
        return
        
    db.mark_webinar_registered(callback.from_user.id)
    await callback.message.answer(WEBINAR_REGISTERED_OK)
    await callback.answer("✅ Зарегистрировано!")


# ══════════════════════════════════════════════════════════════
#  АДМИНИСТРАТИВНАЯ ПАНЕЛЬ
# ══════════════════════════════════════════════════════════════

async def _pin_admin_panel():
    try:
        await bot.unpin_all_chat_messages(chat_id=ADMIN_GROUP_ID)
    except Exception:
        pass
    old = db.get_admin_msg_id()
    if old:
        try:
            await bot.delete_message(ADMIN_GROUP_ID, old)
        except Exception:
            pass
    try:
        msg = await bot.send_message(
            ADMIN_GROUP_ID,
            "🔧 <b>Панель OsteoFace</b>\n\nНажми нужную кнопку 👇",
            reply_markup=kb_admin_menu(TEST_MODE), parse_mode="HTML"
        )
        await bot.pin_chat_message(ADMIN_GROUP_ID, msg.message_id,
                                   disable_notification=True)
        db.set_admin_msg_id(msg.message_id)
    except Exception:
        pass


@router.message(Command("panel"))
async def cmd_panel(message: Message, state: FSMContext):
    if not is_admin(message.chat.id, message.from_user.id):
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
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await callback.message.answer(
        "🔧 <b>Панель OsteoFace</b>",
        reply_markup=kb_admin_menu(TEST_MODE), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_cancel", StateFilter("*"))
async def cb_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Отменено.")


# ─── Тест-режим ──────────────────────────────────────────────
@router.callback_query(F.data == "admin:toggle_test")
async def cb_toggle_test(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    global TEST_MODE
    TEST_MODE = not TEST_MODE
    setup_scheduler()
    await callback.message.edit_reply_markup(reply_markup=kb_admin_menu(TEST_MODE))
    await callback.answer(f"Режим: {'ТЕСТ' if TEST_MODE else 'БОЕВОЙ'}", show_alert=True)


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
        f"👥 Всего: <b>{s['total']}</b>\n"
        f"💰 Оплатили курс: <b>{s['paid']}</b>\n"
        f"💎 Разборы оплачены: <b>{s['razbor_paid']}</b>\n"
        f"🏆 VIP оплачен: <b>{s['vip_paid']}</b>\n"
        f"🎯 Вебинар зарег: <b>{s['webinar_registered']}</b>\n"
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
    link           = data.get("webinar_link", "")

    await state.update_data(
        webinar_dt_str=webinar_dt.strftime("%Y-%m-%d %H:%M:%S"),
        webinar_dt_display=raw
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Сохранить и разослать", callback_data="webinar_setup:confirm"),
        InlineKeyboardButton(text="❌ Отмена",    callback_data="webinar_setup:cancel"),
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
    link           = data.get("webinar_link", "")
    dt_str         = data.get("webinar_dt_str", "")
    dt_display     = data.get("webinar_dt_display", "")
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

@router.callback_query(F.data == "diag_yes")
async def cb_diag_yes(callback: CallbackQuery):
    db.mark_diag_clicked(callback.from_user.id)
    text = (
        "Наше тело и лицо всегда отражают то, что происходит внутри. "
        "И часто главная причина застоя в жизни — это попытка идти чужим путем.\n\n"
        "Это не авто-тест из интернета. Это глубокая индивидуальная диагностика твоего предназначения.\n"
        "Я покажу тебе:\n"
        "🔹 Твои истинные таланты, которые сейчас спят.\n"
        "🔹 Ключевые ошибки, которые блокируют твой успех.\n"
        "🔹 Куда двигаться, чтобы реализовываться в кайф, а не через выгорание.\n"
        "🔹 Как монетизировать свой потенциал и легко выйти на новый уровень дохода.\n\n"
        "Я запишу для тебя детальное личное видео. "
        "Это будет твой персональный навигатор, который поможет расставить всё на свои места.\n\n"
        "Стоимость — 9 900 ₽"
    )
    await callback.message.answer(text, reply_markup=kb_diag_pay())
    await callback.answer()


# --- Анкета Разбор 3000 ---
@router.callback_query(F.data == "start_razbor_form")
async def start_razbor_form(callback: CallbackQuery, state: FSMContext):
    await state.set_state(RazborForm.q1)
    await callback.message.answer("📝 Вопрос 1/5: Укажите ваш возраст:")
    await callback.answer()


@router.message(RazborForm.q1)
async def rf_q1(m: Message, state: FSMContext):
    await state.update_data(a1=m.text)
    await state.set_state(RazborForm.q2)
    await m.answer("📝 Вопрос 2/5: Чем занимаетесь?")


@router.message(RazborForm.q2)
async def rf_q2(m: Message, state: FSMContext):
    await state.update_data(a2=m.text)
    await state.set_state(RazborForm.q3)
    await m.answer("📝 Вопрос 3/5: Что больше всего не нравится в лице?")


@router.message(RazborForm.q3)
async def rf_q3(m: Message, state: FSMContext):
    await state.update_data(a3=m.text)
    await state.set_state(RazborForm.q4)
    await m.answer("📝 Вопрос 4/5: Есть ли боли в шее / спине?")


@router.message(RazborForm.q4)
async def rf_q4(m: Message, state: FSMContext):
    await state.update_data(a4=m.text)
    await state.set_state(RazborForm.q5)
    await m.answer("📝 Вопрос 5/5: Что хочешь получить в результате?")


@router.message(RazborForm.q5)
async def rf_q5(m: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await m.answer("✅ Анкета принята! Ожидайте видеоразбор в ближайшее время.")
    
    text = (
        f"💎 <b>Анкета (Разбор 3000 ₽)</b>\n"
        f"👤 @{m.from_user.username} | ID: {m.from_user.id}\n\n"
        f"1. Возраст: {data['a1']}\n"
        f"2. Занятие: {data['a2']}\n"
        f"3. Что не нравится: {data['a3']}\n"
        f"4. Боли: {data['a4']}\n"
        f"5. Результат: {m.text}"
    )
    await bot.send_message(ADMIN_GROUP_ID, text, reply_markup=kb_admin_question(m.from_user.id), parse_mode="HTML")


# --- Анкета Диагностика 9900 ---
@router.callback_query(F.data == "start_diag_form")
async def start_diag_form(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DiagForm.q1)
    await callback.message.answer("📝 Вопрос 1/8: Ваше имя:")
    await callback.answer()


@router.message(DiagForm.q1)
async def df_q1(m: Message, state: FSMContext):
    await state.update_data(a1=m.text)
    await state.set_state(DiagForm.q2)
    await m.answer("📝 Вопрос 2/8: Ваш возраст:")


@router.message(DiagForm.q2)
async def df_q2(m: Message, state: FSMContext):
    await state.update_data(a2=m.text)
    await state.set_state(DiagForm.q3)
    await m.answer("📝 Вопрос 3/8: Чем занимаетесь?")


@router.message(DiagForm.q3)
async def df_q3(m: Message, state: FSMContext):
    await state.update_data(a3=m.text)
    await state.set_state(DiagForm.q4)
    await m.answer("📝 Вопрос 4/8: Ваш доход сейчас:")


@router.message(DiagForm.q4)
async def df_q4(m: Message, state: FSMContext):
    await state.update_data(a4=m.text)
    await state.set_state(DiagForm.q5)
    await m.answer("📝 Вопрос 5/8: Что не устраивает прямо сейчас, какая главная боль?")


@router.message(DiagForm.q5)
async def df_q5(m: Message, state: FSMContext):
    await state.update_data(a5=m.text)
    await state.set_state(DiagForm.q6)
    await m.answer("📝 Вопрос 6/8: Чего хотите на самом деле?")


@router.message(DiagForm.q6)
async def df_q6(m: Message, state: FSMContext):
    await state.update_data(a6=m.text)
    await state.set_state(DiagForm.q7)
    await m.answer("📝 Вопрос 7/8: Где чувствуете, что «не на своём месте»?")


@router.message(DiagForm.q7)
async def df_q7(m: Message, state: FSMContext):
    await state.update_data(a7=m.text)
    await state.set_state(DiagForm.q8)
    await m.answer("📝 Вопрос 8/8: Какая жизнь для вас идеальна через 1-3 года?")


@router.message(DiagForm.q8)
async def df_q8(m: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await m.answer("✅ Анкета принята! Ожидайте результат диагностики в ближайшее время.")
    
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
    await bot.send_message(ADMIN_GROUP_ID, text, reply_markup=kb_admin_diag_reply(m.from_user.id), parse_mode="HTML")


# --- Ответ на диагностику с АВТО-АПСЕЛЛОМ ---
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
    # В тесте: 10 секунд. В бою: случайное время от 5 до 10 минут (300-600 секунд)
    delay = 10 if TEST_MODE else random.randint(300, 600)
    await asyncio.sleep(delay)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Курс ОстеоФейс", callback_data="buy_request:self")],
        [InlineKeyboardButton(text="🏆 VIP Сопровождение", callback_data="vip_info")]
    ])
    text = (
        "Теперь важно не просто понять, а изменить результат.\n\n"
        "Есть 2 варианта:\n"
        "1. Сделать всё самому (курс)\n"
        "2. Сделать быстрее со мной (сопровождение)"
    )
    try: 
        await bot.send_message(tg_id, text, reply_markup=kb)
    except Exception: 
        pass

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
#  СПИСОК ПОЛЬЗОВАТЕЛЕЙ (пагинация)
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("admin:users:"))
async def cb_users_list(callback: CallbackQuery):
    if not is_admin(callback.message.chat.id, callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    page   = int(callback.data.split(":")[2])
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
    parts  = callback.data.split(":")
    tg_id  = int(parts[1])
    page   = int(parts[2]) if len(parts) > 2 else 0
    u      = db.get_user(tg_id)

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

    # Показываем текущее содержимое
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

@router.message(FunnelEditState.waiting_for_btn_text)
async def fedit_receive_btn_text(message: Message, state: FSMContext):
    text = message.text or ""
    if not text.strip():
        return
    await state.update_data(fedit_btn_text=text.strip())
    await state.set_state(FunnelEditState.waiting_for_btn_url)
    await message.answer("🔗 Теперь отправьте <b>ссылку</b> для этой кнопки:", parse_mode="HTML")

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

@router.callback_query(F.data == "fedit_skip_media")
async def fedit_skip_media(callback: CallbackQuery, state: FSMContext):
    await state.update_data(fedit_media_id="", fedit_media_type="")
    await state.set_state(FunnelEditState.waiting_for_btn_text)
    await callback.message.answer(
        "🔘 Отправьте <b>текст для кнопки</b> (или нажмите пропустить):",
        reply_markup=kb_funnel_skip_button(), parse_mode="HTML"
    )
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

@router.message(FunnelEditState.waiting_for_media)
async def fedit_receive_media(message: Message, state: FSMContext):
    if message.photo:
        file_id   = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id   = message.video.file_id
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
        InlineKeyboardButton(text="❌ Отмена",    callback_data="bcast_cancel"),
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
    text     = data.get("broadcast_text", "")
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
    status    = data.get("status", "")

    if tg_id_raw and str(status).lower() in ("paid", "success", "completed"):
        try:
            tg_id = int(tg_id_raw)
            user  = db.get_user(tg_id)
            if user and not user["is_paid"]:
                db.mark_paid(tg_id)
                await bot.send_message(tg_id, PAYMENT_SUCCESS_COURSE,
                                       reply_markup=kb_payment_success())
        except Exception as e:
            logger.error(f"[webhook] {e}")

    return web.Response(text="ok")


async def start_webhook_server():
    app = web.Application()
    app.router.add_post("/webhook/monecle", payment_webhook_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT).start()
    logger.info(f"Webhook server on {WEBHOOK_HOST}:{WEBHOOK_PORT}")


# ══════════════════════════════════════════════════════════════
#  ЗАПУСК
# ══════════════════════════════════════════════════════════════
async def main():
    db.init_db()
    dp.include_router(router)
    setup_scheduler()
    scheduler.start()
    await start_webhook_server()
    await _pin_admin_panel()
    logger.info(f"Bot started. Mode: {'TEST' if TEST_MODE else 'PRODUCTION'}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
