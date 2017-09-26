from django.core.management.base import BaseCommand, CommandError

from hellomama_registration import utils
from registrations.models import Registration


class Command(BaseCommand):
    help = ("Transfer all registrations linked to one facility to another "
            "facility.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-code", dest="from_code", type=str,
            help=("The facility code where the registrations should be moved "
                  "from.")
        )
        parser.add_argument(
            "--to-code", dest="to_code", type=str,
            help=("The facility code where the registrations should be moved "
                  "to.")
        )

    def handle(self, *args, **kwargs):
        from_code = kwargs['from_code']
        to_code = kwargs['to_code']

        if not from_code or not to_code:
            raise CommandError('From and To code is required.')

        for identity in utils.search_identities("details__personnel_code",
                                                from_code):
            from_identity = identity['id']
            break

        for identity in utils.search_identities("details__personnel_code",
                                                to_code):
            to_identity = identity['id']
            break

        registrations = Registration.objects.filter(
            data__operator_id=from_identity).iterator()

        updated = 0
        for registration in registrations:
            registration.data.update({"operator_id": to_identity})
            registration.save()
            updated += 1

        self.success('Updated %s registrations.' % updated)

    def log(self, level, msg):
        self.stdout.write(level(msg))

    def warning(self, msg):
        self.log(self.style.WARNING, msg)

    def success(self, msg):
        self.log(self.style.SUCCESS, msg)
