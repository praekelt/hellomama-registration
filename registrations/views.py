import django_filters
import django_filters.rest_framework as filters
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.db import connection
from .models import Source, Registration
from rest_hooks.models import Hook
from rest_framework import viewsets, mixins, generics, status
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from .serializers import (UserSerializer, GroupSerializer,
                          SourceSerializer, RegistrationSerializer,
                          HookSerializer, CreateUserSerializer)
from hellomama_registration import utils
# Uncomment line below if scheduled metrics are added
# from .tasks import scheduled_metrics
from .tasks import (
    pull_third_party_registrations, send_public_registration_notifications)


class CreatedAtCursorPagination(CursorPagination):
    ordering = '-created_at'


class IdCursorPagination(CursorPagination):
    ordering = 'id'


class HookViewSet(viewsets.ModelViewSet):
    """
    Retrieve, create, update or destroy webhooks.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Hook.objects.all()
    serializer_class = HookSerializer
    pagination_class = IdCursorPagination

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserViewSet(viewsets.ReadOnlyModelViewSet):

    """
    API endpoint that allows users to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = IdCursorPagination


class GroupViewSet(viewsets.ReadOnlyModelViewSet):

    """
    API endpoint that allows groups to be viewed or edited.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    pagination_class = IdCursorPagination


class UserView(APIView):
    """ API endpoint that allows users creation and returns their token.
    Only admin users can do this to avoid permissions escalation.
    """
    permission_classes = (IsAdminUser,)

    def post(self, request):
        '''Create a user and token, given an email. If user exists just
        provide the token.'''
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get('email')
        try:
            user = User.objects.get(username=email)
        except User.DoesNotExist:
            user = User.objects.create_user(email, email=email)
        token, created = Token.objects.get_or_create(user=user)

        return Response(
            status=status.HTTP_201_CREATED, data={'token': token.key})


class SourceViewSet(viewsets.ModelViewSet):

    """
    API endpoint that allows sources to be viewed or edited.
    """
    permission_classes = (IsAdminUser,)
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    pagination_class = IdCursorPagination


class MetricsView(APIView):

    """ Metrics Interaction
        GET - returns list of all available metrics on the service
        POST - starts up the task that fires all the scheduled metrics
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        status = 200
        resp = {
            "metrics_available": utils.get_available_metrics()
        }
        return Response(resp, status=status)

    def post(self, request, *args, **kwargs):
        status = 201
        # Uncomment line below if scheduled metrics are added
        # scheduled_metrics.apply_async()
        resp = {"scheduled_metrics_initiated": True}
        return Response(resp, status=status)


class RegistrationPostPatch(mixins.CreateModelMixin, mixins.UpdateModelMixin,
                            generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer
    lookup_field = 'id'

    def post(self, request, *args, **kwargs):
        # load the users sources - posting users should only have one source
        source = Source.objects.get(user=self.request.user)
        request.data["source"] = source.id
        return self.create(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user,
                        updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class RegistrationFilter(filters.FilterSet):
    """Filter for registrations created, using ISO 8601 formatted dates"""
    created_before = django_filters.IsoDateTimeFilter(name="created_at",
                                                      lookup_expr="lte")
    created_after = django_filters.IsoDateTimeFilter(name="created_at",
                                                     lookup_expr="gte")

    class Meta:
        model = Registration
        ('stage', 'mother_id', 'validated', 'source', 'created_at')
        fields = ['stage', 'mother_id', 'validated', 'source',
                  'created_before', 'created_after']


class RegistrationGetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows Registrations to be viewed.
    """
    permission_classes = (IsAuthenticated,)
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer
    filter_class = RegistrationFilter
    pagination_class = CreatedAtCursorPagination


class HealthcheckView(APIView):

    """ Healthcheck Interaction
        GET - returns service up - getting auth'd requires DB
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        status = 200
        resp = {
            "up": True,
            "result": {
                "database": "Accessible"
            }
        }
        return Response(resp, status=status)


class ThirdPartyRegistrationView(APIView):

    """ ThirdPartyRegistrationView Interaction
        POST - starts up the task that pulls registrations from a 3rd party
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        status = 201
        pull_third_party_registrations.apply_async(args=[self.request.user.id])
        resp = {"third_party_registration_pull_initiated": True}
        return Response(resp, status=status)


class AddRegistrationView(APIView):

    """ ThirdPartyRegistrationView Interaction
        POST - Validates and Saves the registration
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        status = 201
        resp = {"registration_added": True}

        try:
            source = Source.objects.get(user=self.request.user.id)

            # EH - We have changed this field name to more accurately reflect
            # what is being sent. This is a failsafe to accept both old and
            # new. We have to make sure all 3rd parties pushing registrations
            # have updated before we remove it.
            # Also remove tests.py/test_add_registration_old_keys
            if('health_worker_phone_number' in request.data and
                    'health_worker_personnel_code' not in request.data):
                request.data['health_worker_personnel_code'] = \
                    request.data['health_worker_phone_number']

            pull_third_party_registrations.create_registration(
                request.data, source)
        except Source.DoesNotExist as error:
            resp['registration_added'] = False
            resp['error'] = str(error)
            status = 400
        except KeyError as error:
            resp['registration_added'] = False
            resp['error'] = 'Missing field: %s' % str(error)
            status = 400
        except Exception as error:
            resp['registration_added'] = False
            resp['error'] = str(error)
            status = 400

        return Response(resp, status=status)


class PersonnelCodeView(APIView):

    """ PersonnelCodeView Interaction
        GET - returns a list of personnel codes
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        identities = utils.search_identities(
            "details__has_key", "personnel_code")

        codes = set()
        for identity in identities:
            codes.add(identity['details'].get('personnel_code'))

        return Response({"results": list(codes)}, status=200)


class SendPublicRegistrationNotificationView(APIView):

    """ Triggers a notification send to operators about subscribers not on the
        full set
    """
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):

        status = 202
        accepted = {"accepted": True}
        send_public_registration_notifications.delay()
        return Response(accepted, status=status)


class UserDetailList(APIView):
    """ UserDetailList Interaction
        GET - returns a detailed list of system users
    """
    permission_classes = (IsAuthenticated,)

    def get_data(self, page_size, offset):

        def dictfetchall(cursor):
            """Return all rows from a cursor as a dict"""
            columns = [col[0] for col in cursor.description]
            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        sql = """
            select *
            from get_registrations('{}', '*', '*', '*', '*', {}, {})""".format(
            settings.DBLINK_CONN, page_size, offset)

        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = dictfetchall(cursor)

        return rows

    def get(self, request, *args, **kwargs):

        page_size = 20
        page = int(self.request.query_params.get('page', 1))
        offset = (page - 1) * page_size

        rows = self.get_data(page_size, offset)

        has_previous = False
        has_next = False

        if offset > 0:
            has_previous = True

        if len(rows) > page_size:
            has_next = True
            rows = rows[:page_size]

        return Response({
            "results": rows,
            "has_previous": has_previous,
            "has_next": has_next}, status=200)
