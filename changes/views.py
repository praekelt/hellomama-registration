import django_filters
from .models import Source, Change
from rest_framework import viewsets, mixins, generics, filters
from rest_framework.permissions import IsAuthenticated
from .serializers import ChangeSerializer
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from hellomama_registration import utils

import functools
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


def token_auth_required(auth_token_func):
    '''Decorates a function so that token authentication is required to run it
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            auth_header = request.META.get('HTTP_AUTHORIZATION', None)
            expected_auth_token = auth_token_func()
            if not auth_header:
                response = JsonResponse(
                    {"reason": "Authentication required"}, status=401)
                response['WWW-Authenticate'] = "Token"
                return response
            auth = auth_header.split(" ")
            if auth != ["Token", expected_auth_token]:
                return JsonResponse({"reason": "Forbidden"}, status=403)
            return func(request, *args, **kwargs)

        return wrapper
    return decorator


def seed_auth_token():
    return settings.IDENTITY_AUTH_TOKEN


@csrf_exempt
@token_auth_required(seed_auth_token)
def receive_identity_store_optout(request):
    """Handles optout notifications from the Identity Store."""
    if request.method != "POST":
        return JsonResponse({'reason': "Method not allowed."}, status=405)

    try:
        data = utils.json_decode(request.body)
    except ValueError as e:
        return JsonResponse({'reason': "JSON decode error",
                            'details': six.text_type(e)}, status=400)

    try:
        identity_id = data['identity']
        optout_type = data['optout_type']
        optout_reason = data['optout_reason']
    except KeyError as e:
        return JsonResponse({'reason': '"identity", "optout_type" and \
                                        "optout_reason" must be specified.'},
                            status=400)

    fire_optout_reason_metric(optout_reason)


def fire_optout_reason_metric(reason):
    from registrations.tasks import fire_metric

    fire_metric.apply_async(kwargs={
        "metric_name": 'optout.reason.%s.sum' % reason,
        "metric_value": 1.0
    })
