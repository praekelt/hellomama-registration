from django.utils.encoding import python_2_unicode_compatible
from django.db import models


@python_2_unicode_compatible
class VoiceCall(models.Model):
    created_at = models.DateTimeField(db_index=True)
    shortcode = models.CharField(null=False, blank=False, max_length=36)
    msisdn = models.CharField(null=False, blank=False, max_length=36,
                              db_index=True)
    duration = models.IntegerField(null=False, blank=False)
    reason = models.CharField(null=False, blank=False, max_length=36)

    def __str__(self):
        return "%s - %s" % (self.created_at, self.msisdn)
