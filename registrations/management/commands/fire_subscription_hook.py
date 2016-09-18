from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from rest_hooks.signals import raw_hook_event
from registrations.models import SubscriptionRequest

from rest_hooks.models import Hook


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

    def handle(self, *args, **kwargs):
        event_str, hooks = kwargs['event']
        subscription_requests = kwargs['uuids']
        user = kwargs['user']

        if not hooks.exists():
            raise CommandError(
                'Cannot find any hooks for event %s.' % (event_str,))
        if user:
            hooks = hooks.filter(user=user)

        for req in subscription_requests:
            for hook in hooks:
                raw_hook_event.send(
                    sender=req,
                    event_name=hook.event,
                    payload=req.serialize_hook(hook)['data'],
                    instance=req,
                    user=hook.user)
