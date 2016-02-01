import uuid

from django.contrib.postgres.fields import JSONField
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


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

    def __unicode__(self):
        return u"%s" % self.name


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

    def __str__(self):  # __unicode__ on Python 2
        return str(self.id)


@receiver(post_save, sender=Registration)
def registration_post_save(sender, instance, created, **kwargs):
    """ Post save hook to fire Registration validation task
    """
    if created:
        from .tasks import validate_registration
        validate_registration.apply_async(
            kwargs={"registration_id": instance.id})
