from os import environ
from datetime import datetime

from uuid import UUID
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from seed_services_client import StageBasedMessagingApiClient

from registrations.models import Registration
from hellomama_registration import utils


def validate_and_return_url(url):
    URLValidator()(url)
    return url


class Command(BaseCommand):
    help = ("Verify that a UUID for a registration has the correct"
            "sequence number set for stage of the registration")

    def add_arguments(self, parser):
        parser.add_argument(
            "registration",
            type=lambda uuid: Registration.objects.get(pk=uuid),
            help="The UUID of the registration to verify")
        parser.add_argument(
            "message_set",
            type=str, choices=("mother", "household"),
            help="The message set to verify")
        parser.add_argument(
            "--fix", action="store_true", default=False,
            help=("Attempt to automatically fix the registrations "
                  "sequence numbers if they turn out to be wrong"))
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
            '--sbm-token', dest='sbm_token', type=UUID,
            default=environ.get('STAGE_BASED_MESSAGING_TOKEN'),
            help=('The Authorization token for the SBM Service')
        )

    def handle(self, *args, **kwargs):
        sbm_url = kwargs['sbm_url']
        sbm_token = kwargs['sbm_token'].hex
        registration = kwargs['registration']
        message_set = kwargs['message_set']
        apply_fix = kwargs['fix']
        today = kwargs['today']

        if not sbm_url:
            raise CommandError(
                'Please make sure either the STAGE_BASED_MESSAGING_URL '
                'environment variable or --sbm-url is set.')

        if not sbm_token:
            raise CommandError(
                'Please make sure either the STAGE_BASED_MESSAGING_TOKEN '
                'environment variable or --sbm-token is set.')

        client = StageBasedMessagingApiClient(sbm_token, sbm_url)

        for receiver_id in registration.get_receiver_ids():
            self.verify_subscription_request(
                client, registration, receiver_id, message_set, today,
                apply_fix)

    def verify_subscription_request(
            self, sbm_client, registration, receiver_id, message_set,
            today, apply_fix=False):
        """
        Verify a subscription request for a receiver.

        This checks if a subscription exists at the SBM Service. If it does
        it will fail early because this tool does not yet fix remote
        subscriptions, it only deals with SubscriptionRequests that have not
        turned into a Subscription.

        :param sbm_client StageBasedMessagingApiClient:
            The client to the stage based messaging service API.
        :param registration Registration:
            The registration we're verifying
        :param receiver_id str:
            The UUID of the receiver we're wanting to verify the registration
            for
        :param message_set str:
            The message set we're verifying
        :param today datetime:
            The date we're using to calculate the sequence numbers
        :param apply_fix bool:
            Whether or not to apply the fix or just log it.
        """

        subscriptions = sbm_client.get_subscriptions({
            'identity': receiver_id,
        })

        if subscriptions['count']:
            raise CommandError(
                'Subscriptions exist for %s.' % (registration,))

        weeks_estimate = registration.estimate_current_preg_weeks(today=today)
        voice_days, voice_times = registration.get_voice_days_and_times()
        mother_short_name = utils.get_messageset_short_name(
            registration.stage, message_set, registration.data["msg_type"],
            weeks_estimate, voice_days, voice_times
        )

        message_set_info = utils.get_messageset_schedule_sequence(
            mother_short_name, weeks_estimate)
        messageset_id, schedule_id, next_sequence_number = message_set_info

        sub_requests = registration.get_subscription_requests().filter(
            messageset=messageset_id)
        if not sub_requests.exists():
            raise CommandError(
                'No SubscriptionRequests exist for %s with messageset %s.' % (
                    registration, message_set))

        for request in sub_requests:
            if (request.next_sequence_number != next_sequence_number):
                self.log(
                    '%s next_sequence_number is %s, should be %s' % (
                        request.id.hex,
                        request.next_sequence_number, next_sequence_number))
                if apply_fix:

                    update = {
                        'next_sequence_number': next_sequence_number,
                        'messageset': messageset_id,
                        'schedule': schedule_id,
                    }

                    if sub_requests.filter(pk=request.pk).update(**update):
                        self.log(
                            'Updated %s, set %s' % (
                                request.id.hex,
                                ', '.join(['%s: %s' % kv
                                           for kv in sorted(update.items())]),
                            ))

    def log(self, log):
        self.stdout.write('%s\n' % (log,))
