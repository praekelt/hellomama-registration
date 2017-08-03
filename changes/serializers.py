from .models import Change
from rest_framework import serializers
from seed_services_client.stage_based_messaging \
    import StageBasedMessagingApiClient
from django.conf import settings
from hellomama_registration import utils


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


class LanguageValidator:

    def set_context(self, serializer):
        self.is_create = getattr(serializer, 'instance', None) is None

    def __call__(self, data):
        if self.is_create:

            if data.get('language'):
                new_lang = data['language']

                sbmApi = StageBasedMessagingApiClient(
                    api_url=settings.STAGE_BASED_MESSAGING_URL,
                    auth_token=settings.STAGE_BASED_MESSAGING_TOKEN
                )

                messagesets = []
                languages = sbmApi.get_messageset_languages()
                if data.get('messageset'):
                    short_name = data['messageset']
                    messagesets.append(str(utils.get_messageset_by_shortname(
                        short_name)['id']))
                else:
                    subscriptions = utils.get_subscriptions(data['mother_id'])
                    for subscription in subscriptions:
                        messagesets.append(str(subscription['messageset']))

                for messageset_id in messagesets:
                    if new_lang not in languages.get(messageset_id, []):
                        raise serializers.ValidationError(
                            "The language is invalid for the messageset")


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

    validators = [
        OneFieldRequiredValidator(['messageset', 'language']),
        LanguageValidator()
    ]


class AddChangeSerializer(serializers.ModelSerializer):
    msisdn = serializers.CharField(required=True)

    class Meta:
        model = Change
        read_only_fields = ('validated', 'created_by', 'updated_by',
                            'created_at', 'updated_at')
        fields = ('id', 'action', 'msisdn', 'data', 'validated', 'created_at',
                  'updated_at', 'created_by', 'updated_by')
