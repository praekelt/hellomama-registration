from os import environ

from django.core.management.base import BaseCommand, CommandError

from registrations.models import SubscriptionRequest

from seed_services_client import StageBasedMessagingApiClient

from ._utils import validate_and_return_url


class Command(BaseCommand):
    help = ("This command will loop all subscription requests and find the "
            "corresponding subscription in SBM and update the "
            "initial_sequence_number field, we need this to fast forward the "
            "subscription.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--sbm-url', dest='sbm_url', type=validate_and_return_url,
            default=environ.get('STAGE_BASED_MESSAGING_URL'),
            help=('The Stage Based Messaging Service to verify '
                  'subscriptions for.'))
        parser.add_argument(
            '--sbm-token', dest='sbm_token', type=str,
            default=environ.get('STAGE_BASED_MESSAGING_TOKEN'),
            help=('The Authorization token for the SBM Service'))

    def handle(self, *args, **kwargs):
        sbm_url = kwargs['sbm_url']
        sbm_token = kwargs['sbm_token']

        if not sbm_url:
            raise CommandError(
                'Please make sure either the STAGE_BASED_MESSAGING_URL '
                'environment variable or --sbm-url is set.')

        if not sbm_token:
            raise CommandError(
                'Please make sure either the STAGE_BASED_MESSAGING_TOKEN '
                'environment variable or --sbm-token is set.')

        sbm_client = StageBasedMessagingApiClient(sbm_token, sbm_url)

        sub_requests = SubscriptionRequest.objects.all().iterator()

        updated = 0
        for sub_request in sub_requests:
            subscriptions = sbm_client.get_subscriptions({
                'identity': sub_request.identity,
                'created_at__gt': sub_request.created_at,
                'messageset': sub_request.messageset,
            })

            first = None
            first_date = None
            for sub in subscriptions['results']:
                created_at = sub['created_at']

                if not first_date or created_at < first_date:
                    first_date = created_at
                    first = sub

            if first:
                data = {
                    'initial_sequence_number': sub_request.next_sequence_number
                }
                sbm_client.update_subscription(first['id'], data)

                updated += 1
            else:
                self.warning("Subscription not found: %s" %
                             (sub_request.identity,))

        self.success('Updated %d subscriptions.' % (updated,))

    def log(self, level, msg):
        self.stdout.write(level(msg))

    def warning(self, msg):
        self.log(self.style.WARNING, msg)

    def success(self, msg):
        self.log(self.style.SUCCESS, msg)
