from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from config import (
    CHANNEL_URL, PAY_URL, PAY_URL_SELF, PAY_URL_PRO,
    PAY_URL_RAZBOR, PAY_URL_VIP, COURSE_URL, STUDENTS_CHAT_URL,
    PAY_URL_PROTOCOL
)


# ════════════════════════════════════════════════════════════
#  ОСНОВНЫЕ МЕНЮ
# ════════════════════════════════════════════════════════════

def kb_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Быстро убрать проблему (разбор)", callback_data="fast_solve")],
        [InlineKeyboardButton(text="🎓 Понять систему (вебинар)", callback_data="branch:webinar")],
    ])

def kb_protocol_pay(tg_id: int) -> InlineKeyboardMarkup:
    """Оплата мини-протокола 7000₽"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💊 Получить протокол — 7 000 ₽", callback_data="pay_protocol_click")],
    ])


def kb_persistent_main() -> ReplyKeyboardMarkup:
    """Постоянная клавиатура с кнопкой возврата в главное меню"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔙 Главное меню")]],
        resize_keyboard=True,
        is_persistent=True
    )


# ════════════════════════════════════════════════════════════
#  ПРОБЛЕМЫ И ТЕГИ
# ════════════════════════════════════════════════════════════

def kb_problems() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💧 Отёки", callback_data="problem:otoki")],
        [InlineKeyboardButton(text="⚖️ Асимметрия", callback_data="problem:asimmetriya")],
        [InlineKeyboardButton(text="📐 Овал лица", callback_data="problem:oval")],
        [InlineKeyboardButton(text="💥 Боль", callback_data="problem:bol")],
    ])


def kb_problem_selection() -> InlineKeyboardMarkup:
    """Альтернативный выбор проблем"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💧 Отёки", callback_data="tag:otoki")],
        [InlineKeyboardButton(text="⚖️ Асимметрия", callback_data="tag:asimmetriya")],
        [InlineKeyboardButton(text="📐 Овал лица", callback_data="tag:oval")],
        [InlineKeyboardButton(text="💥 Боль", callback_data="tag:bol")],
    ])


# ════════════════════════════════════════════════════════════
#  ПЛАТЕЖНЫЕ КЛАВИАТУРЫ
# ════════════════════════════════════════════════════════════

def kb_razbor_pay(tg_id: int) -> InlineKeyboardMarkup:
    """Оплата разбора 3000₽"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Получить разбор — 3 000 ₽", url=f"{PAY_URL_RAZBOR}?tg_id={tg_id}")],
    ])


def kb_course_pay(tg_id: int) -> InlineKeyboardMarkup:
    """Оплата курса 49000₽"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Иду на курс — 49 000 ₽", url=f"{PAY_URL_SELF}?tg_id={tg_id}")],
    ])


def kb_pay_self(tg_id: int) -> InlineKeyboardMarkup:
    """Оплата курса ОстеоФейс"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Присоединиться к курсу ОстеоФейс",
                              url=f"{PAY_URL_SELF}?tg_id={tg_id}")],
    ])


def kb_pay_pro(tg_id: int) -> InlineKeyboardMarkup:
    """Оплата курса ОстеоФейс ПРО"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Присоединиться к ОстеоФейс ПРО",
                              url=f"{PAY_URL_PRO}?tg_id={tg_id}")],
    ])


def kb_pay_protocol(tg_id: int) -> InlineKeyboardMarkup:
    """Альтернативная кнопка оплаты мини-протокола"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Мини-протокол — 7 000 ₽", url=f"{PAY_URL_PROTOCOL}?tg_id={tg_id}")],
    ])


def kb_razbor_personal_pay(tg_id: int) -> InlineKeyboardMarkup:
    """Кнопка покупки персонального разбора за 3000₽"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Получить персональный разбор — 3 000 ₽",
                              callback_data="buy_razbor_personal")],
    ])


def kb_pay(tg_id: int) -> InlineKeyboardMarkup:
    """Общая кнопка оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оформить участие",
                              callback_data="buy_request:all")],
    ])


def kb_vip_buy(tg_id: int) -> InlineKeyboardMarkup:
    """Кнопка покупки VIP сопровождения"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Хочу VIP-сопровождение",
                              callback_data="buy_vip")],
    ])


def kb_payment_success() -> InlineKeyboardMarkup:
    """После успешной оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Перейти к курсу", url=COURSE_URL)],
        [InlineKeyboardButton(text="💬 Вступить в чат учеников", url=STUDENTS_CHAT_URL)],
    ])


def kb_after_razbor_paid() -> InlineKeyboardMarkup:
    """После оплаты разбора — предлагаем VIP"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Узнать про VIP-сопровождение",
                              callback_data="vip_info")],
        [InlineKeyboardButton(text="📖 Наш канал", url=CHANNEL_URL)],
    ])


# ════════════════════════════════════════════════════════════
#  ВЕБИНАРЫ
# ════════════════════════════════════════════════════════════

def kb_webinar_register() -> InlineKeyboardMarkup:
    """Запись на вебинар — всегда показываем, независимо от даты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Записаться на вебинар", callback_data="webinar:register")],
    ])


def kb_webinar_join() -> InlineKeyboardMarkup:
    """Подключение к вебинару"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Подключиться к вебинару", callback_data="webinar:join")],
    ])


def kb_webinar_link(link: str) -> InlineKeyboardMarkup:
    """Ссылка на вебинарную комнату"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Переход в комнату", url=link)],
    ])


def kb_post_webinar() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Персональный разбор — 3000 ₽", callback_data="razbor_details")],
        [InlineKeyboardButton(text="📝 Записаться на курс", callback_data="course_landing_info")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question")],
    ])


# ════════════════════════════════════════════════════════════
#  КУРСЫ И ОБУЧЕНИЕ
# ════════════════════════════════════════════════════════════

def kb_day0_info(tag: str = "") -> InlineKeyboardMarkup:
    """Информация о курсах день 0"""
    if tag == "обучение":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Подробнее о курсе", url=PAY_URL_PRO)],
            [InlineKeyboardButton(text="📖 Полезное в канале", url=CHANNEL_URL)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Подробнее о курсах", callback_data="courses_info")],
        [InlineKeyboardButton(text="📖 Полезное в канале", url=CHANNEL_URL)],
    ])


def kb_courses_links() -> InlineKeyboardMarkup:
    """Ссылки на курсы"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌸 ОстеоФейс — для себя", callback_data="buy_request:self")],
        [InlineKeyboardButton(text="🎓 ОстеоФейс ПРО — обучение", callback_data="buy_request:pro")],
        [InlineKeyboardButton(text="🏆 VIP-сопровождение 30 дней", callback_data="vip_info")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
    ])


def kb_course_landing() -> InlineKeyboardMarkup:
    """Лендинг курса"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Перейти на сайт", url="https://monecle.com/lg/osteoface/osteoface_1/")],
    ])


def kb_channel() -> InlineKeyboardMarkup:
    """Ссылка на канал"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти в канал ➡️", url=CHANNEL_URL)],
    ])


# ════════════════════════════════════════════════════════════
#  ПРОГРЕВ ПО ДНЯМ
# ════════════════════════════════════════════════════════════

def kb_warmup_day1(tag: str = "") -> InlineKeyboardMarkup:
    if tag == "обучение":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📖 Полезное в канале", url=CHANNEL_URL)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Получить разбор лица", callback_data="razbor")],
        [InlineKeyboardButton(text="📖 Полезное в канале", url=CHANNEL_URL)],
    ])


def kb_warmup_day2(tag: str = "") -> InlineKeyboardMarkup:
    if tag == "обучение":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 Подробнее о курсе", url=PAY_URL_PRO)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Подробнее о курсах", callback_data="courses_info")],
        [InlineKeyboardButton(text="📖 Полезное в канале", url=CHANNEL_URL)],
    ])


def kb_warmup_day3(tag: str = "") -> InlineKeyboardMarkup:
    if tag == "обучение":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question")],
            [InlineKeyboardButton(text="📚 Подробнее о курсе", url=PAY_URL_PRO)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Подробнее о курсах", callback_data="courses_info")],
    ])


def kb_warmup_day4_self(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записаться на курс ОстеоФейс",
                              callback_data="buy_request:self")],
        [InlineKeyboardButton(text="🏆 VIP-сопровождение",
                              callback_data="vip_info")],
    ])


def kb_warmup_day4_pro(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записаться на ОстеоФейс ПРО",
                              callback_data="buy_request:pro")],
        [InlineKeyboardButton(text="🏆 VIP-сопровождение",
                              callback_data="vip_info")],
    ])


def kb_warmup_day5_buy_self(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записаться на курс ОстеоФейс",
                              callback_data="buy_request:self")],
        [InlineKeyboardButton(text="🏆 VIP — 30 дней с мастером",
                              callback_data="vip_info")],
    ])


def kb_warmup_day5_buy_pro(tg_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записаться на ОстеоФейс ПРО",
                              callback_data="buy_request:pro")],
        [InlineKeyboardButton(text="🏆 VIP — 30 дней с мастером",
                              callback_data="vip_info")],
    ])


# ════════════════════════════════════════════════════════════
#  ФОРМЫ И ЗАПРОС КОНТАКТА
# ════════════════════════════════════════════════════════════

def kb_request_phone() -> ReplyKeyboardMarkup:
    """Запрос номера телефона"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def kb_start_razbor_form() -> InlineKeyboardMarkup:
    """Начать заполнение анкеты разбора"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Заполнить анкету", callback_data="start_razbor_form")],
    ])


def kb_start_diag_form() -> InlineKeyboardMarkup:
    """Начать диагностику"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Начать диагностику", callback_data="start_diag_form")],
    ])


def kb_diag_pay() -> InlineKeyboardMarkup:
    """Оплата диагностики"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Записаться на диагностику", url="https://monecle.com/buy/95078")],
    ])


# ════════════════════════════════════════════════════════════
#  АДМИНИСТРАТИВНЫЕ
# ════════════════════════════════════════════════════════════

def kb_admin_menu(is_test: bool = False) -> InlineKeyboardMarkup:
    """Главное меню администратора"""
    mode = "🔴 Режим: ТЕСТ" if is_test else "🟢 Режим: БОЕВОЙ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="🗓 Управление вебинарами", callback_data="admin:webinar_menu")],
        [InlineKeyboardButton(text="📤 Рассылка", callback_data="admin:broadcast_menu")],
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin:users:0")],
        [InlineKeyboardButton(text="✏️ Изменить шаблоны", callback_data="admin:edit_funnel_menu")],
        [InlineKeyboardButton(text="📝 Шаблон разбора лица", callback_data="admin:edit_razbor_template")],
        [InlineKeyboardButton(text=mode, callback_data="admin:toggle_test")],
    ])


def kb_admin_webinar_menu() -> InlineKeyboardMarkup:
    """Меню управления вебинарами"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗓 Назначить вебинар", callback_data="admin:set_webinar")],
        [InlineKeyboardButton(text="ℹ️ Инфо о вебинаре", callback_data="admin:webinar_info")],
        [InlineKeyboardButton(text="❌ Отменить вебинар", callback_data="admin:cancel_webinar")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:panel")],
    ])


def kb_admin_broadcast_menu() -> InlineKeyboardMarkup:
    """Меню рассылок"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Всем", callback_data="broadcast:all")],
        [InlineKeyboardButton(text="💧 Отёки", callback_data="broadcast:отёки")],
        [InlineKeyboardButton(text="⚖️ Асимметрия", callback_data="broadcast:асимметрия")],
        [InlineKeyboardButton(text="📐 Овал", callback_data="broadcast:овал")],
        [InlineKeyboardButton(text="💥 Боль", callback_data="broadcast:боль")],
        [InlineKeyboardButton(text="✨ Подтяжка", callback_data="broadcast:подтяжка")],
        [InlineKeyboardButton(text="💰 Обучение (ПРО)", callback_data="broadcast:обучение")],
        [InlineKeyboardButton(text="🎯 Зарег. на вебинар", callback_data="broadcast:webinar_reg")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:panel")],
    ])


def kb_course_pay_direct(tg_id: int) -> InlineKeyboardMarkup:
    """Прямая кнопка оплаты курса 49 000₽ (из апселла после 7000₽)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Хочу на курс OsteoFace — 49 000 ₽",
                              url=f"{PAY_URL_SELF}?tg_id={tg_id}")],
        [InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question")],
    ])


def kb_admin_question(user_id: int) -> InlineKeyboardMarkup:
    """Ответ на вопрос пользователя"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Перейти в ЛС", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton(text="🤖 Ответить через бота", callback_data=f"admin_reply:{user_id}")],
    ])


def kb_admin_diag_reply(user_id: int) -> InlineKeyboardMarkup:
    """Ответ на диагностику"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 В ЛС", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton(text="🤖 Ответить (с авто-апселлом)", callback_data=f"admin_reply_diag:{user_id}")],
    ])


def kb_cancel_webinar_confirm() -> InlineKeyboardMarkup:
    """Подтверждение отмены вебинара"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Да, отменить", callback_data="cancel_webinar_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_webinar_abort")],
    ])


def kb_cancel_admin() -> InlineKeyboardMarkup:
    """Отмена действия администратора"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")],
    ])


def kb_users_list(users: list, page: int, total: int,
                  per_page: int = 8) -> InlineKeyboardMarkup:
    """Пагинированный список пользователей"""
    rows = []
    for u in users:
        name = u["full_name"] or "Без имени"
        uname = f"@{u['username']}" if u["username"] else str(u["tg_id"])
        tag = u["tag"] or "—"
        paid = "✅" if u["is_paid"] else ""
        label = f"{paid} {name} ({uname}) [{tag}]"
        rows.append([InlineKeyboardButton(
            text=label[:60],
            callback_data=f"user_info:{u['tg_id']}:{page}"
        )])

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Назад",
                                        callback_data=f"admin:users:{page-1}"))
    total_pages = (total + per_page - 1) // per_page
    nav.append(InlineKeyboardButton(
        text=f"📄 {page+1}/{total_pages}", callback_data="noop"
    ))
    if (page + 1) * per_page < total:
        nav.append(InlineKeyboardButton(text="Вперёд ▶️",
                                        callback_data=f"admin:users:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="🔙 В меню", callback_data="admin:panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_user_back(tg_id: int, page: int) -> InlineKeyboardMarkup:
    """Кнопка возврата к списку пользователей"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать", callback_data=f"admin_write:{tg_id}:{page}")],
        [InlineKeyboardButton(text="◀️ К списку", callback_data=f"admin:users:{page}")],
    ])


# ════════════════════════════════════════════════════════════
#  РЕДАКТОР ВОРОНКИ
# ════════════════════════════════════════════════════════════

def kb_funnel_branch_menu() -> InlineKeyboardMarkup:
    """Меню выбора ветки воронки для редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💧 Отёки", callback_data="fedit:отёки")],
        [InlineKeyboardButton(text="✨ Подтяжка", callback_data="fedit:подтяжка")],
        [InlineKeyboardButton(text="💰 Обучение", callback_data="fedit:обучение")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin:panel")],
    ])


def kb_funnel_day_menu(tag: str) -> InlineKeyboardMarkup:
    """Меню выбора дня воронки для редактирования"""
    rows = [
        [InlineKeyboardButton(text=f"📅 День {d}", callback_data=f"fedit_day:{tag}:{d}")]
        for d in range(1, 6)
    ]
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin:edit_funnel_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_funnel_skip_media() -> InlineKeyboardMarkup:
    """Пропустить добавление медиа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Оставить без медиа", callback_data="fedit_skip_media")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")],
    ])


def kb_funnel_skip_button() -> InlineKeyboardMarkup:
    """Пропустить изменение кнопок"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Оставить стандартные кнопки", callback_data="fedit_skip_btn")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")],
    ])