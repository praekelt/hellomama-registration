from os import environ
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models.signals import post_save
from rest_hooks.models import Hook, model_saved
from rest_hooks.signals import raw_hook_event

from seed_services_client import StageBasedMessagingApiClient

from hellomama_registration import utils
from registrations.models import Registration, SubscriptionRequest
from registrations.tasks import validate_registration


from ._utils import validate_and_return_url


class Command(BaseCommand):
    help = ("Creates or updates all Subscription Requests and Subscriptions "
            "for a registration. Note: Identities with multiple subscriptions "
            "to the same message set will only have one subscription changed.")

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
            "--today", dest="today", default=datetime.datetime.now(),
            type=lambda today: datetime.datetime.strptime(today, '%Y%m%d'),
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

        for receiver_id in receivers:
            if receiver_id == registration.mother_id:
                message_set = "mother"
            else:
                message_set = "household"
            relevant_requests = self.verify_subscription_requests(
                sub_requests, registration, receiver_id, message_set, today,
                apply_fix)
            for request in relevant_requests:
                self.verify_subscription(client, request, subscriptions,
                                         apply_fix)

    def verify_subscription_requests(
            self, requests, registration, receiver_id, message_set,
            today, apply_fix=False):
        """
        Verify a subscription request for a receiver.

        :param requests QuerySet:
            The subscription requests to be verified.
        :param registration Registration:
            The registration we're fixing
        :param receiver_id str:
            The UUID of the receiver we're wanting to fix the registration for
        :param message_set str:
            The message set we're verifying
        :param today datetime:
            The date we're using to calculate the sequence numbers
        :param apply_fix bool:
            Whether or not to apply the fix or just log it.
        """

        weeks_estimate = registration.estimate_current_preg_weeks(today=today)

        # Get the info for the message set this identity should be on
        if message_set == "mother":
            voice_days, voice_times = registration.get_voice_days_and_times()
            messageset_short_name = utils.get_messageset_short_name(
                registration.stage, message_set, registration.data["msg_type"],
                weeks_estimate, voice_days, voice_times
            )
        else:
            messageset_short_name = utils.get_messageset_short_name(
                registration.stage, 'household', registration.data["msg_type"],
                weeks_estimate, "fri", "9_11"
            )

        message_set_info = utils.get_messageset_schedule_sequence(
            messageset_short_name, weeks_estimate)
        messageset_id, schedule_id, next_sequence_number = message_set_info

        # Get the subscrition requests for this user on this messageset
        sub_requests = requests.filter(identity=receiver_id,
                                       messageset=messageset_id)

        if not sub_requests.exists():
            self.log('%s has no subscription requests for %s' % (
                     receiver_id, messageset_short_name))
            if apply_fix:
                self.create_subscription_request(
                    registration, receiver_id, messageset_id, schedule_id,
                    next_sequence_number)

        data = {
            'next_sequence_number': next_sequence_number,
            'messageset': messageset_id,
            'schedule': schedule_id,
        }

        # Find differences between expected and actual subscription requests
        for request in sub_requests:
            expected, actual, is_different = self.sub_request_difference(
                request, data)
            expected_str = ', '.join(['%s: %s' % kv for kv in expected])
            actual_str = ', '.join(['%s: %s' % kv for kv in actual])
            if is_different:
                self.log(
                    '%s has "%s", should be "%s"' % (
                        request.id, actual_str, expected_str))
                if apply_fix:
                    if sub_requests.filter(pk=request.pk).update(**data):
                        self.log(
                            'Updated %s, set "%s"' % (
                                request.id,
                                expected_str,
                            ))
            else:
                self.log('%s has correct subscription request %s' % (
                         registration.id, request.id))
        # Return the updated subscription requests
        return registration.get_subscription_requests().filter(
            identity=receiver_id, messageset=messageset_id)

    def create_subscription_request(self, registration, receiver_id, msgset_id,
                                    msgset_schedule, next_sequence_number):
        """
        Disconnects hook listeners and creates a subscription request with a
        welcome message. Reconnects hook listeners afterwards.

        :param registration Registration:
            The registration we're fixing
        :param receiver_id str:
            The UUID of the receiver we're wanting to fix the registration for
        :param msgset_id int:
            The id of the message set we're creating a subscription request for
        :param msgset_schedule int:
            The id of the schedule for the message set
        :param next_sequence_number int:
            The sequence number of the next message that should be sent
        """
        self.log('Attempting to create subscription request')
        # We don't want this to automatically create a subscription
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')

        sub = {
            "identity": receiver_id,
            "messageset": msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": registration.data["language"],
            "schedule": msgset_schedule,
            "metadata": {}
        }

        # Add mother welcome message. This is the same as is done in the task
        if receiver_id == registration.mother_id:
            if 'voice_days' in registration.data and \
                    registration.data["voice_days"] != "":
                sub["metadata"]["prepend_next_delivery"] = \
                    "%s/static/audio/registration/%s/welcome_mother.mp3" % (
                    settings.PUBLIC_HOST,
                    registration.data["language"])
            else:
                if registration.data["msg_receiver"] in [
                        "father_only", "friend_only", "family_only"]:
                    to_addr = utils.get_identity_address(
                        registration.data["receiver_id"])
                else:
                    to_addr = utils.get_identity_address(
                        registration.mother_id)
                payload = {
                    "to_addr": to_addr,
                    "content": settings.MOTHER_WELCOME_TEXT_NG_ENG,
                    "metadata": {}
                }
                utils.post_message(payload)

        request = SubscriptionRequest.objects.create(**sub)
        post_save.connect(receiver=model_saved,
                          dispatch_uid='instance-saved-hook')
        return request

    def sub_request_difference(self, request, expected):
        expected_copy = [(key, expected[key])
                         for key in sorted(expected.keys())]
        actual = [(key, getattr(request, key))
                  for key in sorted(expected.keys())]
        return (expected_copy, actual, expected_copy != actual)

    def verify_subscription(self, client, sub_request, subscriptions,
                            apply_fix=False):
        """
        Verify a list of subscriptions based on a given subscription request.

        :param sbm_client StageBasedMessagingApiClient:
            The client to the stage based messaging service API
        :param sub_request SubscriptionRequest:
            The subscription request to use for the verification
        :param subscriptions list:
            The subscriptions to verify
        :param apply_fix bool:
            Whether or not to apply the fix or just log it.
        """
        msgset_subscription = {}
        if subscriptions:
            for sub in subscriptions.get(sub_request.identity, {}):
                if sub_request.messageset == sub["messageset"]:
                    msgset_subscription = sub
                    # Prefer active subscriptions
                    if sub["active"]:
                        break
        if not msgset_subscription:
            self.log('No subscription found for subscription request %s' %
                     (sub_request.id))
            if apply_fix:
                self.fire_subscription_hooks(sub_request)
            return

        # Don't do anything if there aren't active subscriptions
        if not msgset_subscription["active"]:
            self.log('No active subscription found for subscription request '
                     '%s. Taking no action' % (sub_request.id))
            return

        # Don't do anything if the subscription is up to date
        if sub_request.next_sequence_number == \
                msgset_subscription["next_sequence_number"]:
            self.log('Next sequence numbers match. Taking no action')
            return

        self.log('Subscription %s has next_sequence_number=%s, should be %s' %
                 (msgset_subscription['id'],
                  msgset_subscription["next_sequence_number"],
                  sub_request.next_sequence_number))
        if apply_fix:
            client.update_subscription(
                msgset_subscription['id'],
                {'next_sequence_number': sub_request.next_sequence_number})
            self.log('Updated subscription %s. Set next_sequence_number to %s'
                     % (msgset_subscription['id'],
                        sub_request.next_sequence_number))

    def fire_subscription_hooks(self, request):
        """
        Triggers the hooks for when a subscription request is added.
        This shoud lead to a subscription being created in the normal way.
        """
        hooks = Hook.objects.filter(event="subscriptionrequest.added")
        if not hooks.exists():
            self.log('Cannot find any hooks for creating a new subscription '
                     'request')

        for hook in hooks:
            raw_hook_event.send(
                sender=request,
                event_name=hook.event,
                payload=request.serialize_hook(hook)['data'],
                instance=request,
                user=hook.user)
            self.log('Firing hook %s for %s.' % (hook, request,))

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

        weeks = registration.estimate_current_preg_weeks(today=today)
        if weeks > settings.PREBIRTH_MAX_WEEKS + settings.POSTBIRTH_MAX_WEEKS:
            raise CommandError(
                'This pregnancy is %s weeks old and should no longer be on '
                'any of our message sets' % (weeks))

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
