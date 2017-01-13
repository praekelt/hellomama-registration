from os import environ
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from seed_services_client import StageBasedMessagingApiClient

from registrations.models import Registration
from registrations.tasks import validate_registration


from ._utils import validate_and_return_url


class Command(BaseCommand):
    help = ("Creates or updates all Subscription Requests and Subscriptions "
            "for a registration")

    def add_arguments(self, parser):
        parser.add_argument(
            "registration",
            type=lambda uuid: Registration.objects.get(pk=uuid),
            help="The UUID of the registration to use")
        parser.add_argument(
            "--fix", action="store_true", default=False,
            help=("Attempt to automatically fix the subscriptions and "
                  "requests if they turn out to be wrong"))
        parser.add_argument(
            "--today", dest="today", default=datetime.now(),
            type=lambda today: datetime.strptime(today, '%Y%m%d'),
            help=("Set the date for 'today' from which to calculate the "
                  "next_sequence_number value. By default it will use "
                  "datetime.now() (format YYYYMMDD)")
        )
        parser.add_argument(
            '--sbm-url', dest='sbm_url', type=validate_and_return_url,
            default=environ.get('STAGE_BASED_MESSAGING_URL'),
            help=('The Stage Based Messaging Service to verify '
                  'subscriptions for.'))
        parser.add_argument(
            '--sbm-token', dest='sbm_token', type=str,
            default=environ.get('STAGE_BASED_MESSAGING_TOKEN'),
            help=('The Authorization token for the SBM Service')
        )

    def handle(self, *args, **kwargs):
        sbm_url = kwargs['sbm_url']
        sbm_token = kwargs['sbm_token']
        registration = kwargs['registration']
        apply_fix = kwargs['fix']
        today = kwargs['today']

        self.validate_input(registration, sbm_url, sbm_token, today)

        client = StageBasedMessagingApiClient(sbm_token, sbm_url)

        # Get subscription requests for identities
        sub_requests = registration.get_subscription_requests()
        receivers = registration.get_receiver_ids()
        subscriptions = {}

        # Get subscriptions for identities
        for receiver_id in receivers:
            sub_response = client.get_subscriptions({
                'identity': receiver_id,
            })
            if sub_response['count']:
                subscriptions[receiver_id] = sub_response['results']

        """
        If there are no requests or subscriptions then take them through the
        normal process to create these.
        """
        if not sub_requests.exists() and not subscriptions:
            self.log("Registration %s has no subscriptions or subscription "
                     "requests" % (registration.id))
            if apply_fix:
                self.log("Attempting to create them")
                validate_registration(registration_id=registration.id)
            return

    def validate_input(self, registration, sbm_url, sbm_token, today):
        if not registration.validated:
            raise CommandError(
                'This registration is not valid. This command only works with '
                'validated registrations')

        # TODO: Handle fixing of post-birth message sets
        if registration.stage != 'prebirth':
            raise CommandError(
                'This command has not been confirmed to work with any stage '
                'other than prebirth, this registration is: %s' % (
                    registration.stage))

        # TODO: Handle conversion to post-birth message sets
        weeks = registration.estimate_current_preg_weeks(today=today)
        if weeks > settings.PREBIRTH_MAX_WEEKS:
            raise CommandError(
                'This pregnancy is %s weeks old and should no longer be on '
                'the prebirth message sets' % (weeks))

        if not sbm_url:
            raise CommandError(
                'Please make sure either the STAGE_BASED_MESSAGING_URL '
                'environment variable or --sbm-url is set')

        if not sbm_token:
            raise CommandError(
                'Please make sure either the STAGE_BASED_MESSAGING_TOKEN '
                'environment variable or --sbm-token is set')

    def log(self, log):
        self.stdout.write('%s\n' % (log,))
