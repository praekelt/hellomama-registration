import uuid

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.utils.encoding import python_2_unicode_compatible

from registrations.models import Source, get_or_incr_cache


@python_2_unicode_compatible
class Change(models.Model):
    """ A request to change a subscription

    Args:
        mother_id (str): UUID of the mother's identity
        action (str): What type of change to implement
        data (json): Change info in json format
        source (object): Auto-completed field based on the Api key
    """

    ACTION_CHOICES = (
        ('change_messaging', "Change messaging type and/or reception times"),
        ('change_loss', "Change to loss messaging"),
        ('unsubscribe_household_only', "Unsubscribe household msg receiver"),
        ('unsubscribe_mother_only', "Unsubscribe mother from messages"),
        ('change_language', "Change language"),
        ('change_baby', "Change to baby messages")
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mother_id = models.CharField(max_length=36, null=False, blank=False)
    action = models.CharField(max_length=255, null=False, blank=False,
                              choices=ACTION_CHOICES)
    data = JSONField(null=True, blank=True)
    validated = models.BooleanField(default=False)
    source = models.ForeignKey(Source, related_name='changes',
                               null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, related_name='changes_created',
                                   null=True)
    updated_by = models.ForeignKey(User, related_name='changes_updated',
                                   null=True)
    user = property(lambda self: self.created_by)

    def __str__(self):
        return str(self.id)


@receiver(post_save, sender=Change)
def change_post_save(sender, instance, created, **kwargs):
    """ Post save hook to fire Change validation task
    """
    if created:
        from .tasks import implement_action
        implement_action.apply_async(
            kwargs={"change_id": str(instance.id)})
        pass


@receiver(post_save, sender=Change)
def fire_language_change_metric(sender, instance, created, **kwargs):
    from registrations.tasks import fire_metric
    if created and instance.action == 'change_language':
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.change.language.sum',
            "metric_value": 1.0
        })

        total_key = 'registrations.change.language.total.last'
        total = get_or_incr_cache(
            total_key,
            Change.objects.filter(action='change_language').count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Change)
def fire_baby_change_metric(sender, instance, created, **kwargs):
    from registrations.tasks import fire_metric
    if created and instance.action == 'change_baby':
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.change.pregnant_to_baby.sum',
            "metric_value": 1.0
        })

        total_key = 'registrations.change.pregnant_to_baby.total.last'
        total = get_or_incr_cache(
            total_key,
            Change.objects.filter(action='change_baby').count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Change)
def fire_loss_change_metric(sender, instance, created, **kwargs):
    from registrations.tasks import fire_metric
    if created and instance.action == 'change_loss':
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.change.pregnant_to_loss.sum',
            "metric_value": 1.0
        })

        total_key = 'registrations.change.pregnant_to_loss.total.last'
        total = get_or_incr_cache(
            total_key,
            Change.objects.filter(action='change_loss').count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })


@receiver(post_save, sender=Change)
def fire_message_change_metric(sender, instance, created, **kwargs):
    from registrations.tasks import fire_metric
    if created and instance.action == 'change_messaging':
        fire_metric.apply_async(kwargs={
            "metric_name": 'registrations.change.messaging.sum',
            "metric_value": 1.0
        })

        total_key = 'registrations.change.messaging.total.last'
        total = get_or_incr_cache(
            total_key,
            Change.objects.filter(action='change_messaging').count)
        fire_metric.apply_async(kwargs={
            'metric_name': total_key,
            'metric_value': total,
        })
