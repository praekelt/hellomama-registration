from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hellomama_registration import utils
from .tasks import (
    fetch_voice_data, fetch_voice_data_history, sync_welcome_audio)


class FetchVoiceDataView(APIView):

    """ FetchVoiceData Interaction
        POST - starts up the task that pulls voice data from the vas2nets
        portal
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        status = 202

        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')

        if start_date and end_date:
            task_name = "fetch_voice_data_history"
            task_id = fetch_voice_data_history.apply_async(
                args=[start_date, end_date])
        else:
            date = utils.get_today() - timedelta(1)
            task_name = "fetch_voice_data"
            task_id = fetch_voice_data.apply_async(
                args=[date.strftime('%Y-%m-%d')])

        resp = {
            "%s_initiated" % (task_name): True,
            "task_id": str(task_id),
        }

        return Response(resp, status=status)


class SyncWelcomeAudioView(APIView):

    """ SyncWelcomeAudio Interaction
        POST - starts up the task that sync the welcome audio files with the
        vas2nets sftp folder
    """
    def post(self, request, *args, **kwargs):
        status = 202

        task_id = sync_welcome_audio.apply_async()

        resp = {
            "sync_welcome_audio_initiated": True,
            "task_id": str(task_id),
        }

        return Response(resp, status=status)


class ResendLastMessageView(APIView):

    """ Triggers a re-send on the msisdn
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """ Finds the identity and subscriptions linked to the MSISDN and
            triggers a resend on each subscription.
        """
        try:
            msisdn = request.data["msisdn"]
            msisdn = utils.normalize_msisdn(msisdn, '234')

            identity = self.get_identity(msisdn)

            if identity:
                subscriptions = utils.get_subscriptions(identity['id'])
                resent = 0
                for subscription in subscriptions:
                    if (
                            subscription['completed'] or
                            subscription['process_status'] not in (0, 1)):
                        continue

                    utils.resend_subscription(subscription['id'])
                    resent += 1

                status = 202
                response = {"accepted": True, "resent_count": resent}
            else:
                status = 400
                response = {
                    "accepted": False,
                    "reason": "Cannot find identity for MSISDN {}".format(
                        msisdn)}
        except KeyError as error:
            status = 400
            response = {"accepted": False,
                        "reason": 'Missing field: {}'.format(error)}

        return Response(response, status=status)

    def get_identity(self, msisdn):
        identities = utils.search_identities(
            "details__addresses__msisdn", msisdn)

        for identity in identities:
            return identity
