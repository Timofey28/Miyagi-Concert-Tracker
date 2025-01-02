import logging
import traceback
import pytz
import requests
from typing import Optional
from datetime import time

from telegram import (
    Update,
    BotCommandScopeAllPrivateChats,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackContext,
    Defaults,
)
from telegram.error import Forbidden
from bs4 import BeautifulSoup

from data import TOKEN, DATA_FILE, MY_ID
from schemas import UserInfo


def get_miyagi_concerts() -> Optional[str]:
    url = 'https://miyagi-concert.ru/'
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f'Error while getting data from site, status code: {response.status_code}')
        return None
    soup = BeautifulSoup(response.text, 'lxml')
    concerts_info = soup.find('div', id='concerts').text
    if concerts_info.endswith(' — следите за анонсами'):
        concerts_info = concerts_info[:-22]
    return f'Расписание концертов Мияги 2025/2026:\n\n{concerts_info}'


async def mail_updated_info(context: CallbackContext):
    cheliki = read_data_file()
    concert_update_msg = get_miyagi_concerts()
    if concert_update_msg is None:
        return
    for chel_id, chel_info in cheliki.items():
        if chel_info.mailing_is_activated:
            if chel_info.last_message_id is not None:
                try:
                    await context.bot.delete_message(chel_id, chel_info.last_message_id)
                except:
                    pass
            try:
                sent_message = await context.bot.send_message(chel_id, concert_update_msg)
                cheliki[chel_id].last_message_id = sent_message.message_id
            except Forbidden:
                del cheliki[chel_id]
                logging.info(f'User {chel_id} has blocked the bot. Removed from mailing list.')
            except Exception as e:
                logging.error(f'Error while sending message to {chel_id}: {e}')
            else:
                logging.info(f'Message sent to {chel_id}')
    write_data_file(cheliki)


async def command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == MY_ID and not context.job_queue.jobs():
        await context.bot.set_my_commands(commands=bot_commands, scope=BotCommandScopeAllPrivateChats())
        context.job_queue.run_daily(mail_updated_info, time(10, 0, 0, 0))

    cheliki = read_data_file()
    cheliki[chat_id] = UserInfo(mailing_is_activated=True, last_message_id=None)
    write_data_file(cheliki)
    msg = 'Подключена ежедневная рассылка с обновлением информации о планируемых концертах Miyagi!\n\n' \
          'Чтобы отписаться, вызови команду /stop.'
    await context.bot.send_message(chat_id, msg)


async def command_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cheliki = read_data_file()
    cheliki[chat_id].mailing_is_activated = False
    write_data_file(cheliki)
    await context.bot.send_message(chat_id, 'Рассылка остановлена! Для возобновления вызови команду /start.')


async def command_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == MY_ID:
        cheliki = read_data_file()
        mailing_list = 'Список подписчиков на рассылку:\n\n'
        for chel_id, user_info in cheliki.items():
            mailing_list += f'{chel_id}: {user_info}\n'
        await context.bot.send_message(chat_id, mailing_list)


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f'{traceback.format_exc()}')


def read_data_file() -> dict[int, UserInfo]:
    with open(DATA_FILE) as file:
        people = list(filter(lambda x: x != '\n', file.readlines()))
    cheliki = {}
    for chel in people:
        chel_info = chel.split()
        chel_id = int(chel_info[0])
        mailing_is_activated = bool(int(chel_info[1]))
        last_message_id = int(chel_info[2]) if int(chel_info[2]) != -1 else None
        cheliki[chel_id] = UserInfo(mailing_is_activated=mailing_is_activated, last_message_id=last_message_id)
    return cheliki


def write_data_file(data: dict[int, UserInfo]) -> None:
    with open(DATA_FILE, 'w') as file:
        for chel_id, user_info in data.items():
            file.write(f'{chel_id} {str(user_info)}\n')


def run_bot():
    print('Starting bot...')
    defaults = Defaults(tzinfo=pytz.timezone('Europe/Moscow'))
    app = Application.builder().token(TOKEN).defaults(defaults).build()

    # Commands
    global bot_commands
    app.add_handler(CommandHandler('start', command_start))
    app.add_handler(CommandHandler('stop', command_stop))
    app.add_handler(CommandHandler('show', command_show))
    bot_commands = [
        ('start', 'Подписаться на рассылку обновлений о концертах Miyagi'),
        ('stop', 'Отписаться от рассылки обновлений о концертах Miyagi')
    ]

    # Errors
    app.add_error_handler(handle_error)

    # Pools the bot
    print('Polling...')
    app.run_polling(poll_interval=1)


if __name__ == '__main__':
    # Настройка логов
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        filename='info.log',
        filemode='w',
        level=logging.INFO
    )
    logger = logging.getLogger('httpx')
    logger.setLevel(logging.WARNING)

    open(DATA_FILE, 'a').close()
    bot_commands = None

    run_bot()