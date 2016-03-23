from celery.task import Task

from hellomama_registration import utils
from registrations.models import Registration, SubscriptionRequest
from .models import Change


class ImplementAction(Task):
    """ Task to apply a Change action.
    """
    name = "hellomama_registration.changes.tasks.implement_action"

    def change_baby(self, change):
        # Get mother's current subscription
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)
        # Get mother's preferred msg_format
        mother = utils.get_identity(change.mother_id)
        # Get mother's registration
        registration = Registration.objects.get(mother_id=change.mother_id)

        stage = 'postbirth'
        weeks = 0
        voice_days = mother["details"]["preferred_msg_days"]
        voice_times = mother["details"]["preferred_msg_times"]

        mother_short_name = utils.get_messageset_short_name(
            stage, 'mother', mother["details"]["preferred_msg_type"],
            weeks, voice_days, voice_times)

        mother_msgset_id, mother_msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(mother_short_name, weeks)

        # Make new subscription request object
        mother_sub = {
            "contact": change.mother_id,
            "messageset": mother_msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": mother["details"]["preferred_language"],
            "schedule": mother_msgset_schedule
        }
        SubscriptionRequest.objects.create(**mother_sub)

        # Make household subscription if required
        if registration.data["msg_receiver"] != 'mother_only':
            household_short_name = utils.get_messageset_short_name(
                stage, 'household', mother["details"]["preferred_msg_type"],
                weeks, None, None)
            household_msgset_id, household_msgset_schedule, seq_number =\
                utils.get_messageset_schedule_sequence(
                    household_short_name, weeks)
            household_sub = {
                "contact": mother["details"]["linked_to"],
                "messageset": household_msgset_id,
                "next_sequence_number": seq_number,
                "lang": mother["details"]["preferred_language"],
                "schedule": household_msgset_schedule
            }
            SubscriptionRequest.objects.create(**household_sub)

        return "Change baby completed"

    def change_loss(self, change):
        pass

    def change_messaging(self, change):
        # Get mother's current subscription
        subscriptions = utils.get_subscriptions(change.mother_id)
        # Deactivate subscriptions
        for subscription in subscriptions:
            utils.deactivate_subscription(subscription)
        # Get mother's registration
        registration = Registration.objects.get(mother_id=change.mother_id)

        # Determine stage & week
        # TODO #33: handle miscarriage stage
        # if the registration was for postbirth, we can assume postbirth
        if registration.stage == 'postbirth':
            stage = 'postbirth'
            weeks = utils.calc_baby_age(
                utils.get_today(),
                registration.data["baby_dob"])
        # otherwise, we need to look if the user has changed to baby
        else:
            baby_switch = Change.objects.filter(mother_id=change.mother_id,
                                                action='change_baby')
            if baby_switch.count() > 0:
                # TODO #32: handle a person that has switched to baby for a
                # previous pregnancy
                stage = 'postbirth'
                weeks = utils.calc_baby_age(
                    utils.get_today(),
                    baby_switch.created_at[0:10].replace('-', ''))
            else:
                stage = 'prebirth'
                weeks = utils.calc_pregnancy_week_lmp(
                    utils.get_today(), registration.data["last_period_date"])

        # Determine voice_days & voice_times
        if 'voice_days' in change.data:
            voice_days = change.data["voice_days"]
            voice_times = change.data["voice_times"]
        else:
            voice_days = None
            voice_times = None

        mother_short_name = utils.get_messageset_short_name(
            stage, 'mother', change.data["msg_type"],
            weeks, voice_days, voice_times)

        mother_msgset_id, mother_msgset_schedule, next_sequence_number =\
            utils.get_messageset_schedule_sequence(mother_short_name, weeks)

        # Make new subscription request object
        mother_sub = {
            "contact": change.mother_id,
            "messageset": mother_msgset_id,
            "next_sequence_number": next_sequence_number,
            "lang": subscriptions[0]["lang"],  # use first subscription's lang
            "schedule": mother_msgset_schedule
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
        pass

    def unsubscribe_mother_only(self, change):
        pass

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
