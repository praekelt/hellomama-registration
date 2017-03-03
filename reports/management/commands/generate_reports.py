import pytz
import calendar

from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator, EmailValidator
from django.utils import timezone

from reports.tasks import generate_report


def mk_validator(django_validator):
    def validator(inputstr):
        django_validator()(inputstr)
        return inputstr
    return validator


def midnight(timestamp):
    return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)


def one_month_after(timestamp):
    weekday, number_of_days = calendar.monthrange(
        timestamp.year, timestamp.month)
    return timestamp + timedelta(days=number_of_days)


def midnight_validator(inputstr):
    return midnight(datetime.strptime(inputstr, '%Y-%m-%d')).replace(
        tzinfo=pytz.timezone(settings.TIME_ZONE))


class Command(BaseCommand):

    help = ('Call task to generate XLS spreadsheet report on registrations '
            'and write it to disk')

    def add_arguments(self, parser):
        parser.add_argument(
            '--start',
            type=midnight_validator, default=midnight(timezone.now()),
            help=('The start of the reporting range (YYYY-MM-DD). '
                  'Defaults to today according to the configured timezone.'))
        parser.add_argument(
            '--end',
            type=midnight_validator,
            default=None,
            help=('The end of the reporting range (YYYY-MM-DD). '
                  'Defaults to exactly 1 month after `--start`'))
        parser.add_argument(
            '--output-file', type=str, default=None,
            help='The file to write the report to.'
        )
        parser.add_argument(
            '--email-to', type=mk_validator(EmailValidator),
            default=[], action='append',
            help='Who to email the report to.'
        )
        parser.add_argument(
            '--email-from', type=mk_validator(EmailValidator),
            default=settings.DEFAULT_FROM_EMAIL,
            help='Which address to send the email from',
        )
        parser.add_argument(
            '--email-subject', type=str,
            default='Seed Control Interface Generated Report',
            help='The subject of the email',
        )
        parser.add_argument(
            '--identity-store-url', type=mk_validator(URLValidator),
            default=settings.IDENTITY_STORE_URL)
        parser.add_argument(
            '--identity-store-token', type=str,
            default=settings.IDENTITY_STORE_TOKEN)
        parser.add_argument(
            '--sbm-url', type=mk_validator(URLValidator))
        parser.add_argument(
            '--sbm-token', type=str)
        parser.add_argument(
            '--ms-url', type=mk_validator(URLValidator))
        parser.add_argument(
            '--ms-token', type=str)

    def handle(self, *args, **kwargs):
        sbm_token = kwargs['sbm_token']
        sbm_url = kwargs['sbm_url']
        ms_token = kwargs['ms_token']
        ms_url = kwargs['ms_url']
        start_date = kwargs['start']
        end_date = kwargs['end']
        output_file = kwargs['output_file']

        if not sbm_url:
            raise CommandError(
                'Please make sure the --sbm-url is set.')

        if not sbm_token:
            raise CommandError(
                'Please make sure the --sbm-token is set.')

        if not ms_url:
            raise CommandError(
                'Please make sure the --ms-url is set.')

        if not ms_token:
            raise CommandError(
                'Please make sure the --ms-token is set.')

        if not output_file:
            raise CommandError(
                'Please specify --output-file.')

        if end_date is None:
            end_date = one_month_after(start_date)

        generate_report.apply_async(kwargs={
            'output_file': output_file,
            'id_store_token': kwargs['identity_store_token'],
            'id_store_url': kwargs['identity_store_url'],
            'sbm_token': sbm_token,
            'sbm_url': sbm_url,
            'ms_token': ms_token,
            'ms_url': ms_url,
            'start_date': kwargs['start'],
            'end_date': end_date,
            'email_recipients': kwargs['email_to'],
            'email_sender': kwargs['email_from'],
            'email_subject': kwargs['email_subject']
        })
