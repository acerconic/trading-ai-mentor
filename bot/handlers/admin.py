import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import Database
from config import ADMIN_ID

admin_router = Router()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def _admin_check(user_id: int) -> bool:
    return user_id == ADMIN_ID


def _build_admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Все пользователи", callback_data="adm_users")
    builder.button(text="📊 Статистика", callback_data="adm_stats")
    builder.button(text="🔄 Обновить", callback_data="adm_refresh")
    builder.adjust(2, 1)
    return builder.as_markup()


def _build_user_actions_kb(target_id: int, is_approved: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_approved:
        builder.button(text="🚫 Заблокировать", callback_data=f"adm_block_{target_id}")
    else:
        builder.button(text="✅ Одобрить", callback_data=f"approve_{target_id}")
    builder.button(text="🗑 Удалить из БД", callback_data=f"adm_delete_{target_id}")
    builder.button(text="◀️ Назад к списку", callback_data="adm_users")
    builder.adjust(1)
    return builder.as_markup()


async def _format_stats_message() -> str:
    users = await Database.get_all_users()
    total = len(users)
    approved = sum(1 for u in users if u.get("is_approved"))
    pending = total - approved
    total_books = sum(u.get("studied_books", 0) for u in users)
    total_hw = sum(u.get("hw_attempts", 0) for u in users)
    total_fails = sum(u.get("hw_fails", 0) for u in users)
    pass_rate = round(((total_hw - total_fails) / total_hw * 100), 1) if total_hw > 0 else 0

    top = sorted(
        [u for u in users if u.get("is_approved")],
        key=lambda x: x.get("studied_books", 0),
        reverse=True
    )[:5]

    msg = (
        "👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 <b>Общая статистика:</b>\n"
        f"  👥 Всего пользователей: <b>{total}</b>\n"
        f"  ✅ Одобрено: <b>{approved}</b>\n"
        f"  ⏳ Ожидают одобрения: <b>{pending}</b>\n\n"
        "📚 <b>Активность:</b>\n"
        f"  📖 Книг изучено (всего): <b>{total_books}</b>\n"
        f"  🎯 Практик сдано: <b>{total_hw}</b>\n"
        f"  ✅ Процент сдачи: <b>{pass_rate}%</b>\n\n"
        "🔓 <i>Лимиты страниц/МБ отключены для всех одобренных учеников.</i>\n"
    )

    if top:
        msg += "\n🏆 <b>Топ-5 учеников:</b>\n"
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, u in enumerate(top):
            name = u.get('username') or 'Без имени'
            msg += f"  {medals[i]} @{name} — <b>{u.get('studied_books', 0)}</b> книг | <b>{u.get('hw_attempts', 0)}</b> практик\n"

    return msg


# ─────────────────────────────────────────────
#  /admin COMMAND  +  🔧 Admin Panel BUTTON
# ─────────────────────────────────────────────

@admin_router.message(F.text.in_({"/admin", "🔧 Admin Panel"}))
async def show_admin_panel(message: Message):
    if not _admin_check(message.from_user.id):
        return

    msg = await _format_stats_message()
    await message.answer(msg, reply_markup=_build_admin_panel_kb(), parse_mode="HTML")


# ─────────────────────────────────────────────
#  REFRESH BUTTON
# ─────────────────────────────────────────────

@admin_router.callback_query(F.data == "adm_refresh")
async def adm_refresh(callback: CallbackQuery):
    if not _admin_check(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    msg = await _format_stats_message()
    try:
        await callback.message.edit_text(msg, reply_markup=_build_admin_panel_kb(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("✅ Обновлено!")


# ─────────────────────────────────────────────
#  STATS SUMMARY
# ─────────────────────────────────────────────

@admin_router.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery):
    if not _admin_check(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    msg = await _format_stats_message()
    try:
        await callback.message.edit_text(msg, reply_markup=_build_admin_panel_kb(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


# ─────────────────────────────────────────────
#  ALL USERS LIST
# ─────────────────────────────────────────────

@admin_router.callback_query(F.data == "adm_users")
async def adm_users(callback: CallbackQuery):
    if not _admin_check(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    users = await Database.get_all_users()
    if not users:
        await callback.answer("Пользователей нет.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for u in users:
        status = "✅" if u.get("is_approved") else "⏳"
        name = u.get("username") or f"id:{u['telegram_id']}"
        builder.button(
            text=f"{status} @{name}",
            callback_data=f"adm_user_{u['telegram_id']}"
        )
    builder.button(text="◀️ Назад", callback_data="adm_stats")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            f"👥 <b>Все пользователи ({len(users)}):</b>\n\nНажмите на ученика для управления:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


# ─────────────────────────────────────────────
#  SINGLE USER DETAIL
# ─────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_user_"))
async def adm_user_detail(callback: CallbackQuery):
    if not _admin_check(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    target_id = int(callback.data.split("_")[2])
    user = await Database.get_user(target_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    status = "✅ Одобрен" if user.get("is_approved") else "⏳ Ожидает"
    name = user.get("username") or "—"
    books = user.get("studied_books", 0)
    hw = user.get("hw_attempts", 0)
    fails = user.get("hw_fails", 0)
    lang = user.get("language") or "не выбран"
    win = round(((hw - fails) / hw * 100), 1) if hw > 0 else 0

    detail_msg = (
        f"👤 <b>Информация об ученике:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"👤 Username: @{name}\n"
        f"🌐 Язык: <b>{lang.upper()}</b>\n"
        f"📌 Статус: <b>{status}</b>\n\n"
        f"📚 Книг изучено: <b>{books}</b>\n"
        f"🎯 Практик сдано: <b>{hw}</b>\n"
        f"❌ Не сдал: <b>{fails}</b>\n"
        f"📈 Успешность: <b>{win}%</b>"
    )

    try:
        await callback.message.edit_text(
            detail_msg,
            reply_markup=_build_user_actions_kb(target_id, bool(user.get("is_approved"))),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


# ─────────────────────────────────────────────
#  BLOCK USER
# ─────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_block_"))
async def adm_block_user(callback: CallbackQuery, bot: Bot):
    if not _admin_check(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    target_id = int(callback.data.split("_")[2])
    await Database.update_approval(target_id, is_approved=False)

    try:
        await bot.send_message(target_id, "🚫 Ваш доступ был отозван администратором.")
    except Exception:
        pass

    await callback.answer("🚫 Пользователь заблокирован.", show_alert=True)
    # Refresh user detail
    user = await Database.get_user(target_id)
    if user:
        name = user.get("username") or "—"
        await callback.message.edit_text(
            f"🚫 Пользователь @{name} (ID: <code>{target_id}</code>) заблокирован.",
            reply_markup=_build_user_actions_kb(target_id, False),
            parse_mode="HTML"
        )


# ─────────────────────────────────────────────
#  DELETE USER
# ─────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("adm_delete_"))
async def adm_delete_user(callback: CallbackQuery):
    if not _admin_check(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    target_id = int(callback.data.split("_")[2])
    await Database.delete_user(target_id)
    await callback.answer("🗑 Пользователь удалён из базы данных.", show_alert=True)

    # Go back to user list
    users = await Database.get_all_users()
    builder = InlineKeyboardBuilder()
    for u in users:
        status = "✅" if u.get("is_approved") else "⏳"
        name = u.get("username") or f"id:{u['telegram_id']}"
        builder.button(
            text=f"{status} @{name}",
            callback_data=f"adm_user_{u['telegram_id']}"
        )
    builder.button(text="◀️ Назад", callback_data="adm_stats")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            f"👥 <b>Все пользователи ({len(users)}):</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        pass


# ─────────────────────────────────────────────
#  APPROVE / REJECT (from new user notification)
# ─────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
async def process_admin_decision(callback: CallbackQuery, bot: Bot):
    if not _admin_check(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа.", show_alert=True)

    parts = callback.data.split("_")
    action = parts[0]
    user_id = int(parts[1])

    if action == "approve":
        await Database.update_approval(user_id, is_approved=True)
        new_text = f"{callback.message.html_text}\n\n✅ <b>Одобрено</b>"
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML")
        except Exception:
            pass
        try:
            await bot.send_message(user_id, "🎉 Доступ открыт! Нажмите /start чтобы продолжить.")
        except Exception as e:
            logger.error(f"Cannot notify user {user_id}: {e}")
        await callback.answer("✅ Пользователь одобрен!")

    elif action == "reject":
        new_text = f"{callback.message.html_text}\n\n❌ <b>Отклонено</b>"
        try:
            await callback.message.edit_text(new_text, parse_mode="HTML")
        except Exception:
            pass
        try:
            await bot.send_message(user_id, "❌ Ваша заявка была отклонена администратором.")
        except Exception as e:
            logger.error(f"Cannot notify user {user_id}: {e}")
        await callback.answer("❌ Пользователь отклонён.")
