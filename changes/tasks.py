import requests

from django.conf import settings

from celery.task import Task

from registrations.models import SubscriptionRequest
from registrations.tasks import (get_messageset_short_name,
                                 get_messageset_schedule_sequence)
from .models import Change


def get_subscription(identity):
    """ Gets the first active subscription found for an identity
    """
    url = settings.IDENTITIES_URL + '/identities/'
    params = {'id': identity, 'active': True}
    headers = {'Authorization': ['Token %s' % settings.IDENTITIES_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.get(url, params=params, headers=headers)
    return r.json()[0]  # return first object


def get_messageset(messageset_id):
    url = settings.STAGE_BASED_URL + 'messageset/%s/' % messageset_id
    headers = {'Authorization': ['Token %s' % settings.STAGE_BASED_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.get(url, headers=headers)
    return r.json()


def get_schedule(schedule_id):
    url = settings.STAGE_BASED_URL + 'schedule/%s/' % str(schedule_id)
    headers = {'Authorization': ['Token %s' % settings.STAGE_BASED_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.get(url, headers=headers)
    return r.json()


def unsubscribe_identity(identity, reason):
    """ Send and unsubscribe request to the identity store
    """
    url = settings.IDENTITIES_URL + 'optout/%s/' % identity
    data = {
        "optout_type": "unsubscribe",
        "identity": identity,
        "reason": reason,
        "address_type": "",
        "address": "",
        "request_source": "change_backend",
        "requestor_source_id": None
    }
    headers = {'Authorization': ['Token %s' % settings.IDENTITIES_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.post(url, data=data, headers=headers)
    return r.json()["id"]


class ImplementAction(Task):
    """ Task to apply a Change action.
    """
    name = "hellomama_registration.changes.tasks.implement_action"

    def change_baby(self, change):
        pass

    def change_loss(self, change):
        pass

    def change_messaging(self, change):
        # Get mother's current subscription
        subscription = get_subscription(change.mother_id)
        # Get current messageset
        messageset = get_messageset(subscription.messageset_id)
        # Get current schedule
        schedule = get_schedule(subscription.schedule)

        # Try to find a manual switch to baby messages
        # manual_baby_switch = Change.objects.filter(mother_id=change.mother_id)
        # if len(manual_baby_switch) > 0:
        #     print("Manually switched to baby", manual_baby_switch)
        #     stage = 'postbirth'
        #     weeks = 'calc from manual_baby_switch.created_at'
        # # Check if
        # elif

        if 'postbirth' in messageset["short_name"]:
            stage = 'postbirth'
        elif 'prebirth' in messageset["short_name"]:
            stage = 'prebirth'
        else:
            stage = 'miscarriage'

        if 'voice_days' in change.data:
            voice_days = change.data["voice_days"]
            voice_times = change.data["voice_times"]
        else:
            voice_days = None
            voice_times = None

        # get schedule days of week: comma-seperated str e.g. '2' for Tue
        days_of_week = schedule["day_of_week"]
        # determine how many times a week messages are sent e.g. 2 for '1,3'
        msgs_per_week = float(len(days_of_week.split(',')))
        # determine approximate current week
        weeks = int(round(
            subscription["next_sequence_number"] / msgs_per_week))

        mother_short_name = get_messageset_short_name(
            stage, 'mother', change.data["msg_type"],
            weeks, voice_days, voice_times)

        mother_msgset_id, mother_msgset_schedule, next_sequence_number =\
            get_messageset_schedule_sequence(
                mother_short_name, weeks, voice_days, voice_times
            )

        # Unsubscribe from current subscriptions
        unsubscribe_identity(change.mother_id, 'change_messaging')

        # Find previous registration object
        # registration = Registration.objects.get(mother_id=change.mother_id)
        # print("Registration data -----------", registration.data)

        # Make new subscription request object
        mother_sub = {
            "contact": change.data["mother_id"],
            "messageset_id": mother_msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": subscription["lang"],
            "schedule": mother_msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        return "Change incomplete"

    def change_language(self, change):
        pass

    def unsubscribe_household_only(self, change):
        pass

    def unsubscribe_mother_only(self, change):
        pass

    def run(self, change_id, **kwargs):
        """ Implements the appropriate action
        """
        change = Change.objects.get(id=change_id)

        if change.action == 'change_baby':
            self.change_baby(change)
        elif change.action == 'change_loss':
            self.change_loss(change)
        elif change.action == 'change_messaging':
            effect = self.change_messaging(change)
            return effect
        elif change.action == 'change_language':
            self.change_language(change)
        elif change.action == 'unsubscribe_household_only':
            self.unsubscribe_household_only(change)
        elif change.action == 'unsubscribe_mother_only':
            self.unsubscribe_mother_only(change)

implement_action = ImplementAction()
