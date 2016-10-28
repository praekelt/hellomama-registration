import pika

from django.db.models import Count
from django.db.models.expressions import RawSQL
from django.conf import settings
from functools import partial

from hellomama_registration import utils

from .models import Registration


class MetricGenerator(object):
    def __init__(self):
        for msg_type in settings.MSG_TYPES:
            setattr(
                self, 'registrations_msg_type_{}_sum'.format(msg_type),
                partial(self.registrations_msg_type_sum, msg_type)
            )
            setattr(
                self, 'registrations_msg_type_{}_total_last'.format(msg_type),
                partial(self.registrations_msg_type_total_last, msg_type)
            )
        for receiver_type in settings.RECEIVER_TYPES:
            setattr(
                self, 'registrations_receiver_type_{}_sum'.format(
                    receiver_type),
                partial(self.registrations_receiver_type_sum, receiver_type)
            )
            setattr(
                self, 'registrations_receiver_type_{}_total_last'.format(
                    receiver_type),
                partial(
                    self.registrations_receiver_type_total_last, receiver_type)
            )
        for language in settings.LANGUAGES:
            setattr(
                self, 'registrations_language_{}_sum'.format(language),
                partial(self.registrations_language_sum, language)
            )

    def generate_metric(self, name, start, end):
        """
        Generates a metric value for the given parameters.

        args:
            name: The name of the metric
            start: Datetime for where the metric window starts
            end: Datetime for where the metric window ends
        """
        metric_func = getattr(self, name.replace('.', '_'))
        return metric_func(start, end)

    def registrations_created_sum(self, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .count()

    def registrations_created_total_last(self, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .count()

    def registrations_unique_operators_sum(self, start, end):
        operators_before = Registration.objects\
            .filter(created_at__lte=start)\
            .annotate(operator=RawSQL("(data->>%s)", ('operator_id',)))\
            .values('operator')

        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .annotate(operator=RawSQL("(data->>%s)", ('operator_id',)))\
            .values('operator')\
            .annotate(count=Count('operator'))\
            .filter(count=1)\
            .exclude(operator__in=operators_before)\
            .count()

    def registrations_msg_type_sum(self, msg_type, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(data__msg_type=msg_type)\
            .count()

    def registrations_msg_type_total_last(self, msg_type, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .filter(data__msg_type=msg_type)\
            .count()

    def registrations_receiver_type_sum(self, receiver_type, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(data__msg_receiver=receiver_type)\
            .count()

    def registrations_receiver_type_total_last(
            self, receiver_type, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .filter(data__msg_receiver=receiver_type)\
            .count()

    def registrations_language_sum(self, language, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(data__language=language)\
            .count()


def send_metric(amqp_url, prefix, name, value, timestamp):
    parameters = pika.URLParameters(amqp_url)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    timestamp = utils.timestamp_to_epoch(timestamp)

    if prefix:
        name = '{}.{}'.format(prefix, name)

    channel.basic_publish(
        'graphite', name, '{} {}'.format(float(value), int(timestamp)),
        pika.BasicProperties(content_type='text/plain', delivery_mode=2))

    connection.close()
