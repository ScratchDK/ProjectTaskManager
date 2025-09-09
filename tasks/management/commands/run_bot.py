from django.core.management.base import BaseCommand
from tasks.telegram_bot import start_bot, stop_bot
import asyncio


class Command(BaseCommand):
    help = 'Запускает Telegram бота'

    def handle(self, *args, **options):
        self.stdout.write('Запуск Telegram бота...')

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(start_bot())
            self.stdout.write('Бот запущен. Нажмите Ctrl+C для остановки.')
            loop.run_forever()
        except KeyboardInterrupt:
            self.stdout.write('Остановка бота...')
            loop.run_until_complete(stop_bot())
        finally:
            loop.close()
