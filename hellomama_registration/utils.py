import datetime
import requests
import json

from django.conf import settings


def get_today():
    return datetime.datetime.today()


def calc_pregnancy_week_lmp(today, lmp):
    """ Calculate how far along the mother's prenancy is in weeks.
    """
    last_period_date = datetime.datetime.strptime(lmp, "%Y%m%d")
    time_diff = today - last_period_date
    preg_weeks = int(time_diff.days / 7)
    # You can't be one week pregnant (smaller numbers will be rejected)
    if preg_weeks == 1:
        preg_weeks = 2
    return preg_weeks


def calc_baby_age(today, baby_dob):
    """ Calculate the baby's age in weeks.
    """
    baby_dob_date = datetime.datetime.strptime(baby_dob, "%Y%m%d")
    time_diff = today - baby_dob_date
    if time_diff.days >= 0:
        age_weeks = int(time_diff.days / 7)
        return age_weeks
    else:
        # Return -1 if the date is in the future
        return -1


def get_identity(identity):
    url = "%s/%s/%s/" % (settings.IDENTITY_STORE_URL, "identities", identity)
    headers = {'Authorization': ['Token %s' % settings.IDENTITY_STORE_TOKEN],
               'Content-Type': ['application/json']}
    r = requests.get(url, headers=headers)
    return r.json()


def get_identity_address(identity):
    url = "%s/%s/%s/addresses/msisdn" % (settings.IDENTITY_STORE_URL,
                                         "identities", identity)
    params = {"default": True}
    headers = {'Authorization': ['Token %s' % (
        settings.IDENTITY_STORE_TOKEN, )],
        'Content-Type': ['application/json']}
    r = requests.get(url, params=params, headers=headers).json()
    if len(r["results"]) > 0:
        return r["results"][0]
    else:
        return None


def get_messageset(short_name):
    url = "%s/%s/" % (settings.STAGE_BASED_MESSAGING_URL, "messageset")
    params = {'short_name': short_name}
    headers = {'Authorization': [
        'Token %s' % settings.STAGE_BASED_MESSAGING_TOKEN],
        'Content-Type': ['application/json']
    }
    r = requests.get(url, params=params, headers=headers)
    return r.json()["results"][0]  # messagesets should be unique, return 1st


def get_schedule(schedule_id):
    url = "%s/%s/%s/" % (settings.STAGE_BASED_MESSAGING_URL,
                         "schedule", schedule_id)
    headers = {'Authorization': [
        'Token %s' % settings.STAGE_BASED_MESSAGING_TOKEN],
        'Content-Type': ['application/json']
    }
    r = requests.get(url, headers=headers)
    return r.json()


def get_subscriptions(identity):
    """ Gets the first active subscription found for an identity
    """
    url = "%s/%s/" % (settings.STAGE_BASED_MESSAGING_URL, "subscriptions")
    params = {'id': identity, 'active': True}
    headers = {'Authorization': [
        'Token %s' % settings.STAGE_BASED_MESSAGING_TOKEN],
        'Content-Type': ['application/json']
    }
    r = requests.get(url, params=params, headers=headers)
    return r.json()["results"]


def patch_subscription(subscription, data):
    """ Patches the given subscription with the data provided
    """
    url = "%s/%s/%s/" % (settings.STAGE_BASED_MESSAGING_URL,
                         "subscriptions", subscription["id"])
    data = data
    headers = {'Authorization': [
        'Token %s' % settings.STAGE_BASED_MESSAGING_TOKEN],
        'Content-Type': ['application/json']
    }
    r = requests.patch(url, data=data, headers=headers)
    return r.json()


def deactivate_subscription(subscription):
    """ Sets a subscription deactive via a Patch request
    """
    return patch_subscription(subscription, {"active": False})


def get_messageset_short_name(stage, recipient, msg_type, weeks, voice_days,
                              voice_times):

    if recipient == "household":
        msg_type = "text"

    if stage == "prebirth":
        week_range = "10_42"
    elif stage == "miscarriage":
        week_range = "0_2"
    elif stage == "postbirth":
        if recipient == "household":
            week_range = "0_52"
        elif 0 <= weeks <= 12:
            week_range = "0_12"
        elif 13 <= weeks <= 52:
            week_range = "13_52"
    elif stage == "loss":
        week_range = "0_2"

    if msg_type == "text":
        short_name = "%s.%s.%s.%s" % (
            stage, recipient, msg_type, week_range)
    else:
        short_name = "%s.%s.%s.%s.%s.%s" % (
            stage, recipient, msg_type, week_range, voice_days, voice_times)

    return short_name


def get_messageset_schedule_sequence(short_name, weeks):
    # get messageset
    messageset = get_messageset(short_name)

    messageset_id = messageset["id"]
    schedule_id = messageset["default_schedule"]
    # get schedule
    schedule = get_schedule(schedule_id)

    # calculate next_sequence_number
    # get schedule days of week: comma-seperated str e.g. '1,3' for Mon & Wed
    days_of_week = schedule["day_of_week"]
    # determine how many times a week messages are sent e.g. 2 for '1,3'
    msgs_per_week = len(days_of_week.split(','))
    # determine starting message
    # check if in prebirth stage - only starting messaging in week 10
    if 'miscarriage' in short_name:
        next_sequence_number = 1  # always start loss messages at 1
    elif 'prebirth' in short_name:
        next_sequence_number = msgs_per_week * (
            weeks - settings.PREBIRTH_MIN_WEEKS)
        if next_sequence_number == 0:
            next_sequence_number = 1  # next_sequence_number cannot be 0
    elif '13_52' in short_name:
        next_sequence_number = msgs_per_week * (weeks - 13)
        if next_sequence_number == 0:
            next_sequence_number = 1  # next_sequence_number cannot be 0
    else:
        next_sequence_number = msgs_per_week * weeks
        if next_sequence_number == 0:
            next_sequence_number = 1  # next_sequence_number cannot be 0

    return (messageset_id, schedule_id, next_sequence_number)


def post_message(payload):
    result = requests.post(
        url="%s/outbound/" % settings.MESSAGE_SENDER_URL,
        data=json.dumps(payload),
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Token %s' % (
                settings.MESSAGE_SENDER_TOKEN,)
        }
    ).json()
    return result
