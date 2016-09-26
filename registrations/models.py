import uuid
from datetime import datetime

from django.contrib.postgres.fields import JSONField
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Source(models.Model):
    """ The source from which a registation originates.
        The User foreignkey is used to identify the source based on the
        user's api token.
    """
    AUTHORITY_CHOICES = (
        ('patient', "Patient"),
        ('advisor', "Trusted Advisor"),
        ('hw_limited', "Health Worker Limited"),
        ('hw_full', "Health Worker Full")
    )
    name = models.CharField(max_length=100, null=False, blank=False)
    user = models.ForeignKey(User, related_name='sources', null=False)
    authority = models.CharField(max_length=30, null=False, blank=False,
                                 choices=AUTHORITY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "%s" % self.name


class RegistrationException(Exception):
    pass


@python_2_unicode_compatible
class Registration(models.Model):
    """ A registation submitted via Vumi or other sources.

    After a registation has been created, a task will fire that
    validates if the data provided is sufficient for the stage
    of pregnancy.

    Args:
        stage (str): The stage of pregnancy of the mother
        data (json): Registration info in json format
        validated (bool): True if the registation has been
            validated after creation
        source (object): Auto-completed field based on the Api key
    """

    STAGE_CHOICES = (
        ('prebirth', "Mother is pregnant"),
        ('postbirth', "Baby has been born"),
        ('loss', "Baby loss")
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.CharField(max_length=30, null=False, blank=False,
                             choices=STAGE_CHOICES)
    mother_id = models.CharField(max_length=36, null=False, blank=False)
    data = JSONField(null=True, blank=True)
    validated = models.BooleanField(default=False)
    source = models.ForeignKey(Source, related_name='registrations',
                               null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, related_name='registrations_created',
                                   null=True)
    updated_by = models.ForeignKey(User, related_name='registrations_updated',
                                   null=True)
    user = property(lambda self: self.created_by)

    def __str__(self):
        return str(self.id)

    def get_voice_days_and_times(self):
        return self.data.get('voice_days'), self.data.get('voice_times')

    def get_weeks_pregnant_or_age(self):
        week = self.data.get("preg_week") or self.data.get("baby_age")
        if week is not None:
            return week
        raise RegistrationException(
            'Neither preg_week or baby_age are specified for %s.' % (self,))

    def get_receiver_ids(self):
        """
        A registration can result in multiple people being registered.
        The mother, a household (or related family members) can be registered
        for messaging.

        :returns: set of uuid strings
        """
        return set(
            filter(None, [self.mother_id, self.data.get('receiver_id')]))

    def get_subscription_requests(self):
        """
        Returns all possible subscriptions created for this registration,
        these may be for the mother or for related family members (stored
        in the receiver_id)

        :returns: Django Queryset
        """
        return SubscriptionRequest.objects.filter(
            identity__in=self.get_receiver_ids())

    def estimate_current_preg_weeks(self, today=None):
        # NOTE: circular import :/
        from hellomama_registration import utils
        today = today or datetime.now()
        return utils.calc_pregnancy_week_lmp(
            today, self.data['last_period_date'])


@receiver(post_save, sender=Registration)
def registration_post_save(sender, instance, created, **kwargs):
    """ Post save hook to fire Registration validation task
    """
    if created:
        from .tasks import validate_registration
        validate_registration.apply_async(
            kwargs={"registration_id": str(instance.id)})


@receiver(post_save, sender=Registration)
def fire_created_metric(sender, instance, created, **kwargs):
    from .tasks import fire_metric
    if created:
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.created.sum',
            "metric_value": 1.0
        })

        total_key = 'registrations.created.last'
        total = get_or_incr_cache(
            total_key,
            Registration.objects.count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Registration)
def fire_source_metric(sender, instance, created, **kwargs):
    from .tasks import fire_metric
    if created:
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.source.%s.sum' % (
                instance.source.user.username),
            "metric_value": 1.0
        })


@receiver(post_save, sender=Registration)
def fire_unique_operator_metric(sender, instance, created, **kwargs):
    # if registration is made by a new unique user (operator), fire a metric
    from .tasks import fire_metric
    if (created and instance.data and instance.data['operator_id'] and
        Registration.objects.filter(
            data__operator_id=instance.data['operator_id']).count() == 1):
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.unique_operators.sum',
            "metric_value": 1.0
        })


def get_or_incr_cache(key, func):
    """
    Used to either get a value from the cache, or if the value doesn't exist
    in the cache, run the function to get a value to use to populate the cache
    """
    value = cache.get(key)
    if value is None:
        value = func()
        cache.set(key, value)
    else:
        cache.incr(key)
        value += 1
    return value


@receiver(post_save, sender=Registration)
def fire_message_type_metric(sender, instance, created, **kwargs):
    """
    Fires a metric for each message type of each registration.

    Fires both a `sum` metric with 1.0 for each registration, as well as a
    `last` metric with the total amount of registrations for that type.
    """
    from .tasks import fire_metric, is_valid_msg_type
    if (created and instance.data and instance.data.get('msg_type') and
            is_valid_msg_type(instance.data['msg_type'])):
        msg_type = instance.data['msg_type']
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.msg_type.%s.sum' % msg_type,
            "metric_value": 1.0,
        })

        total_key = 'registrations.msg_type.%s.last' % msg_type
        total = get_or_incr_cache(
            total_key,
            Registration.objects.filter(data__msg_type=msg_type).count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Registration)
def fire_receiver_type_metric(sender, instance, created, **kwargs):
    """Fires a metric for each receiver message type of each subscription."""
    from .tasks import fire_metric, is_valid_msg_receiver
    if (created and instance.data and instance.data['msg_receiver'] and
            is_valid_msg_receiver(instance.data['msg_receiver'])):
        msg_receiver = instance.data['msg_receiver']
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.receiver_type.%s.sum' % msg_receiver,
            "metric_value": 1.0,
        })

        total_key = 'registrations.receiver_type.%s.last' % msg_receiver
        total = get_or_incr_cache(
            total_key,
            Registration.objects.filter(data__msg_receiver=msg_receiver).count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Registration)
def fire_language_metric(sender, instance, created, **kwargs):
    """
    Fires metrics for each language for each subscription, a sum metric for
    the registrations over time, and a last metric for the total count.
    """
    from .tasks import fire_metric, is_valid_lang
    if (created and instance.data and instance.data.get('language') and
            is_valid_lang(instance.data['language'])):
        lang = instance.data['language']
        fire_metric.apply_async(kwargs={
            'metric_name': "registrations.language.%s.sum" % lang,
            'metric_value': 1.0,
        })

        total_key = "registrations.language.%s.last" % lang
        total = get_or_incr_cache(
            total_key,
            Registration.objects.filter(data__language=lang).count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


def registrations_for_identity_field(params):
    from hellomama_registration.utils import search_identities
    identities = search_identities(params=params)
    ids = ()
    for data in identities:
        ids = ids + (data["id"],)

    return Registration.objects.filter(
        data__operator_id__in=ids)


@receiver(post_save, sender=Registration)
def fire_state_metric(sender, instance, created, **kwargs):
    """
    Fires metrics for each state for each subscription, a sum metric for
    the registrations over time, and a last metric for the total count.
    """
    from .tasks import fire_metric, is_valid_state
    from hellomama_registration.utils import get_identity, normalise_string
    if (created and instance.data and instance.data['operator_id']):
        identity = get_identity(instance.data['operator_id'])
        if (identity.get('details') and identity['details'].get('state') and
                is_valid_state(normalise_string(
                    identity['details']['state']))):
            state = identity['details']['state']
            normalised_state = normalise_string(state)
            fire_metric.apply_async(kwargs={
                'metric_name': "registrations.state.%s.sum" % normalised_state,
                'metric_value': 1.0,
            })

            total_key = "registrations.state.%s.last" % normalised_state

            total = get_or_incr_cache(
                total_key,
                registrations_for_identity_field(
                    {"details__state": state}).count)
            fire_metric.apply_async(kwargs={
                'metric_name': total_key,
                'metric_value': total,
            })


# @receiver(post_save, sender=Registration)
def fire_role_metric(sender, instance, created, **kwargs):
    """
    Fires metrics for each role for each subscription, a sum metric for
    the registrations over time, and a last metric for the total count.
    """
    from .tasks import fire_metric, is_valid_role
    from hellomama_registration.utils import get_identity, normalise_string
    if (created and instance.data and instance.data['operator_id']):
        identity = get_identity(instance.data['operator_id'])
        if (identity.get('details') and identity['details'].get('role') and
                is_valid_role(normalise_string(
                    identity['details']['role']))):
            role = identity['details']['role']
            normalised_role = normalise_string(role)
            fire_metric.apply_async(kwargs={
                'metric_name': "registrations.role.%s.sum" % normalised_role,
                'metric_value': 1.0,
            })

            total_key = "registrations.role.%s.last" % normalised_role

            total = get_or_incr_cache(
                total_key,
                registrations_for_identity_field(
                    {"details__role": role}).count)
            fire_metric.apply_async(kwargs={
                'metric_name': total_key,
                'metric_value': total,
            })


@python_2_unicode_compatible
class SubscriptionRequest(models.Model):
    """ A data model that maps to the Stagebased Store
    Subscription model. Created after a successful Registration
    validation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.CharField(max_length=36, null=False, blank=False)
    messageset = models.IntegerField(null=False, blank=False)
    next_sequence_number = models.IntegerField(default=1, null=False,
                                               blank=False)
    lang = models.CharField(max_length=6, null=False, blank=False)
    schedule = models.IntegerField(default=1)
    metadata = JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def serialize_hook(self, hook):
        # optional, there are serialization defaults
        # we recommend always sending the Hook
        # metadata along for the ride as well
        return {
            'hook': hook.dict(),
            'data': {
                'id': str(self.id),
                'identity': self.identity,
                'messageset': self.messageset,
                'next_sequence_number': self.next_sequence_number,
                'lang': self.lang,
                'schedule': self.schedule,
                'metadata': self.metadata,
                'created_at': self.created_at.isoformat(),
                'updated_at': self.updated_at.isoformat()
            }
        }

    def __str__(self):
        return str(self.id)
