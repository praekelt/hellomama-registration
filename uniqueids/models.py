import random

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.encoding import python_2_unicode_compatible

from .tasks import add_unique_id_to_identity


@python_2_unicode_compatible
class Record(models.Model):
    """ The historical record of identities requiring unique integer refs
        write_to is the field we should write back to on the identity details
    """
    id = models.BigIntegerField(primary_key=True)
    identity = models.UUIDField()
    write_to = models.CharField(max_length=36, null=False, blank=False)
    length = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, related_name='records_created',
                                   null=True)
    updated_by = models.ForeignKey(User, related_name='records_updated',
                                   null=True)
    user = property(lambda self: self.created_by)

    def __str__(self):
        return "%s for %s" % (self.id, str(self.identity))


@receiver(pre_save, sender=Record)
def record_pre_save(sender, instance, **kwargs):
    """ Pre save hook to generate a unique ID
    """
    if instance.id is None:
        instance.id = generate_unique_id(length=instance.length)


@receiver(post_save, sender=Record)
def record_post_save(sender, instance, created, **kwargs):
    """ Post save hook to patch the source identity
    """
    if created:
        add_unique_id_to_identity.apply_async(
            kwargs={
                "identity": str(instance.identity),
                "unique_id": instance.id,
                "write_to": instance.write_to
            })


def random_digits(digits):
    lower = 10**(digits-1)
    upper = 10**digits - 1
    return random.randint(lower, upper)


def digits_of(number):
    return [int(digit) for digit in str(number)]


def luhn_checksum(the_number):
    digits = digits_of(the_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for digit in even_digits:
        total += sum(digits_of(2 * digit))
    return total % 10


def calculate_luhn(partial_number):
    check_digit = luhn_checksum(int(partial_number) * 10)
    return check_digit if check_digit == 0 else 10 - check_digit


def generate_unique_id(length=10, attempts=0):
    source = random_digits(int(length)-1)
    checksum = calculate_luhn(source)
    unique_id = int(str(source) + str(checksum))

    try:
        Record.objects.get(id=unique_id)
        if attempts < 10:
            generate_unique_id(length=length, attempts=attempts+1)
        else:
            return "Aborting unique_id generation after 10 failed attempts"
    except Record.DoesNotExist:
        return unique_id
