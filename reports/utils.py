import pytz
import calendar
import random
import string

from datetime import datetime, timedelta
from django.conf import settings


def midnight(timestamp):
    return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)


def one_month_after(timestamp):
    weekday, number_of_days = calendar.monthrange(
        timestamp.year, timestamp.month)
    return timestamp + timedelta(days=number_of_days)


def midnight_validator(inputstr):
    return midnight(datetime.strptime(inputstr, '%Y-%m-%d')).replace(
        tzinfo=pytz.timezone(settings.TIME_ZONE))


def generate_random_filename(suffix='.xlsx'):
    return ''.join(
        random.choice(string.ascii_lowercase) for i in range(12)) + suffix
