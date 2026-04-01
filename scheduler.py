import asyncio
import logging
from datetime import datetime

import aiohttp
from aiogram import Bot

import database as db
from config import MONECLE_API_URL, MONECLE_API_ID, MONECLE_API_KEY, ADMIN_GROUP_ID
from content import (
    WARMUP, WEBINAR_REMIND_1D, WEBINAR_REMIND_2H, WEBINAR_REMIND_15M,
    POST_ATTENDED, POST_NOT_ATTENDED,
    BUY_REMIND_1H, BUY_REMIND_24H,
    RAZBOR_REMIND_1H, RAZBOR_REMIND_24H,
    VIP_REMIND_1H, VIP_REMIND_24H,
    PAYMENT_SUCCESS_COURSE, PAYMENT_SUCCESS_RAZBOR, PAYMENT_SUCCESS_VIP,
)
from keyboards import (
    kb_warmup_day1, kb_warmup_day2, kb_warmup_day3,
    kb_warmup_day4_self, kb_warmup_day4_pro,
    kb_warmup_day5_buy_self, kb_warmup_day5_buy_pro,
    kb_webinar_register, kb_webinar_join,
    kb_post_webinar, kb_pay, kb_payment_success,
    kb_razbor_personal_pay, kb_after_razbor_paid,
    kb_vip_buy, kb_start_razbor_form, kb_start_diag_form
)

logger = logging.getLogger(__name__)

TAGS_SELF = {"отёки", "подтяжка"}
TAG_PRO   = "обучение"


# ══════════════════════════════════════════════════════════════
#  УТИЛИТЫ
# ══════════════════════════════════════════════════════════════
async def safe_send(bot: Bot, tg_id: int, text: str,
                    keyboard=None, parse_mode: str = "HTML") -> bool:
    try:
        await bot.send_message(chat_id=tg_id, text=text,
                               reply_markup=keyboard, parse_mode=parse_mode)
        await asyncio.sleep(0.05)
        return True
    except Exception as e:
        logger.warning(f"[safe_send] {tg_id}: {e}")
        return False


def _warmup_keyboard(day: int, tag: str, tg_id: int,
                     has_webinar: bool):
    if day == 1: return kb_warmup_day1(tag)
    if day == 2: return kb_warmup_day2(tag)
    if day == 3: return kb_warmup_day3(tag)
    if day == 4:
        return kb_warmup_day4_pro(tg_id) if tag == TAG_PRO else kb_warmup_day4_self(tg_id)
    if day == 5:
        if has_webinar:
            return kb_webinar_register()
        return kb_warmup_day5_buy_pro(tg_id) if tag == TAG_PRO else kb_warmup_day5_buy_self(tg_id)
    return None


def _patch_day5_text(text: str, tag: str, has_webinar: bool) -> str:
    if has_webinar:
        return text
    course_name = "на курс ОстеоФейс ПРО" if tag == TAG_PRO else "на курс ОстеоФейс"
    text = text.replace("на мастер-класс", course_name)
    text = text.replace(
        "📅 Присоединяйся — ниже 👇",
        "Подробности и запись — по кнопке ниже 👇"
    )
    return text


def _resolve_warmup_content(tag: str, day: int) -> dict:
    override = db.get_funnel_content(tag, day)
    if override and override["text"]:
        return {
            "text":  override["text"],
            "photo": override["media_file_id"] if override["media_type"] == "photo" else None,
            "video": override["media_file_id"] if override["media_type"] == "video" else None,
            "btn_text": override.get("btn_text", ""),
            "btn_url":  override.get("btn_url", "")
        }

    raw = WARMUP.get(tag, {}).get(day)
    if raw is None:
        return {"text": "", "photo": None, "video": None, "btn_text": "", "btn_url": ""}
    if isinstance(raw, str):
        return {"text": raw, "photo": None, "video": None, "btn_text": "", "btn_url": ""}
    if isinstance(raw, dict):
        return {
            "text":  raw.get("text", ""),
            "photo": raw.get("photo"),
            "video": raw.get("video"),
            "btn_text": "", "btn_url": ""
        }
    return {"text": str(raw), "photo": None, "video": None, "btn_text": "", "btn_url": ""}


# ══════════════════════════════════════════════════════════════
#  JOB 1 — ПРОГРЕВ
#  Боевой: check каждый час; реально сообщение 1 раз в сутки.
#  Тестовый: 1 минута = 1 сутки.
# ══════════════════════════════════════════════════════════════
async def job_daily_warmup(bot: Bot, is_test: bool = False):
    users = db.get_warmup_users()
    now   = datetime.now()

    webinar      = db.get_webinar()
    has_webinar  = bool(webinar and webinar["is_active"] and webinar["webinar_link"])

    for user in users:
        tg_id     = user["tg_id"]
        tag       = user["tag"]
        join_str  = user["join_date"]
        last_sent = user["last_warmup_sent"] or 0

        if tag not in WARMUP:
            continue
        try:
            join_dt = datetime.strptime(join_str, "%Y-%m-%d %H:%M:%S")
            elapsed = (now - join_dt).total_seconds()

            if is_test:
                current_day = int(elapsed / 30)
            else:
                current_day = int(elapsed / 86400)

            next_day = last_sent + 1
            if next_day < 1 or next_day > 5 or next_day > current_day:
                continue

            content = _resolve_warmup_content(tag, next_day)
            text    = content["text"]
            if not text:
                continue

            if next_day == 5:
                text = _patch_day5_text(text, tag, has_webinar)

            if content.get("btn_text") and content.get("btn_url"):
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=content["btn_text"], url=content["btn_url"])
                ]])
            else:
                kb = _warmup_keyboard(next_day, tag, tg_id, has_webinar)

            if content["photo"]:
                try:
                    await bot.send_photo(
                        chat_id=tg_id, photo=content["photo"],
                        caption=text, reply_markup=kb, parse_mode="HTML"
                    )
                except Exception:
                    await safe_send(bot, tg_id, text, kb)
            else:
                await safe_send(bot, tg_id, text, kb)

            if content["video"]:
                await asyncio.sleep(2)
                try:
                    await bot.send_video(
                        chat_id=tg_id, video=content["video"],
                        caption="Видео к сегодняшнему материалу 👇"
                    )
                except Exception:
                    pass

            db.set_last_warmup_sent(tg_id, next_day)

        except Exception as e:
            logger.error(f"[warmup] user {tg_id}: {e}")


# ══════════════════════════════════════════════════════════════
#  JOB 2 — ПОСТ-ВЕБИНАР
# ══════════════════════════════════════════════════════════════
async def job_daily_post_webinar(bot: Bot, is_test: bool = False):
    users = db.get_post_webinar_users()
    now   = datetime.now()

    for user in users:
        tg_id     = user["tg_id"]
        attended  = bool(user["webinar_attended"])
        step      = user["post_webinar_step"]
        start_str = user["post_webinar_start"]
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
            elapsed  = (now - start_dt).total_seconds()
            day = int(elapsed / 30) if is_test else int(elapsed / 86400)

            series    = POST_ATTENDED if attended else POST_NOT_ATTENDED
            max_steps = len(series)

            if step >= max_steps or day < step + 1:
                continue

            entry = series.get(step + 1)
            if isinstance(entry, dict):
                text     = entry.get("text", "")
                photo_id = entry.get("photo")
                if photo_id:
                    try:
                        await bot.send_photo(
                            chat_id=tg_id, photo=photo_id,
                            caption=text, reply_markup=kb_post_webinar(),
                            parse_mode="HTML"
                        )
                        db.increment_post_webinar_step(tg_id)
                        continue
                    except Exception:
                        pass
            else:
                text = entry or ""

            if text:
                await safe_send(bot, tg_id, text, kb_post_webinar())
                db.increment_post_webinar_step(tg_id)

        except Exception as e:
            logger.error(f"[post_webinar] user {tg_id}: {e}")


# ══════════════════════════════════════════════════════════════
#  JOB 3 — ДОЖИМ «КУПИТЬ КУРС» (1ч и 24ч)
# ══════════════════════════════════════════════════════════════
async def job_buy_reminders(bot: Bot, is_test: bool = False):
    users = db.get_buy_reminder_candidates()
    now   = datetime.now()

    for user in users:
        tg_id     = user["tg_id"]
        click_str = user["click_buy_time"]
        sent_1h   = bool(user["buy_reminder_1h_sent"])
        sent_24h  = bool(user["buy_reminder_24h_sent"])
        try:
            click_dt = datetime.strptime(click_str, "%Y-%m-%d %H:%M:%S")
            if is_test:
                val = (now - click_dt).total_seconds()
                c1h  = 30 <= val < 60
                c24h = 60 <= val < 90
            else:
                val  = (now - click_dt).total_seconds() / 3600
                c1h  = 1.0 <= val < 1.5
                c24h = 24.0 <= val < 24.5

            if not sent_1h and c1h:
                if await safe_send(bot, tg_id, BUY_REMIND_1H, kb_pay(tg_id)):
                    db.set_buy_reminder_sent(tg_id, "1h")
            elif not sent_24h and c24h:
                if await safe_send(bot, tg_id, BUY_REMIND_24H, kb_pay(tg_id)):
                    db.set_buy_reminder_sent(tg_id, "24h")

        except Exception as e:
            logger.error(f"[buy_reminders] user {tg_id}: {e}")


# ══════════════════════════════════════════════════════════════
#  JOB 4 — ДОЖИМ «ПЕРСОНАЛЬНЫЙ РАЗБОР» (1ч и 24ч)
# ══════════════════════════════════════════════════════════════
async def job_razbor_reminders(bot: Bot, is_test: bool = False):
    users = db.get_razbor_reminder_candidates()
    now   = datetime.now()

    for user in users:
        tg_id     = user["tg_id"]
        click_str = user["razbor_pay_click_time"]
        sent_1h   = bool(user["razbor_remind_1h_sent"])
        sent_24h  = bool(user["razbor_remind_24h_sent"])
        try:
            click_dt = datetime.strptime(click_str, "%Y-%m-%d %H:%M:%S")
            if is_test:
                val = (now - click_dt).total_seconds()
                c1h  = 30 <= val < 60
                c24h = 60 <= val < 90
            else:
                val  = (now - click_dt).total_seconds() / 3600
                c1h  = 1.0 <= val < 1.5
                c24h = 24.0 <= val < 24.5

            kb = kb_razbor_personal_pay(tg_id)
            if not sent_1h and c1h:
                if await safe_send(bot, tg_id, RAZBOR_REMIND_1H, kb):
                    db.set_razbor_reminder_sent(tg_id, "1h")
            elif not sent_24h and c24h:
                if await safe_send(bot, tg_id, RAZBOR_REMIND_24H, kb):
                    db.set_razbor_reminder_sent(tg_id, "24h")

        except Exception as e:
            logger.error(f"[razbor_reminders] user {tg_id}: {e}")


# ══════════════════════════════════════════════════════════════
#  JOB 5 — ДОЖИМ VIP (1ч и 24ч)
# ══════════════════════════════════════════════════════════════
async def job_vip_reminders(bot: Bot, is_test: bool = False):
    users = db.get_vip_reminder_candidates()
    now   = datetime.now()

    for user in users:
        tg_id     = user["tg_id"]
        click_str = user["vip_click_time"]
        sent_1h   = bool(user["vip_remind_1h_sent"])
        sent_24h  = bool(user["vip_remind_24h_sent"])
        try:
            click_dt = datetime.strptime(click_str, "%Y-%m-%d %H:%M:%S")
            if is_test:
                val = (now - click_dt).total_seconds()
                c1h  = 30 <= val < 60
                c24h = 60 <= val < 90
            else:
                val  = (now - click_dt).total_seconds() / 3600
                c1h  = 1.0 <= val < 1.5
                c24h = 24.0 <= val < 24.5

            kb = kb_vip_buy(tg_id)
            if not sent_1h and c1h:
                if await safe_send(bot, tg_id, VIP_REMIND_1H, kb):
                    db.set_vip_reminder_sent(tg_id, "1h")
            elif not sent_24h and c24h:
                if await safe_send(bot, tg_id, VIP_REMIND_24H, kb):
                    db.set_vip_reminder_sent(tg_id, "24h")

        except Exception as e:
            logger.error(f"[vip_reminders] user {tg_id}: {e}")


# ══════════════════════════════════════════════════════════════
#  JOB 6 — НАПОМИНАНИЯ О ВЕБИНАРЕ
# ══════════════════════════════════════════════════════════════
async def job_webinar_reminders(bot: Bot, is_test: bool = False):
    webinar = db.get_webinar()
    if not webinar or not webinar["is_active"] or not webinar["webinar_date"]:
        return
    try:
        webinar_dt = datetime.strptime(webinar["webinar_date"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return

    now = datetime.now()
    sec_left = (webinar_dt - now).total_seconds()

    if is_test:
        c1d   = 90 <= sec_left <= 120
        c2h   = 60 <= sec_left < 90
        c15m  = 30 <= sec_left < 60
        deact = sec_left <= -30
    else:
        c1d   = 82800 <= sec_left <= 90000 
        c2h   = 5400 <= sec_left <= 9000   
        c15m  = 0 < sec_left <= 1800       
        deact = sec_left <= -3600         

    all_users = [u for u in db.get_all_users() if not u["is_paid"]]
    if not all_users:
        return

    link = webinar["webinar_link"]
    def kb_for(u): return kb_webinar_join() if u["webinar_registered"] else kb_webinar_register()

    if not webinar["reminder_1d_sent"] and c1d:
        d = webinar_dt.strftime("%d.%m.%Y")
        t = webinar_dt.strftime("%H:%M")
        text = WEBINAR_REMIND_1D.format(date=d, time=t)
        for u in all_users:
            await safe_send(bot, u["tg_id"], text, kb_for(u))
        db.set_webinar_reminder_sent("1d")

    elif not webinar["reminder_2h_sent"] and c2h:
        for u in all_users:
            await safe_send(bot, u["tg_id"], WEBINAR_REMIND_2H, kb_for(u))
        db.set_webinar_reminder_sent("2h")

    elif not webinar["reminder_15m_sent"] and c15m:
        for u in all_users:
            await safe_send(bot, u["tg_id"], WEBINAR_REMIND_15M, kb_for(u))
        db.set_webinar_reminder_sent("15m")

    if deact:
        for u in all_users:
            if u["webinar_registered"]:
                db.start_post_webinar(u["tg_id"])
        db.deactivate_webinar()


async def job_diag_reminders(bot: Bot, is_test: bool = False):
    """Дожим для диагностики предназначения (9900₽)"""
    users = db.get_diag_reminders()
    now = datetime.now()
    
    for user in users:
        tg_id = user["tg_id"]
        click_str = user["diag_click_time"]
        sent_1h = bool(user["diag_remind_1h_sent"])
        sent_24h = bool(user["diag_remind_24h_sent"])
        
        if not click_str:
            continue
            
        try:
            click_dt = datetime.strptime(click_str, "%Y-%m-%d %H:%M:%S")
            if is_test:
                val = (now - click_dt).total_seconds()
                c1h = 30 <= val < 60
                c24h = 60 <= val < 90
            else:
                val = (now - click_dt).total_seconds() / 3600
                c1h = 1.0 <= val < 1.5
                c24h = 24.0 <= val < 24.5
            
            from keyboards import kb_diag_pay
            
            if not sent_1h and c1h:
                text = (
                    "Ты не просто так сюда попал.\n\n"
                    "Сейчас у тебя есть шанс понять себя. ⏳\n\n"
                    "Диагностика предназначения — это:\n"
                    "— честный взгляд на твою ситуацию\n"
                    "— где ты сейчас и куда идёшь\n"
                    "— как выйти на деньги и реализацию\n\n"
                    "Стоимость — 9900 ₽"
                )
                if await safe_send(bot, tg_id, text, kb_diag_pay()):
                    db.set_diag_remind_sent(tg_id, "1h")
                    
            elif not sent_24h and c24h:
                text = (
                    "Проблема не в деньгах.\n\n"
                    "Проблема в том, что человек живёт не своим.\n"
                    "Я могу это показать. 👇\n\n"
                    "Диагностика предназначения — 9900 ₽"
                )
                if await safe_send(bot, tg_id, text, kb_diag_pay()):
                    db.set_diag_remind_sent(tg_id, "24h")
                    
        except Exception as e:
            logger.error(f"[diag_reminders] user {tg_id}: {e}")


# ══════════════════════════════════════════════════════════════
#  JOB 7 — ПРОВЕРКА ОПЛАТ ЧЕРЕЗ MONECLE API
# ══════════════════════════════════════════════════════════════
_KNOWN_PAID_ORDERS: set = set()

async def job_check_payments(bot: Bot):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                MONECLE_API_URL,
                data={"method": "GetOrders", "id": MONECLE_API_ID,
                      "key": MONECLE_API_KEY, "count": 200},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    return
                data = await resp.json(content_type=None)

        items = data.get("items", [])
        paid_orders = [
            o for o in items
            if o.get("date_paid") and o.get("date_paid") not in ("", "0000-00-00 00:00:00")
        ]

        for order in paid_orders:
            order_id = str(order.get("order_id", ""))
            if order_id in _KNOWN_PAID_ORDERS:
                continue

            phone_raw = str(order.get("phone", "")).replace("+", "").strip()
            if not phone_raw:
                continue

            user = db.get_user_by_phone(phone_raw)
            if not user:
                _KNOWN_PAID_ORDERS.add(order_id)
                continue

            tg_id = user["tg_id"]
            uname = f"@{user['username']}" if user["username"] else f"ID {tg_id}"
            amount = order.get("total_price", 0)
            intent = user["last_buy_intent"] or "course"
            product = order.get("product_name", "").lower()

            is_diag = ("предназначени" in product) or (int(amount) == 9900)
            is_razbor = ("разбор" in product) or (int(amount) == 3000)
            is_vip = ("vip" in product) or (int(amount) > 10000)

            _KNOWN_PAID_ORDERS.add(order_id)

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            if is_diag and not user.get("diag_paid"):
                db.mark_diag_paid(tg_id)
                try:
                    from keyboards import kb_start_diag_form
                    await bot.send_message(
                        tg_id, 
                        "🎉 Оплата получена! Чтобы я мог составить результат, заполните анкету 👇", 
                        reply_markup=kb_start_diag_form()
                    )
                    kb_ls = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 Написать в ЛС", url=f"tg://user?id={tg_id}")]
                    ])
                    await bot.send_message(
                        ADMIN_GROUP_ID,
                        f"🧬 <b>Оплачена Диагностика!</b>\nПользователь: {uname}\nСумма: {amount} ₽\nУслуга: Диагностика предназначения",
                        reply_markup=kb_ls, parse_mode="HTML"
                    )
                except Exception:
                    pass

            elif is_razbor and not user["razbor_paid"]:
                db.mark_razbor_paid(tg_id)
                try:
                    from keyboards import kb_start_razbor_form
                    await bot.send_message(
                        tg_id, 
                        "🎉 Оплата получена! Заполните короткую анкету перед разбором 👇", 
                        reply_markup=kb_start_razbor_form()
                    )
                    kb_ls = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 Написать в ЛС", url=f"tg://user?id={tg_id}")]
                    ])
                    await bot.send_message(
                        ADMIN_GROUP_ID,
                        f"💎 <b>Оплачен разбор!</b>\nПользователь: {uname}\nСумма: {amount} ₽\nУслуга: Персональный разбор (3000)",
                        reply_markup=kb_ls, parse_mode="HTML"
                    )
                except Exception:
                    pass

            elif is_vip and not user["vip_paid"]:
                with db.get_conn() as conn:
                    conn.execute('UPDATE users SET vip_paid=1, paid_date=? WHERE tg_id=?', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), tg_id))
                try:
                    kb_ls = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 Написать в ЛС", url=f"tg://user?id={tg_id}")]
                    ])
                    await bot.send_message(
                        ADMIN_GROUP_ID, 
                        f"🏆 <b>Оплачен VIP!</b>\nПользователь: {uname}\nСумма: {amount} ₽\nУслуга: VIP-сопровождение",
                        reply_markup=kb_ls, parse_mode="HTML"
                    )
                    await bot.send_message(tg_id, PAYMENT_SUCCESS_VIP, parse_mode="HTML")
                except Exception:
                    pass

            elif not user["is_paid"]:
                db.mark_paid(tg_id)
                product_label = "🎓 Курс ОстеоФейс ПРО" if "pro" in intent or "pro" in product else "🎓 Курс ОстеоФейс"
                try:
                    from keyboards import kb_payment_success
                    kb_ls = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 Написать в ЛС", url=f"tg://user?id={tg_id}")]
                    ])
                    await bot.send_message(
                        ADMIN_GROUP_ID,
                        f"🎉 <b>Новая оплата курса!</b>\nПользователь: {uname}\nСумма: {amount} ₽\nУслуга: {product_label}",
                        reply_markup=kb_ls, parse_mode="HTML"
                    )
                    await bot.send_message(tg_id, PAYMENT_SUCCESS_COURSE, reply_markup=kb_payment_success(), parse_mode="HTML")
                except Exception:
                    pass

    except asyncio.TimeoutError:
        pass
    except Exception as e:
        logger.error(f"[check_payments] {e}")
