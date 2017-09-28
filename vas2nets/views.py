from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hellomama_registration import utils
from .tasks import fetch_voice_data


class FetchVoiceDataView(APIView):

    """ FetchVoiceData Interaction
        POST - starts up the task that pulls voice data from the vas2nets
        portal
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        status = 202
        date = utils.get_today() - timedelta(1)
        task_id = fetch_voice_data.apply_async(
            args=[date.strftime('%Y-%m-%d')])
        resp = {"fetch_voice_data_initiated": True, "task_id": str(task_id)}
        return Response(resp, status=status)
