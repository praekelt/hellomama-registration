from os import environ

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from rest_hooks.signals import raw_hook_event
from registrations.models import SubscriptionRequest

from rest_hooks.models import Hook

from seed_services_client import StageBasedMessagingApiClient

from ._utils import validate_and_return_url


def find_events(event_str):
    return (event_str, Hook.objects.filter(event=event_str))


def find_subscription_requests(uuid):
    return SubscriptionRequest.objects.get(pk=uuid)


def find_user(username):
    return User.objects.get(username=username)


class Command(BaseCommand):
    help = ("Manually fires a Subscription Request webhook to the SBM "
            "service to create a Subscription")

    def add_arguments(self, parser):
        parser.add_argument('event', type=find_events,
                            help='The event to fire the hooks for.')
        parser.add_argument('uuids', nargs='+',
                            type=find_subscription_requests,
                            help='The UUIDs of the SubscriptionRequests')
        parser.add_argument('--username', dest='user',
                            action='store', default=None,
                            type=find_user,
                            help='Filter on a specific username if required')
        parser.add_argument(
            '--blind', action='store_false', default=True,
            dest='check_subscription',
            help=('Do not check with the stage based messaging API whether'
                  'or not a subscription for the subscription request already'
                  'exists. NOT RECOMMENDED AT ALL'))
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
        event_str, hooks = kwargs['event']
        subscription_requests = kwargs['uuids']
        user = kwargs['user']
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

        if not hooks.exists():
            raise CommandError(
                'Cannot find any hooks for event %s.' % (event_str,))
        if user:
            hooks = hooks.filter(user=user)

        for req in subscription_requests:
            if check_subscription and self.count_subscriptions(client, req):
                self.log(('Subscriptions already exist for %s (identity: %s).'
                          ' Skipping.') % (req, req.identity))
                continue

            for hook in hooks:
                raw_hook_event.send(
                    sender=req,
                    event_name=hook.event,
                    payload=req.serialize_hook(hook)['data'],
                    instance=req,
                    user=hook.user)
                self.log('Firing hook %s for %s.' % (hook, req,))

    def log(self, log):
        self.stdout.write('%s\n' % (log,))

    def count_subscriptions(self, sbm_client, subscription_request):
        subscriptions = sbm_client.get_subscriptions({
            'identity': subscription_request.identity,
        })
        return int(subscriptions['count'])
