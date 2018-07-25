from .models import Record, State
from rest_framework import serializers


class RecordSerializer(serializers.ModelSerializer):

    class Meta:
        model = Record
        read_only_fields = ('id')
        fields = ('id', 'identity', 'write_to', 'length',
                  'created_at', 'created_by')


class StateSerializer(serializers.ModelSerializer):

    class Meta:
        model = State
        read_only_fields = ('id', 'name')
        fields = '__all__'
