from django.contrib.auth.models import User, Group
from .models import Source, Registration
from rest_hooks.models import Hook
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'groups')


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ('url', 'name')


class CreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()


class SourceSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Source
        read_only_fields = ('created_at', 'updated_at')
        fields = ('url', 'id', 'name', 'user', 'authority', 'created_at',
                  'updated_at')


class RegistrationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Registration
        read_only_fields = ('validated', 'created_by', 'updated_by',
                            'created_at', 'updated_at')
        fields = ('id', 'stage', 'validated', 'mother_id', 'data', 'source',
                  'created_at', 'updated_at', 'created_by', 'updated_by')


class HookSerializer(serializers.ModelSerializer):

    class Meta:
        model = Hook
        read_only_fields = ('user',)
        exclude = ()
