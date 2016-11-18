from os import environ

from django.core.management.base import BaseCommand, CommandError

from registrations.models import Registration
from registrations.tasks import validate_registration

from seed_services_client import StageBasedMessagingApiClient

from ._utils import validate_and_return_url


class Command(BaseCommand):
    help = ("Validates all Registrations without Subscription Requests and "
            "creates one for each. This should also lead to the creation of a "
            "Subscription in the SMB service")

    def add_arguments(self, parser):
        parser.add_argument(
            '--blind', action='store_false', default=True,
            dest='check_subscription',
            help=('Do not check with the stage based messaging API whether'
                  'or not a subscription for the identity already exists.'
                  'NOT RECOMMENDED AT ALL'))
        parser.add_argument(
            '--sbm-url', dest='sbm_url', type=validate_and_return_url,
            default=environ.get('STAGE_BASED_MESSAGING_URL'),
            help=('The Stage Based Messaging Service to verify '
                  'subscriptions for.'))
        parser.add_argument(
            '--sbm-token', dest='sbm_token',
            default=environ.get('STAGE_BASED_MESSAGING_TOKEN'),
            help=('The Authorization token for the SBM Service')
        )

    def handle(self, *args, **kwargs):
        sbm_url = kwargs['sbm_url']
        sbm_token = kwargs['sbm_token']
        check_subscription = kwargs['check_subscription']

        if check_subscription:
            if not sbm_url:
                raise CommandError(
                    'Please make sure either the STAGE_BASED_MESSAGING_URL '
                    'environment variable or --sbm-url is set.')

            if not sbm_token:
                raise CommandError(
                    'Please make sure either the STAGE_BASED_MESSAGING_TOKEN '
                    'environment variable or --sbm-token is set.')
            client = StageBasedMessagingApiClient(sbm_token, sbm_url)

        registrations = Registration.objects.filter(validated=True)

        for reg in registrations:
            requests = reg.get_subscription_requests()
            if requests.exists():
                continue
            if check_subscription and self.count_subscriptions(client, reg):
                self.log(('Registration %s without Subscription Requests '
                          'already has subscription (identity: %s). '
                          'Skipping.')
                         % (reg.pk, reg.mother_id))
                continue

            """
            validate_registration() ensures no invalid registrations get
            subscriptions and creates the Subscription Request
            """
            output = validate_registration.apply_async(
                kwargs={"registration_id": str(reg.id)})
            output = output + " (%s)"
            self.log(output % (reg.mother_id))

    def log(self, log):
        self.stdout.write('%s\n' % (log,))

    def count_subscriptions(self, sbm_client, registration):
        subscriptions = sbm_client.get_subscriptions({
            'identity': registration.mother_id,
        })
        return int(subscriptions['count'])
