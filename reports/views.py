from datetime import datetime
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.tasks import generate_report
from reports.serializers import ReportGenerationSerializer


class ReportsView(APIView):
    """ Reports Generation
        POST - starts up the task that generates the reports
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = ReportGenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        generate_report.apply_async(kwargs={
            "start_date": datetime.strftime(data['start_date'], '%Y-%m-%d'),
            "end_date": datetime.strftime(data['end_date'], '%Y-%m-%d'),
            "email_recipients": data['email_to'],
            "email_sender": data['email_from'],
            "email_subject": data['email_subject']})
        status = 202
        resp = {"report_generation_requested": True}
        return Response(resp, status=status)
