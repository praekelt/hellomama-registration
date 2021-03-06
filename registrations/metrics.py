import pika
from django.db.models import Count
from django.db.models.expressions import RawSQL
from django.conf import settings
from functools import partial

from hellomama_registration import utils

from .models import Registration, Source, registrations_for_identity_field
from changes.models import Change


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
            setattr(
                self, 'optout_msg_type_{}_sum'.format(msg_type),
                partial(self.optout_msg_type_sum, msg_type)
            )
            setattr(
                self, 'optout_msg_type_{}_total_last'.format(msg_type),
                partial(self.optout_msg_type_total_last, msg_type)
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
            setattr(
                self, 'optout_receiver_type_{}_sum'.format(
                    receiver_type),
                partial(
                    self.optout_receiver_type_sum, receiver_type)
            )
            setattr(
                self, 'optout_receiver_type_{}_total_last'.format(
                    receiver_type),
                partial(
                    self.optout_receiver_type_total_last, receiver_type)
            )
        for language in settings.LANGUAGES:
            setattr(
                self, 'registrations_language_{}_sum'.format(language),
                partial(self.registrations_language_sum, language)
            )
            setattr(
                self, 'registrations_language_{}_total_last'.format(language),
                partial(self.registrations_language_total_last, language)
            )
        for state in settings.STATES:
            setattr(
                self, 'registrations_state_{}_sum'.format(state),
                partial(self.registrations_state_sum, state)
            )
            setattr(
                self, 'registrations_state_{}_total_last'.format(state),
                partial(self.registrations_state_total_last, state)
            )
        for role in settings.ROLES:
            setattr(
                self, 'registrations_role_{}_sum'.format(role),
                partial(self.registrations_role_sum, role)
            )
            setattr(
                self, 'registrations_role_{}_total_last'.format(role),
                partial(self.registrations_role_total_last, role)
            )
        for reason in settings.OPTOUT_REASONS:
            setattr(
                self, 'optout_reason_{}_sum'.format(reason),
                partial(self.optout_reason_sum, reason)
            )
            setattr(
                self, 'optout_reason_{}_total_last'.format(reason),
                partial(self.optout_reason_total_last, reason)
            )
        for source in settings.OPTOUT_SOURCES:
            setattr(
                self, 'optout_source_{}_sum'.format(source),
                partial(self.optout_source_sum, source)
            )
            setattr(
                self, 'optout_source_{}_total_last'.format(source),
                partial(self.optout_source_total_last, source)
            )
        sources = Source.objects.all()
        sources.prefetch_related('user')
        for source in Source.objects.all():
            username = source.user.username
            setattr(
                self, 'registrations_source_{}_sum'.format(username),
                partial(self.registrations_source_sum, username)
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

    def registrations_language_total_last(self, language, start, end):
        return Registration.objects\
            .filter(created_at__lte=end)\
            .filter(data__language=language)\
            .count()

    def registrations_state_sum(self, state, start, end):
        return registrations_for_identity_field("details__state", state)\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .count()

    def registrations_state_total_last(self, state, start, end):
        return registrations_for_identity_field("details__state", state)\
            .filter(created_at__lte=end)\
            .count()

    def registrations_role_sum(self, role, start, end):
        return registrations_for_identity_field("details__role", role)\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .count()

    def registrations_role_total_last(self, role, start, end):
        return registrations_for_identity_field("details__role", role)\
            .filter(created_at__lte=end)\
            .count()

    def registrations_source_sum(self, user, start, end):
        return Registration.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(source__user__username=user)\
            .count()

    def registrations_change_language_sum(self, start, end):
        return Change.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(action='change_language')\
            .count()

    def registrations_change_language_total_last(self, start, end):
        return Change.objects\
            .filter(created_at__lte=end)\
            .filter(action='change_language')\
            .count()

    def registrations_change_pregnant_to_baby_sum(self, start, end):
        return Change.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(action='change_baby')\
            .count()

    def registrations_change_pregnant_to_baby_total_last(self, start, end):
        return Change.objects\
            .filter(created_at__lte=end)\
            .filter(action='change_baby')\
            .count()

    def registrations_change_pregnant_to_loss_sum(self, start, end):
        return Change.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(action='change_loss')\
            .count()

    def registrations_change_pregnant_to_loss_total_last(self, start, end):
        return Change.objects\
            .filter(created_at__lte=end)\
            .filter(action='change_loss')\
            .count()

    def registrations_change_messaging_sum(self, start, end):
        return Change.objects\
            .filter(created_at__gt=start)\
            .filter(created_at__lte=end)\
            .filter(action='change_messaging')\
            .count()

    def registrations_change_messaging_total_last(self, start, end):
        return Change.objects\
            .filter(created_at__lte=end)\
            .filter(action='change_messaging')\
            .count()

    def optout_msg_type_sum(self, msg_type, start, end):
        result = utils.search_optouts({
            "created_at__gt": start,
            "created_at__lte": end,
        })

        identities = set(data['identity'] for data in result)

        return Registration.objects.filter(
                    mother_id__in=identities,
                    data__msg_type=msg_type).count()

    def optout_msg_type_total_last(self, msg_type, start, end):
        result = utils.search_optouts({
            "created_at__lte": end,
        })

        identities = set(data['identity'] for data in result)

        return Registration.objects.filter(
                    mother_id__in=identities,
                    data__msg_type=msg_type).count()

    def optout_receiver_type_sum(self, receiver_type, start, end):
        result = utils.search_optouts({
            "created_at__gt": start,
            "created_at__lte": end,
        })

        identities = set(data['identity'] for data in result)

        return Registration.objects.filter(
                    mother_id__in=identities,
                    data__msg_receiver=receiver_type).count()

    def optout_receiver_type_total_last(self, receiver_type, start, end):
        result = utils.search_optouts({
            "created_at__lte": end,
        })

        identities = set(data['identity'] for data in result)

        return Registration.objects.filter(
                    mother_id__in=identities,
                    data__msg_receiver=receiver_type).count()

    def optout_reason_sum(self, reason, start, end):
        result = utils.search_optouts({
            "reason": reason,
            "created_at__gt": start,
            "created_at__lte": end,
        })
        return sum(1 for r in result)

    def optout_reason_total_last(self, reason, start, end):
        result = utils.search_optouts({
            "reason": reason,
            "created_at__lte": end,
        })
        return sum(1 for r in result)

    def optout_source_sum(self, source, start, end):
        result = utils.search_optouts({
            "request_source": source,
            "created_at__gt": start,
            "created_at__lte": end,
        })
        return sum(1 for r in result)

    def optout_source_total_last(self, source, start, end):
        result = utils.search_optouts({
            "request_source": source,
            "created_at__lte": end,
        })
        return sum(1 for r in result)


def send_metric(amqp_channel, prefix, name, value, timestamp):
    timestamp = utils.timestamp_to_epoch(timestamp)

    if prefix:
        name = '{}.{}'.format(prefix, name)

    amqp_channel.basic_publish(
        'graphite', name, '{} {}'.format(float(value), int(timestamp)),
        pika.BasicProperties(content_type='text/plain', delivery_mode=2))
