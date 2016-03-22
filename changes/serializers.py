from .models import Change
from rest_framework import serializers


class ChangeSerializer(serializers.ModelSerializer):

    class Meta:
        model = Change
        read_only_fields = ('validated', 'created_by', 'updated_by',
                            'created_at', 'updated_at')
        fields = ('id', 'action', 'mother_id', 'data', 'validated', 'source',
                  'created_at', 'updated_at', 'created_by', 'updated_by')
