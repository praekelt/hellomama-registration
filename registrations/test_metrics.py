try:
    import mock
except ImportError:
    from unittest import mock

import json
import responses

from datetime import datetime
from django.contrib.auth.models import User
from django.test import TestCase
from django.db.models.signals import post_save

from rest_hooks.models import model_saved

from .metrics import MetricGenerator, send_metric
from .tests import AuthenticatedAPITestCase
from .models import Source, Registration
from hellomama_registration import utils
from changes.models import (
    Change, change_post_save, fire_language_change_metric,
    fire_baby_change_metric, fire_loss_change_metric,
    fire_message_change_metric)


class MetricsGeneratorTests(AuthenticatedAPITestCase):

    def _replace_post_save_hooks_change(self):
        def has_listeners():
            return post_save.has_listeners(Change)
        assert has_listeners(), (
            "Change model has no post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")
        post_save.disconnect(receiver=change_post_save,
                             sender=Change)
        post_save.disconnect(receiver=fire_language_change_metric,
                             sender=Change)
        post_save.disconnect(receiver=fire_baby_change_metric,
                             sender=Change)
        post_save.disconnect(receiver=fire_loss_change_metric,
                             sender=Change)
        post_save.disconnect(receiver=fire_message_change_metric,
                             sender=Change)
        post_save.disconnect(receiver=model_saved,
                             dispatch_uid='instance-saved-hook')
        assert not has_listeners(), (
            "Change model still has post_save listeners. Make sure"
            " helpers cleaned up properly in earlier tests.")

    def _restore_post_save_hooks_change(self):
        post_save.connect(receiver=change_post_save,
                          sender=Change)
        post_save.connect(receiver=fire_language_change_metric,
                          sender=Change)
        post_save.connect(receiver=fire_baby_change_metric,
                          sender=Change)
        post_save.connect(receiver=fire_loss_change_metric,
                          sender=Change)
        post_save.connect(receiver=fire_message_change_metric,
                          sender=Change)
        post_save.connect(receiver=model_saved,
                          dispatch_uid='instance-saved-hook')

    def setUp(self):
        super(MetricsGeneratorTests, self).setUp()
        self._replace_post_save_hooks_change()

    def tearDown(self):
        super(MetricsGeneratorTests, self).tearDown()
        self._restore_post_save_hooks_change()

    def test_generate_metric(self):
        """
        The generate_metric function should call the correct function with the
        correct start and end datetimes.
        """
        generator = MetricGenerator()
        generator.foo_bar = mock.MagicMock()
        start = datetime(2016, 10, 26)
        end = datetime(2016, 10, 26)
        generator.generate_metric('foo.bar', start, end)

        generator.foo_bar.assert_called_once_with(start, end)

    def create_registration_on(self, timestamp, source, **kwargs):
        r = Registration.objects.create(
            mother_id='motherid', source=source, data=kwargs)
        r.created_at = timestamp
        r.save()
        return r

    def create_lang_change_on(self, timestamp, source, **kwargs):
        return self.create_change_on(timestamp, source, 'change_language')

    def create_baby_change_on(self, timestamp, source, **kwargs):
        return self.create_change_on(timestamp, source, 'change_baby')

    def create_loss_change_on(self, timestamp, source, **kwargs):
        return self.create_change_on(timestamp, source, 'change_loss')

    def create_messaging_change_on(self, timestamp, source, **kwargs):
        return self.create_change_on(timestamp, source, 'change_messaging')

    def create_change_on(self, timestamp, source, action, **kwargs):
        data = {
            "mother_id": "846877e6-afaa-43de-acb1-09f61ad4de99",
            "action": action,
            "data": {"test_adminuser_change": "test_adminuser_changed"},
            "source": source
        }
        c = Change.objects.create(**data)
        c.created_at = timestamp
        c.save()
        return c

    def test_registrations_created_sum(self):
        """
        Should return the amount of registrations in the given timeframe.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(datetime(2016, 10, 14), source)  # Before
        self.create_registration_on(datetime(2016, 10, 15), source)  # On
        self.create_registration_on(datetime(2016, 10, 20), source)  # In
        self.create_registration_on(datetime(2016, 10, 25), source)  # On
        self.create_registration_on(datetime(2016, 10, 26), source)  # After

        reg_count = MetricGenerator().registrations_created_sum(start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_created_total_last(self):
        """
        Should return the total amount of registrations at the 'end' point in
        time.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(datetime(2016, 10, 14), source)  # Before
        self.create_registration_on(datetime(2016, 10, 25), source)  # On
        self.create_registration_on(datetime(2016, 10, 26), source)  # After

        reg_count = MetricGenerator().registrations_created_total_last(
            start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_unique_operators_sum(self):
        """
        Should return the amount of new operators in the given timeframe.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        # Registration before should exclude 1
        self.create_registration_on(
            datetime(2016, 10, 14), source, operator_id='1')
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='1')
        # Two registrations during should exclude 2
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='2')
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='2')
        # Registration after shouldn't exclude 3
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='3')
        self.create_registration_on(
            datetime(2016, 10, 26), source, operator_id='3')

        reg_count = MetricGenerator().registrations_unique_operators_sum(
            start, end)
        self.assertEqual(reg_count, 1)

    def test_registrations_msg_type_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific message type.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, msg_type='type1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source, msg_type='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, msg_type='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, msg_type='type1')  # After

        reg_count = MetricGenerator().registrations_msg_type_sum(
            'type1', start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_msg_type_total_last(self):
        """
        Should return the amount of registrations before the end of the
        timeframe for the given message type.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, msg_type='type1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_type='type2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, msg_type='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, msg_type='type1')  # After

        reg_count = MetricGenerator().registrations_msg_type_total_last(
            'type1', start, end)
        self.assertEqual(reg_count, 3)

    def test_registrations_receiver_type_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific receiver type.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, msg_receiver='type1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source, msg_receiver='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_receiver='type1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_receiver='type2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, msg_receiver='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, msg_receiver='type1')  # After

        reg_count = MetricGenerator().registrations_receiver_type_sum(
            'type1', start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_receiver_type_total_last(self):
        """
        Should return the amount of registrations before the end of the
        timeframe for the given receiver type.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, msg_receiver='type1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_receiver='type1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, msg_receiver='type2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, msg_receiver='type1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, msg_receiver='type1')  # After

        reg_count = MetricGenerator().registrations_receiver_type_total_last(
            'type1', start, end)
        self.assertEqual(reg_count, 3)

    def test_registrations_language_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific language

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, language='eng')  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source, language='eng')  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source, language='eng')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, language='hau')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, language='eng')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, language='eng')  # After

        reg_count = MetricGenerator().registrations_language_sum(
            'eng', start, end)
        self.assertEqual(reg_count, 2)

    def test_registrations_language_total_last(self):
        """
        Should return the amount of registrations before the end of the
        timeframe for the given language
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, language='eng')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, language='eng')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, language='hau')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, language='eng')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, language='eng')  # After

        reg_count = MetricGenerator().registrations_language_total_last(
            'eng', start, end)
        self.assertEqual(reg_count, 3)

    def identity_search_callback(self, request):
        headers = {'Content-Type': "application/json"}
        resp = {
            "results": [
                {
                    "id": "id1",
                    "details": {"state": "state2"},
                },
            ]
        }
        return (200, headers, json.dumps(resp))

    @responses.activate
    def test_registrations_state_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific state.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        url = 'http://localhost:8001/api/v1/identities/search/?' \
              'details__state=state1'
        responses.add_callback(
            responses.GET, url, callback=self.identity_search_callback,
            content_type="application/json", match_querystring=True)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, operator_id='id1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source, operator_id='id1')  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, operator_id='id1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, operator_id='id1')  # After

        reg_count = MetricGenerator().registrations_state_sum(
            'state1', start, end)
        self.assertEqual(reg_count, 2)

    @responses.activate
    def test_registrations_state_total_last(self):
        """
        Should return the amount of registrations until the end of the
        timeframe.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        url = 'http://localhost:8001/api/v1/identities/search/?' \
              'details__state=state1'
        responses.add_callback(
            responses.GET, url, callback=self.identity_search_callback,
            content_type="application/json", match_querystring=True)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, operator_id='id1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, operator_id='id1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, operator_id='id1')  # After

        reg_count = MetricGenerator().registrations_state_total_last(
            'state1', start, end)
        self.assertEqual(reg_count, 3)

    @responses.activate
    def test_registrations_role_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific role.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        url = 'http://localhost:8001/api/v1/identities/search/?' \
              'details__role=role1'
        responses.add_callback(
            responses.GET, url, callback=self.identity_search_callback,
            content_type="application/json", match_querystring=True)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, operator_id='id1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source, operator_id='id1')  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, operator_id='id1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, operator_id='id1')  # After

        reg_count = MetricGenerator().registrations_role_sum(
            'role1', start, end)
        self.assertEqual(reg_count, 2)

    @responses.activate
    def test_registrations_role_total_last(self):
        """
        Should return the amount of registrations up to the end of the
        timeframe.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        url = 'http://localhost:8001/api/v1/identities/search/?' \
              'details__role=role1'
        responses.add_callback(
            responses.GET, url, callback=self.identity_search_callback,
            content_type="application/json", match_querystring=True)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source, operator_id='id1')  # Before
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id1')  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source, operator_id='id2')  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source, operator_id='id1')  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source, operator_id='id1')  # After

        reg_count = MetricGenerator().registrations_role_total_last(
            'role1', start, end)
        self.assertEqual(reg_count, 3)

    def test_registrations_source_sum(self):
        """
        Should return the amount of registrations in the given timeframe for
        a specific source.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """
        user1 = User.objects.create(username='user1')
        user2 = User.objects.create(username='user2')
        source1 = Source.objects.create(
            name='TestSource1', authority='hw_full', user=user1)
        source2 = Source.objects.create(
            name='TestSource2', authority='hw_full', user=user2)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_registration_on(
            datetime(2016, 10, 14), source1)  # Before
        self.create_registration_on(
            datetime(2016, 10, 15), source1)  # On
        self.create_registration_on(
            datetime(2016, 10, 20), source1)  # During
        self.create_registration_on(
            datetime(2016, 10, 20), source2)  # Wrong type
        self.create_registration_on(
            datetime(2016, 10, 25), source1)  # On
        self.create_registration_on(
            datetime(2016, 10, 26), source1)  # After

        reg_count = MetricGenerator().registrations_source_sum(
            'user1', start, end)
        self.assertEqual(reg_count, 2)

    def test_change_language_sum(self):
        """
        Should return the amount of language changes in the given timeframe.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """

        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_lang_change_on(datetime(2016, 10, 14), source)  # Before
        self.create_lang_change_on(datetime(2016, 10, 15), source)  # On
        self.create_lang_change_on(datetime(2016, 10, 20), source)  # In
        self.create_lang_change_on(datetime(2016, 10, 25), source)  # On
        self.create_lang_change_on(datetime(2016, 10, 26), source)  # After

        # Make sure other change type is not added
        self.create_messaging_change_on(datetime(2016, 10, 20), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_language_sum(start, end)
        self.assertEqual(change_count, 2)

    def test_change_language_total_last(self):
        """
        Should return the total amount of language changes at the 'end' point
        in time.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_lang_change_on(datetime(2016, 10, 14), source)  # Before
        self.create_lang_change_on(datetime(2016, 10, 25), source)  # On
        self.create_lang_change_on(datetime(2016, 10, 26), source)  # After

        # Make sure other change type is not added
        self.create_messaging_change_on(datetime(2016, 10, 24), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_language_total_last(start, end)
        self.assertEqual(change_count, 2)

    def test_change_baby_sum(self):
        """
        Should return the amount of pregnancy to baby changes in the given
        timeframe.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """

        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_baby_change_on(datetime(2016, 10, 14), source)  # Before
        self.create_baby_change_on(datetime(2016, 10, 15), source)  # On
        self.create_baby_change_on(datetime(2016, 10, 20), source)  # In
        self.create_baby_change_on(datetime(2016, 10, 25), source)  # On
        self.create_baby_change_on(datetime(2016, 10, 26), source)  # After

        # Make sure other change type is not added
        self.create_messaging_change_on(datetime(2016, 10, 20), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_pregnant_to_baby_sum(start, end)
        self.assertEqual(change_count, 2)

    def test_change_baby_total_last(self):
        """
        Should return the total amount of pregnancy to baby changes at the
        'end' point in time.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_baby_change_on(datetime(2016, 10, 14), source)  # Before
        self.create_baby_change_on(datetime(2016, 10, 25), source)  # On
        self.create_baby_change_on(datetime(2016, 10, 26), source)  # After

        # Make sure other change type is not added
        self.create_messaging_change_on(datetime(2016, 10, 24), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_pregnant_to_baby_total_last(start, end)
        self.assertEqual(change_count, 2)

    def test_change_loss_sum(self):
        """
        Should return the amount of pregnancy to loss changes in the given
        timeframe.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """

        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_loss_change_on(datetime(2016, 10, 14), source)  # Before
        self.create_loss_change_on(datetime(2016, 10, 15), source)  # On
        self.create_loss_change_on(datetime(2016, 10, 20), source)  # In
        self.create_loss_change_on(datetime(2016, 10, 25), source)  # On
        self.create_loss_change_on(datetime(2016, 10, 26), source)  # After

        # Make sure other change type is not added
        self.create_messaging_change_on(datetime(2016, 10, 20), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_pregnant_to_loss_sum(start, end)
        self.assertEqual(change_count, 2)

    def test_change_loss_total_last(self):
        """
        Should return the total amount of pregnancy to loss changes at the
        'end' point in time.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_loss_change_on(datetime(2016, 10, 14), source)  # Before
        self.create_loss_change_on(datetime(2016, 10, 25), source)  # On
        self.create_loss_change_on(datetime(2016, 10, 26), source)  # After

        # Make sure other change type is not added
        self.create_messaging_change_on(datetime(2016, 10, 24), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_pregnant_to_loss_total_last(start, end)
        self.assertEqual(change_count, 2)

    def test_change_message_sum(self):
        """
        Should return the amount of messaging changes in the given
        timeframe.

        Only one of the borders of the timeframe should be included, to avoid
        duplication.
        """

        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_messaging_change_on(datetime(2016, 10, 14), source)  # Bef
        self.create_messaging_change_on(datetime(2016, 10, 15), source)  # On
        self.create_messaging_change_on(datetime(2016, 10, 20), source)  # In
        self.create_messaging_change_on(datetime(2016, 10, 25), source)  # On
        self.create_messaging_change_on(datetime(2016, 10, 26), source)  # Aft

        # Make sure other change type is not added
        self.create_baby_change_on(datetime(2016, 10, 20), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_messaging_sum(start, end)
        self.assertEqual(change_count, 2)

    def test_change_message_total_last(self):
        """
        Should return the total amount of messaging changes at the
        'end' point in time.
        """
        user = User.objects.create(username='user1')
        source = Source.objects.create(
            name='TestSource', authority='hw_full', user=user)

        start = datetime(2016, 10, 15)
        end = datetime(2016, 10, 25)

        self.create_messaging_change_on(datetime(2016, 10, 14), source)  # Befo
        self.create_messaging_change_on(datetime(2016, 10, 25), source)  # On
        self.create_messaging_change_on(datetime(2016, 10, 26), source)  # Aft

        # Make sure other change type is not added
        self.create_baby_change_on(datetime(2016, 10, 24), source)  # In

        change_count = MetricGenerator()\
            .registrations_change_messaging_total_last(start, end)
        self.assertEqual(change_count, 2)

    def test_that_all_metrics_are_present(self):
        """
        We need to make sure that we have a function for each of the metrics.
        """
        user = User.objects.create(username='user1')
        Source.objects.create(
            name='TestSource', authority='hw_full', user=user)
        for metric in utils.get_available_metrics():
            self.assertTrue(callable(getattr(
                MetricGenerator(), metric.replace('.', '_'))))


class SendMetricTests(TestCase):
    def test_send_metric(self):
        """
        The send_metric function should publish the correct message to the
        correct exchange, using the provided channel.
        """
        channel = mock.MagicMock()
        send_metric(
            channel, '', 'foo.bar', 17, datetime.utcfromtimestamp(1317))

        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')

    def test_send_metric_prefix(self):
        """
        The send_metric function should add the correct prefix tot he metric
        name that it sends.
        """
        channel = mock.MagicMock()
        send_metric(
            channel, 'test.prefix', 'foo.bar', 17,
            datetime.utcfromtimestamp(1317))

        [exchange, routing_key, message, properties], _ = (
            channel.basic_publish.call_args)
        self.assertEqual(exchange, 'graphite')
        self.assertEqual(routing_key, 'test.prefix.foo.bar')
        self.assertEqual(message, '17.0 1317')
        self.assertEquals(properties.delivery_mode, 2)
        self.assertEquals(properties.content_type, 'text/plain')
