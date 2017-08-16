from django.utils.encoding import python_2_unicode_compatible
from django.db import models


@python_2_unicode_compatible
class ReportTaskStatus(models.Model):
    """ The status of the report generate tasks
    """

    STATUS_CHOICES = (
        ('Pending', "Pending"),
        ('Running', "Running"),
        ('Sending', "Sending"),
        ('Done', "Done")
    )

    start_date = models.CharField(max_length=30, null=False, blank=False)
    end_date = models.CharField(max_length=30, null=False, blank=False)
    email_subject = models.CharField(max_length=100, null=False, blank=False)
    file_size = models.IntegerField(null=True)
    status = models.CharField(max_length=30, null=False, blank=False,
                              choices=STATUS_CHOICES)
    error = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "%s - %s: %s(%s)" % (
            self.start_date, self.end_date, self.email_subject, self.status)
