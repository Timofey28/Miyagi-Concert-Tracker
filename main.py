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
from schemas import User


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
    chat = update.effective_chat
    if chat.id == MY_ID and not context.job_queue.jobs():
        await context.bot.set_my_commands(commands=bot_commands, scope=BotCommandScopeAllPrivateChats())
        context.job_queue.run_daily(mail_updated_info, time(9, 0, 0, 0))
        # context.job_queue.run_repeating(mail_updated_info, interval=3)

    cheliki = read_data_file()
    cheliki[chat.id] = User(
        id=chat.id,
        mailing_is_activated=True,
        last_message_id=None,
        username=chat.username,
        first_name=chat.first_name,
        last_name=chat.last_name
    )
    write_data_file(cheliki)
    msg = 'Подключена ежедневная рассылка с обновлением информации о планируемых концертах Miyagi!\n\n' \
          'Чтобы отписаться, вызови команду /stop.'
    await context.bot.send_message(chat.id, msg)


async def command_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cheliki = read_data_file()
    cheliki[chat_id].mailing_is_activated = False
    write_data_file(cheliki)
    await context.bot.send_message(chat_id, 'Рассылка остановлена! Для возобновления вызови команду /start.')


async def command_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id == MY_ID:
        cheliki = list(read_data_file().values())
        mailing_list = 'Список подписчиков на рассылку:\n\n'
        counter = 1
        for chel in cheliki:
            mailing_list += f'{counter}) {str(chel)}\n'
            counter += 1
        await context.bot.send_message(chat_id, mailing_list, parse_mode='markdown')


async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f'{traceback.format_exc()}')


def read_data_file() -> dict[int, User]:
    with open(DATA_FILE, encoding='utf-8') as file:
        people = list(map(lambda user: eval(user), file.readlines()))
    cheliki = {}
    for chel in people:
        cheliki[chel.id] = chel
    return cheliki


def write_data_file(data: dict[int, User]) -> None:
    users = list(data.values())
    users.sort(key=lambda user: user.mailing_is_activated, reverse=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        for user in users:
            file.write(repr(user) + '\n')


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

    # Polls the bot
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
