from django.core.management.base import BaseCommand, CommandError

from hellomama_registration import utils
from registrations.models import Registration


class Command(BaseCommand):
    help = ("Transfer all registrations linked to incorrect operators to the "
            "correct operators.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", dest="source", type=int,
            help=("The source id where incorrect registrations are linked to.")
        )

    def handle(self, *args, **kwargs):
        source = kwargs['source']

        if not source:
            raise CommandError('Source is required.')

        registrations = Registration.objects.filter(
            source_id=source).iterator()

        updated = 0
        for registration in registrations:
            operator = utils.get_identity(
                registration.data['operator_id'])

            print operator
            if 'personnel_code' not in operator['details']:

                try:
                    identities = utils.search_identities(
                        "details__personnel_code",
                        operator['details']['default_address'])
                    identity = next(identities)
                    print identity
                    new_operator_id = identity['id']

                    registration.data.update({"operator_id": new_operator_id})
                    registration.save()
                    updated += 1
                except StopIteration:
                    self.warning('New operator not found: %s' % (
                        registration.data['operator_id']))

        self.success('Updated %s registrations.' % updated)

    def log(self, level, msg):
        self.stdout.write(level(msg))

    def warning(self, msg):
        self.log(self.style.WARNING, msg)

    def success(self, msg):
        self.log(self.style.SUCCESS, msg)
