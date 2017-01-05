import django_filters
from .models import Source, Change
from registrations.models import Registration, get_or_incr_cache
from rest_framework import viewsets, mixins, generics, filters
from rest_framework.permissions import IsAuthenticated
from .serializers import ChangeSerializer
from django.http import JsonResponse
from hellomama_registration import utils

import six


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
                                                      lookup_type="lte")
    created_after = django_filters.IsoDateTimeFilter(name="created_at",
                                                     lookup_type="gte")

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
            # optout_type = data['optout_type']
            optout_reason = data['optout_reason']
        except KeyError as e:
            return JsonResponse({'reason': '"identity", "optout_type" and '
                                '"optout_reason" must be specified.'
                                 }, status=400)

        registration = Registration.objects.get(mother_id=identity_id)
        if registration.data.get('msg_receiver'):
            fire_optout_receiver_type_metric(registration.data['msg_receiver'])

        fire_optout_reason_metric(optout_reason)

        return JsonResponse({})


def fire_optout_reason_metric(reason):
    from registrations.tasks import fire_metric

    fire_metric.apply_async(kwargs={
        "metric_name": 'optout.reason.%s.sum' % reason,
        "metric_value": 1.0
    })

    def search_optouts_reason():
        result = utils.search_optouts({"reason": reason})
        return len(list(result))

    total_key = 'optout.reason.%s.total.last' % reason
    total = get_or_incr_cache(
        total_key,
        search_optouts_reason)
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
