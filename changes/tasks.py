from celery.task import Task

from hellomama_registration import utils
from registrations.models import Registration, SubscriptionRequest
from .models import Change


class ImplementAction(Task):
    """ Task to apply a Change action.
    """
    name = "hellomama_registration.changes.tasks.implement_action"

    def change_baby(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)
        # Get mother's identity
        mother = utils.get_identity(change.mother_id)
        # Get mother's registration
        registrations = Registration.objects.\
            filter(mother_id=change.mother_id, stage='prebirth').\
            order_by('-created_at')

        stage = 'postbirth'
        weeks = 0
        voice_days = mother["details"].get("preferred_msg_days")
        voice_times = mother["details"].get("preferred_msg_times")

        mother_short_name = utils.get_messageset_short_name(
            stage, 'mother', mother["details"]["preferred_msg_type"],
            weeks, voice_days, voice_times)

        mother_msgset_id, mother_msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(mother_short_name, weeks)

        # Make new subscription request object
        mother_sub = {
            "identity": change.mother_id,
            "messageset": mother_msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": mother["details"]["preferred_language"],
            "schedule": mother_msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        # Make household subscription if required
        for registration in registrations:
            if registration.data["msg_receiver"] != 'mother_only':
                household_short_name = utils.get_messageset_short_name(
                    stage, 'household', mother["details"]
                    ["preferred_msg_type"], weeks, "fri", "9_11")
                household_msgset_id, household_msgset_schedule, seq_number =\
                    utils.get_messageset_schedule_sequence(
                        household_short_name, weeks)
                household_sub = {
                    "identity": mother["details"]["linked_to"],
                    "messageset": household_msgset_id,
                    "next_sequence_number": seq_number,
                    "lang": mother["details"]["preferred_language"],
                    "schedule": household_msgset_schedule
                }
                SubscriptionRequest.objects.create(**household_sub)
            break

        return "Change baby completed"

    def change_loss(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)
        # Get mother's identity
        mother = utils.get_identity(change.mother_id)

        stage = 'miscarriage'
        weeks = 0
        voice_days = mother["details"].get("preferred_msg_days")
        voice_times = mother["details"].get("preferred_msg_times")

        mother_short_name = utils.get_messageset_short_name(
            stage, 'mother', mother["details"]["preferred_msg_type"],
            weeks, voice_days, voice_times)

        mother_msgset_id, mother_msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(mother_short_name, weeks)

        # Make new subscription request object
        mother_sub = {
            "identity": change.mother_id,
            "messageset": mother_msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": mother["details"]["preferred_language"],
            "schedule": mother_msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        # Get mother's registration
        registrations = Registration.objects.\
            filter(mother_id=change.mother_id, stage='prebirth').\
            order_by('-created_at')
        for registration in registrations:
            if registration.data["msg_receiver"] != 'mother_only':
                # Get household's current subscriptions
                subscriptions = utils.get_subscriptions(
                    mother["details"]["linked_to"])
                # Deactivate subscriptions
                for subscription in subscriptions:
                    utils.deactivate_subscription(subscription)
            break

        return "Change loss completed"

    def change_messaging(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(change.mother_id)
        current_sub = subscriptions[0]  # necessary assumption
        current_nsn = current_sub["next_sequence_number"]

        # get current subscription's messageset
        current_msgset = utils.get_messageset(current_sub["messageset"])

        # get current subscription's schedule
        current_sched = utils.get_schedule(current_sub["schedule"])
        current_days = current_sched["day_of_week"]
        current_rate = len(current_days.split(','))  # msgs per week

        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)

        # Determine voice_days & voice_times
        if change.data["msg_type"] == 'audio':
            to_type = 'audio'
            voice_days = change.data["voice_days"]
            voice_times = change.data["voice_times"]
        else:
            to_type = 'text'
            voice_days = None
            voice_times = None

        if 'audio' in current_msgset["short_name"]:
            from_type = 'audio'
        else:
            from_type = 'text'

        if 'miscarriage' in current_msgset["short_name"]:
            stage = 'miscarriage'
            weeks = 1  # just a placeholder to get the messageset_short_name
        elif 'postbirth' in current_msgset["short_name"]:
            stage = 'postbirth'
            # set placeholder weeks for getting the messageset_short_name
            if '0_12' in current_msgset["short_name"]:
                weeks = 1
            else:
                weeks = 13
        else:
            stage = 'prebirth'
            weeks = 11  # just a placeholder to get the messageset_short_name

        new_short_name = utils.get_messageset_short_name(
            stage, 'mother', to_type,
            weeks, voice_days, voice_times)

        new_msgset_id, new_msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(new_short_name, weeks)

        # calc new_nsn rather than using next_sequence_number
        if from_type == to_type:
            new_nsn = current_nsn
        else:
            new_sched = utils.get_schedule(new_msgset_schedule)
            new_days = new_sched["day_of_week"]
            new_rate = len(new_days.split(','))  # msgs per week

        new_nsn = int(current_nsn * new_rate / float(current_rate))
        # prevent rounding nsn to 0
        if new_nsn == 0:
            new_nsn = 1

        # Make new subscription request object
        mother_sub = {
            "identity": change.mother_id,
            "messageset": new_msgset_id,
            "next_sequence_number": new_nsn,
            "lang": current_sub["lang"],  # use first subscription's lang
            "schedule": new_msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        return "Change messaging completed"

    def change_language(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Patch subscriptions languages
        for subscription in subscriptions:
            utils.patch_subscription(
                subscription, {"lang": change.data["new_language"]})

        if change.data["household_id"]:
            # Get household's current subscriptions
            subscriptions = utils.get_subscriptions(
                change.data["household_id"])
            # Patch subscriptions languages
            for subscription in subscriptions:
                utils.patch_subscription(
                    subscription, {"lang": change.data["new_language"]})

        return "Change language completed"

    def unsubscribe_household_only(self, change):
        # Get household's current subscriptions
        subscriptions = utils.get_subscriptions(
            change.data["household_id"])
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)

        return "Unsubscribe household completed"

    def unsubscribe_mother_only(self, change):
        # Get mother's current subscriptions
        subscriptions = utils.get_subscriptions(
            change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)

        return "Unsubscribe mother completed"

    def run(self, change_id, **kwargs):
        """ Implements the appropriate action
        """
        change = Change.objects.get(id=change_id)

        result = {
            'change_baby': self.change_baby,
            'change_loss': self.change_loss,
            'change_messaging': self.change_messaging,
            'change_language': self.change_language,
            'unsubscribe_household_only': self.unsubscribe_household_only,
            'unsubscribe_mother_only': self.unsubscribe_mother_only,
        }.get(change.action, None)(change)
        return result

implement_action = ImplementAction()
