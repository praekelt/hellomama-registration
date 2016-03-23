import requests
import datetime

from django.conf import settings
from celery.task import Task

from registrations.models import Registration, SubscriptionRequest
from registrations.tasks import (get_messageset_short_name,
                                 get_messageset_schedule_sequence,
                                 calc_baby_age,
                                 calc_pregnancy_week_lmp)
from .models import Change


def get_today():
    return datetime.datetime.today()


def get_subscription(identity):
    """ Gets the first active subscription found for an identity
    """
    url = settings.STAGE_BASED_URL + 'subscriptions/'
    params = {'id': identity, 'active': True}
    headers = {'Authorization': ['Token %s' % settings.STAGE_BASED_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.get(url, params=params, headers=headers)
    return r.json()[0]  # return first object TODO: handle multiple


# def get_identity(identity):
#     url = settings.IDENTITIES_URL + 'identities/%s/' % str(identity)
#     headers = {'Authorization': ['Token %s' % settings.IDENTITIES_TOKEN],
#                'Content-Type': ['application/json']}
#     r = requests.get(url, headers=headers)
#     return r.json()


def deactivate_subscription(subscription):
    """ Sets a subscription deactive via a Patch request
    """
    url = settings.STAGE_BASED_URL + 'subscriptions/%s/' % subscription["id"]
    data = {"active": False}
    headers = {'Authorization': ['Token %s' % settings.STAGE_BASED_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.patch(url, data=data, headers=headers)
    return r.json()


def get_messageset(messageset_id):
    url = settings.STAGE_BASED_URL + 'messageset/%s/' % messageset_id
    headers = {'Authorization': ['Token %s' % settings.STAGE_BASED_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.get(url, headers=headers)
    return r.json()


# def unsubscribe_identity(identity, reason):
#     """ Send and unsubscribe request to the identity store
#     """
#     url = settings.IDENTITIES_URL + 'optout/%s/' % identity
#     data = {
#         "optout_type": "unsubscribe",
#         "identity": identity,
#         "reason": reason,
#         "address_type": "",
#         "address": "",
#         "request_source": "change_backend",
#         "requestor_source_id": None
#     }
#     headers = {'Authorization': ['Token %s' % settings.IDENTITIES_TOKEN],
#                'Content-Type': ['application/json']}
#     r = requests.post(url, data=data, headers=headers)
#     return r.json()["id"]


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
        # Deactivate subscription
        subscription = deactivate_subscription(subscription)
        # Get mother's registration
        registration = Registration.objects.get(mother_id=change.mother_id)

        # Determine stage & week
        # TODO: handle miscarriage stage
        # if the registration was for postbirth, we can assume postbirth
        if registration.stage == 'postbirth':
            stage = 'postbirth'
            weeks = calc_baby_age(get_today(), registration.data["baby_dob"])
        # otherwise, we need to look if the user has changed to baby
        else:
            baby_switch = Change.objects.filter(mother_id=change.mother_id,
                                                action='change_baby')
            if baby_switch.count() > 0:
                # TODO: handle a person that has switched to baby for a
                # previous pregnancy
                stage = 'postbirth'
                weeks = calc_baby_age(
                    get_today(), baby_switch.created_at[0:10].replace('-', ''))
            else:
                stage = 'prebirth'
                weeks = calc_pregnancy_week_lmp(
                    get_today(), registration.data["last_period_date"])

        # Determine voice_days & voice_times
        if 'voice_days' in change.data:
            voice_days = change.data["voice_days"]
            voice_times = change.data["voice_times"]
        else:
            voice_days = None
            voice_times = None

        mother_short_name = get_messageset_short_name(
            stage, 'mother', change.data["msg_type"],
            weeks, voice_days, voice_times)

        mother_msgset_id, mother_msgset_schedule, next_sequence_number =\
            get_messageset_schedule_sequence(
                mother_short_name, weeks, voice_days, voice_times
            )

        # Make new subscription request object
        mother_sub = {
            "contact": change.mother_id,
            "messageset_id": mother_msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": subscription["lang"],
            "schedule": mother_msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        return "Change messaging completed"

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
