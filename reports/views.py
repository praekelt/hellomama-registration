from datetime import datetime
from django.core.urlresolvers import reverse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.pagination import CursorPagination

from reports.tasks.detailed_report import generate_report
from reports.tasks.msisdn_message_report import generate_msisdn_message_report
from reports.serializers import (ReportGenerationSerializer,
                                 ReportTaskStatusSerializer)
from reports.models import ReportTaskStatus


class ReportsView(APIView):
    """ Reports generation
        GET: lists available reports
        POST: creates a task to generate a detailed report
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        response = {
            'reports': {
                'detailed': {
                    'name': 'Detailed report',
                    'endpoint': reverse('generate-reports'),
                },
                'msisdn-messages': {
                    'name': 'MSISDN messages report',
                    'endpoint': reverse('generate-report-msisdn-messages'),
                },
            },
        }

        return Response(response, status=200)

    def post(self, request, *args, **kwargs):
        serializer = ReportGenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        task_status = ReportTaskStatus.objects.create(**{
            "start_date": datetime.strftime(data['start_date'], '%Y-%m-%d'),
            "end_date": datetime.strftime(data['end_date'], '%Y-%m-%d'),
            "email_subject": data['email_subject'],
            "status": ReportTaskStatus.PENDING
        })

        generate_report.apply_async(kwargs={
            "start_date": datetime.strftime(data['start_date'], '%Y-%m-%d'),
            "end_date": datetime.strftime(data['end_date'], '%Y-%m-%d'),
            "task_status_id": task_status.id,
            "email_recipients": data['email_to'],
            "email_sender": data['email_from'],
            "email_subject": data['email_subject']})
        status = 202
        resp = {"report_generation_requested": True}
        return Response(resp, status=status)


class MSISDNMessagesReportView(APIView):
    """
    Generate a report of MSISDNs and the messages they've received.

    POST: Start generating a report.
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        request_data = request.data.copy()

        serializer = ReportGenerationSerializer(data=request_data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        task_status = ReportTaskStatus.objects.create(**{
            "start_date": datetime.strftime(data['start_date'], '%Y-%m-%d'),
            "end_date": datetime.strftime(data['end_date'], '%Y-%m-%d'),
            "email_subject": data['email_subject'],
            "status": ReportTaskStatus.PENDING,
        })

        generate_msisdn_message_report.apply_async(kwargs={
            "start_date": datetime.strftime(data['start_date'], '%Y-%m-%d'),
            "end_date": datetime.strftime(data['end_date'], '%Y-%m-%d'),
            "task_status_id": task_status.id,
            "msisdns": data['msisdns'],
            "email_recipients": data['email_to'],
            "email_sender": data['email_from'],
            "email_subject": data['email_subject']
        })

        return Response({"report_generation_requested": True}, status=202)


class SmallResultsSetPagination(CursorPagination):
    ordering = '-created_at'
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 10


class ReportTaskStatusViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows ReportTaskStatus to be viewed.
    """
    permission_classes = (IsAuthenticated,)
    queryset = ReportTaskStatus.objects.all()
    serializer_class = ReportTaskStatusSerializer
    pagination_class = SmallResultsSetPagination
    ordering_fields = ('created_at',)
