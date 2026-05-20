"""定时提醒插件：业务在 services.reminder_service，存储在 repositories。"""

from nonebot import get_driver, on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.params import CommandArg

from services.reminder_service import (
    bootstrap_reminders,
    handle_reminder_command,
    session_target,
)

reminder = on_command("提醒", priority=12, block=True)


@reminder.handle()
async def _handle_reminder(
    _bot: Bot,
    event: MessageEvent,
    args: Message = CommandArg(),
) -> None:
    raw = args.extract_plain_text().strip()
    target_kind, target_id = session_target(event)
    msg = await handle_reminder_command(
        raw=raw,
        bot_self_id=str(event.self_id),
        creator_id=str(event.get_user_id()),
        target_kind=target_kind,
        target_id=target_id,
        bot=_bot,
        event=event,
    )
    await reminder.finish(msg)


driver = get_driver()


@driver.on_startup
async def _startup() -> None:
    await bootstrap_reminders()
