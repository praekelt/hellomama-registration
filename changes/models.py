import uuid

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.utils.encoding import python_2_unicode_compatible

from registrations.models import Source


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
            "metric_name": 'change.language.sum',
            "metric_value": 1.0
        })
