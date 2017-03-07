from django.conf import settings
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.tasks import generate_report
from reports.serializers import ReportGenerationSerializer


class ReportsView(APIView):
    """ Reports Generation
        POST - starts up the task that generates the reports
    """
    permission_classes = (IsAdminUser,)

    def post(self, request, *args, **kwargs):
        serializer = ReportGenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        email_recipients = data.get('email_to', [])
        email_sender = data.get('email_from', settings.DEFAULT_FROM_EMAIL)
        email_subject = data.get(
            'email_subject', 'Seed Control Interface Generated Report')

        generate_report.apply_async(output_file=data['output_file'],
                                    start_date=data['start_date'],
                                    end_date=data['end_date'],
                                    email_recipients=email_recipients,
                                    email_sender=email_sender,
                                    email_subject=email_subject)
        status = 202
        resp = {"report_generation_requested": True}
        return Response(resp, status=status)
