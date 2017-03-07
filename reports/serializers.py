from django.utils import timezone
from rest_framework import serializers
from reports.utils import midnight, midnight_validator, one_month_after


class ReportGenerationSerializer(serializers.Serializer):
    output_file = serializers.CharField()
    start_date = serializers.CharField(allow_blank=True, required=False)
    end_date = serializers.CharField(allow_blank=True, required=False)
    email_to = serializers.ListField(
        child=serializers.EmailField(), required=False)
    email_from = serializers.EmailField(allow_blank=True, required=False)
    email_subject = serializers.CharField(allow_blank=True, required=False)

    def validate(self, data):
        if 'start_date' not in data:
            data['start_date'] = midnight(timezone.now())

        if 'end_date' not in data:
            data['end_date'] = one_month_after(data['start_date'])
        return data

    def validate_date(self, value):
        try:
            date = midnight_validator(value)
        except ValueError as e:
            raise serializers.ValidationError(e.message)
        return date

    def validate_start_date(self, value):
        return self.validate_date(value)

    def validate_end_date(self, value):
        return self.validate_date(value)
