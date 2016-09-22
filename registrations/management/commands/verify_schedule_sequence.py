from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from registrations.models import Registration


class Command(BaseCommand):
    help = ("Verify that a UUID for a registration has the correct"
            "sequence number set for stage of the registration")

    def add_arguments(self, parser):
        parser.add_argument(
            "registration_uuid",
            type=lambda uuid: Registration.objects.get(pk=uuid),
            help="The UUID of the registration to verify")
        parser.add_argument(
            "--fix", action="store_true", default=False,
            help=("Attempt to automatically fix the registrations "
                  "sequence numbers if they turn out to be wrong"))

    def handle(self, *args, **kwargs):
        print kwargs
