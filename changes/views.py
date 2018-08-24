import django_filters
import django_filters.rest_framework as filters
from .models import Source, Change
from registrations.models import Registration, get_or_incr_cache
from rest_framework import viewsets, mixins, generics, status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import ChangeSerializer
from django.http import JsonResponse
from django.conf import settings
from django.db.models import Q
from hellomama_registration import utils
from .serializers import AdminChangeSerializer, AddChangeSerializer
from seed_services_client import IdentityStoreApiClient

import six


class CreatedAtCursorPagination(CursorPagination):
    ordering = "-created_at"


class ChangePost(mixins.CreateModelMixin, generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Change.objects.all()
    serializer_class = ChangeSerializer

    def post(self, request, *args, **kwargs):
        # load the users sources - posting users should only have one source
        source = Source.objects.get(user=self.request.user)
        request.data["source"] = source.id
        return self.create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user,
                        updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class ChangeFilter(filters.FilterSet):
    """Filter for changes created, using ISO 8601 formatted dates"""
    created_before = django_filters.IsoDateTimeFilter(name="created_at",
                                                      lookup_expr="lte")
    created_after = django_filters.IsoDateTimeFilter(name="created_at",
                                                     lookup_expr="gte")

    class Meta:
        model = Change
        ('action', 'mother_id', 'validated', 'source', 'created_at')
        fields = ['action', 'mother_id', 'validated', 'source',
                  'created_before', 'created_after']


class ChangeGetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Changes to be viewed.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Change.objects.all()
    serializer_class = ChangeSerializer
    filter_class = ChangeFilter
    pagination_class = CreatedAtCursorPagination


class ReceiveIdentityStoreOptout(mixins.CreateModelMixin,
                                 generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        """Handles optout notifications from the Identity Store."""
        try:
            data = utils.json_decode(request.body)
        except ValueError as e:
            return JsonResponse({'reason': "JSON decode error",
                                'details': six.text_type(e)}, status=400)

        try:
            identity_id = data['identity']
            optout_reason = data['optout_reason']
            optout_source = data['optout_source']
        except KeyError as e:
            return JsonResponse({'reason': '"identity", "optout_reason" and '
                                 '"optout_source" must be specified.'
                                 }, status=400)

        registrations = Registration.objects.filter(mother_id=identity_id).\
            order_by('-created_at')

        if not registrations.exists():
            registrations = Registration.objects.filter(
                data__receiver_id=identity_id).order_by('-created_at')

        for registration in registrations:
            if registration.data.get('msg_receiver'):
                fire_optout_receiver_type_metric(
                    registration.data['msg_receiver'])

            fire_optout_reason_metric(optout_reason)

            if registration.data.get('msg_type'):
                fire_optout_message_type_metric(registration.data['msg_type'])

            fire_optout_source_metric(optout_source)

            break

        return JsonResponse({})


def fire_optout_reason_metric(reason):
    from registrations.tasks import fire_metric

    if reason not in settings.OPTOUT_REASONS:
        reason = 'other'

    fire_metric.apply_async(kwargs={
        "metric_name": 'optout.reason.%s.sum' % reason,
        "metric_value": 1.0
    })

    def search_optouts_reason():
        result = utils.search_optouts({"reason": reason})
        return sum(1 for r in result)

    total_key = 'optout.reason.%s.total.last' % reason
    total = get_or_incr_cache(
        total_key,
        search_optouts_reason)
    fire_metric.apply_async(kwargs={
        'metric_name': total_key,
        'metric_value': total,
    })


def fire_optout_source_metric(source):
    from registrations.tasks import fire_metric

    # remove the _public part
    source_short = source.split('_')[0]

    fire_metric.apply_async(kwargs={
        "metric_name": 'optout.source.%s.sum' % source_short,
        "metric_value": 1.0
    })

    def search_optouts_source():
        result = utils.search_optouts({"request_source": source})
        return sum(1 for r in result)

    total_key = 'optout.source.%s.total.last' % source_short
    total = get_or_incr_cache(
        total_key,
        search_optouts_source)
    fire_metric.apply_async(kwargs={
        'metric_name': total_key,
        'metric_value': total,
    })


def fire_optout_receiver_type_metric(msg_receiver):
    from registrations.tasks import fire_metric

    fire_metric.apply_async(kwargs={
        "metric_name": 'optout.receiver_type.%s.sum' % msg_receiver,
        "metric_value": 1.0
    })

    def search_optouts_receiver_type():
        result = utils.search_optouts()

        identities = set(data['identity'] for data in result)

        return Registration.objects.filter(
            Q(
                mother_id__in=identities,
                data__msg_receiver=msg_receiver) |
            Q(
                data__receiver_id__in=identities,
                data__msg_receiver=msg_receiver)).count()

    total_key = 'optout.receiver_type.%s.total.last' % msg_receiver
    total = get_or_incr_cache(
        total_key,
        search_optouts_receiver_type)
    fire_metric.apply_async(kwargs={
        'metric_name': total_key,
        'metric_value': total,
    })


def fire_optout_message_type_metric(msg_type):
    from registrations.tasks import fire_metric

    fire_metric.apply_async(kwargs={
        "metric_name": 'optout.msg_type.%s.sum' % msg_type,
        "metric_value": 1.0
    })

    def search_optouts_message_type():
        result = utils.search_optouts()

        identities = set(data['identity'] for data in result)

        return Registration.objects.filter(
            Q(
                mother_id__in=identities,
                data__msg_type=msg_type) |
            Q(
                data__receiver_id__in=identities,
                data__msg_type=msg_type)).count()

    total_key = 'optout.msg_type.%s.total.last' % msg_type
    total = get_or_incr_cache(
        total_key,
        search_optouts_message_type)
    fire_metric.apply_async(kwargs={
        'metric_name': total_key,
        'metric_value': total,
    })


def get_or_create_source(request):
    source, created = Source.objects.get_or_create(
        user=request.user,
        defaults={
            "authority": "advisor",
            "name": (request.user.get_full_name() or
                     request.user.username)
            })
    return source


class ReceiveAdminOptout(generics.CreateAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = ChangeSerializer

    def post(self, request, *args, **kwargs):

        source = get_or_create_source(self.request)

        request.data['source'] = source.id
        request.data['data'] = {"reason": "other"}
        request.data['action'] = "unsubscribe_mother_only"

        return super(ReceiveAdminOptout, self).post(request, *args, **kwargs)


class ReceiveAdminChange(generics.CreateAPIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):

        admin_serializer = AdminChangeSerializer(data=request.data)
        if admin_serializer.is_valid():
            data = admin_serializer.validated_data
        else:
            return Response(admin_serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        source = get_or_create_source(self.request)

        changes = []
        if data.get('messageset'):
            change = {
                "mother_id": str(data['mother_id']),
                "action": "change_messaging",
                "data": {"new_short_name": data['messageset']},
                "source": source.id,
            }
            if data.get('language'):
                change["data"]["new_language"] = data['language']
            changes.append(change)

        elif data.get('language'):
            change = {
                "mother_id": str(data['mother_id']),
                "action": "change_language",
                "data": {"new_language": data['language']},
                "source": source.id,
            }
            changes.append(change)

        serializer = ChangeSerializer(data=changes, many=True)

        if serializer.is_valid():
            serializer.save()

            return Response(data=serializer.data,
                            status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)


class AddChangeView(generics.CreateAPIView):

    """ AddChangeView Interaction
        POST - Validates and Saves the change, optouts if needed
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        add_serializer = AddChangeSerializer(data=request.data)
        if add_serializer.is_valid():
            data = add_serializer.validated_data
        else:
            return Response(add_serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            source = Source.objects.get(user=self.request.user)
        except Source.DoesNotExist:
            return Response("Source not found for user.",
                            status=status.HTTP_400_BAD_REQUEST)

        data["source"] = source.id

        ids_client = IdentityStoreApiClient(
            settings.IDENTITY_STORE_TOKEN, settings.IDENTITY_STORE_URL)

        if data.get('msisdn'):
            data['msisdn'] = utils.normalize_msisdn(data['msisdn'], '234')
            identity = ids_client.get_identity_by_address('msisdn',
                                                          data['msisdn'])
            try:
                mother_identity = next(identity['results'])
            except StopIteration:
                return Response({"msisdn": ["No identity for this number."]},
                                status=status.HTTP_400_BAD_REQUEST)
            data['mother_id'] = mother_identity['id']

        if ('voice_days' in data['data']):
            data['data']['voice_days'] = utils.get_voice_days(
                data['data']['voice_days'])

        if ('voice_times' in data['data']):
            data['data']['voice_times'] = utils.get_voice_times(
                data['data']['voice_times'])

        if ('msg_type' in data['data']):
            data['data']['msg_type'] = utils.get_msg_type(
                data['data']['msg_type'])

        if ('new_language' in data['data']):
            data['data']['new_language'] = utils.get_language(
                data['data']['new_language'])

        if data['data'].get('household_msisdn'):
            data['data']['household_msisdn'] = utils.normalize_msisdn(
                data['data']['household_msisdn'], '234')
            households = ids_client.get_identity_by_address(
                'msisdn', data['data']['household_msisdn'])['results']
            try:
                household = next(households)
            except StopIteration:
                return Response({"household_msisdn":
                                ["No identity for this number."]},
                                status=status.HTTP_400_BAD_REQUEST)
            data['data']['household_id'] = household['id']

            if (not data.get('msisdn') and
                    household['details'].get('linked_to')):
                data['mother_id'] = household['details']['linked_to']

        if 'unsubscribe' in data['action']:
            identity_id = data['mother_id']
            msisdn = data.get('msisdn')
            if data['action'] == 'unsubscribe_household_only':
                identity_id = data['data']['household_id']
                msisdn = data.get('household_msisdn')

            optout_info = {
                'optout_type': 'stop',
                'identity': identity_id,
                'reason': data['data']['reason'],
                'address_type': 'msisdn',
                'address': msisdn,
                'request_source': source.name,
                'requestor_source_id': source.id
            }
            ids_client.create_optout(optout_info)

        serializer = ChangeSerializer(data=data)

        if serializer.is_valid():
            serializer.save(created_by=self.request.user,
                            updated_by=self.request.user)

            return Response(data=serializer.data,
                            status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
