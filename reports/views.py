from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.tasks import generate_report
from reports.utils import midnight, midnight_validator, one_month_after


class ReportsView(APIView):

    """ Reports Generation
        POST - starts up the task that generates the reports
    """
    permission_classes = (IsAdminUser,)

    def post(self, request, *args, **kwargs):
        try:
            output_file = request.data['output_file']
        except KeyError:
            raise ValidationError("Please specify 'output_file'.")
        if 'start_date' in request.data:
            start_date = midnight_validator(request.data['start_date'])
        else:
            start_date = midnight(timezone.now())
        if 'end_date' in request.data:
            end_date = midnight_validator(request.data['end_date'])
        else:
            end_date = one_month_after(start_date)
        email_to = request.data.get('email_to', [])
        email_from = request.data.get(
            'email_from', settings.DEFAULT_FROM_EMAIL)
        email_subject = request.data.get(
            'email_subject', 'Seed Control Interface Generated Report')

        generate_report.apply_async(output_file=output_file,
                                    start_date=start_date, end_date=end_date,
                                    email_recipients=email_to,
                                    email_sender=email_from,
                                    email_subject=email_subject)
        status = 200
        resp = {"report_generation_requested": True}
        return Response(resp, status=status)
