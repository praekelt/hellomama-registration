from .models import Change
from rest_framework import serializers


class OneFieldRequiredValidator:
    def __init__(self, fields):
        self.fields = fields

    def set_context(self, serializer):
        self.is_create = getattr(serializer, 'instance', None) is None

    def __call__(self, data):
        if self.is_create:

            for field in self.fields:
                if data.get(field):
                    return

            raise serializers.ValidationError(
                "One of these fields must be populated: %s" %
                (', '.join(self.fields)))


class ChangeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Change
        read_only_fields = ('validated', 'created_by', 'updated_by',
                            'created_at', 'updated_at')
        fields = ('id', 'action', 'mother_id', 'data', 'validated', 'source',
                  'created_at', 'updated_at', 'created_by', 'updated_by')


class AdminChangeSerializer(serializers.Serializer):
    mother_id = serializers.UUIDField(allow_null=False)
    subscription = serializers.UUIDField(required=False)
    messageset = serializers.CharField(required=False)
    language = serializers.CharField(required=False)

    validators = [OneFieldRequiredValidator(['messageset', 'language'])]
