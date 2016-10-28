from datetime import datetime, timedelta
from django.test import TestCase

from registrations.graphite import GraphiteRetention, RetentionScheme


class TestGraphiteRetention(TestCase):
    def test_multipliers(self):
        """
        When using s, m, h, etc, we should be multiplying by the correct
        value to convert the number and letter combination to total seconds.
        """
        ret1 = GraphiteRetention('17s:2m')
        self.assertEqual(ret1.precision, timedelta(seconds=17))
        self.assertEqual(ret1.duration, timedelta(minutes=2))
        ret2 = GraphiteRetention('7h:12d')
        self.assertEqual(ret2.precision, timedelta(hours=7))
        self.assertEqual(ret2.duration, timedelta(days=12))
        ret3 = GraphiteRetention('3w:1y')
        self.assertEqual(ret3.precision, timedelta(weeks=3))
        # Graphite considers a year to have 365 days
        self.assertEqual(ret3.duration, timedelta(days=365))

    def test_get_buckets_clean_division(self):
        """
        The get_buckets function should return correct buckets for the given
        retention scheme when the resolution fits cleanly in the duration.
        """
        ret = GraphiteRetention('20s:1m')
        now = datetime(2016, 10, 26, 12, 00, 00)
        buckets = list(ret.get_buckets(now=now))
        buckets.sort(key=lambda d: d[0])

        expected = [
            (
                datetime(2016, 10, 26, 11, 59, 00),
                datetime(2016, 10, 26, 11, 59, 20)
            ),
            (
                datetime(2016, 10, 26, 11, 59, 20),
                datetime(2016, 10, 26, 11, 59, 40)
            ),
            (
                datetime(2016, 10, 26, 11, 59, 40),
                datetime(2016, 10, 26, 12, 00, 00)
            ),
        ]
        expected.sort(key=lambda d: d[0])

        self.assertEqual(buckets, expected)

    def test_get_buckets_remainder_division(self):
        """
        The get_buckets function should return correct buckets for the given
        retention scheme when the resolution doesn't fit cleanly in the
        duration.
        """
        ret = GraphiteRetention('25s:1m')
        now = datetime(2016, 10, 26, 12, 00, 00)
        buckets = list(ret.get_buckets(now=now))
        buckets.sort(key=lambda d: d[0])

        expected = [
            (
                datetime(2016, 10, 26, 11, 59, 00),
                datetime(2016, 10, 26, 11, 59, 25)
            ),
            (
                datetime(2016, 10, 26, 11, 59, 25),
                datetime(2016, 10, 26, 11, 59, 50)
            ),
            (
                datetime(2016, 10, 26, 11, 59, 50),
                datetime(2016, 10, 26, 12, 00, 00)
            ),
        ]
        expected.sort(key=lambda d: d[0])

        self.assertEqual(buckets, expected)

    def test_get_buckets_finish_parameter(self):
        """
        The get_buckets function should return correct buckets for the given
        retention scheme cut off by the finish parameter.
        """
        ret = GraphiteRetention('20s:1m')
        now = datetime(2016, 10, 26, 12, 00, 00)
        finish = datetime(2016, 10, 26, 11, 59, 32)
        buckets = list(ret.get_buckets(now=now, finish=finish))
        buckets.sort(key=lambda d: d[0])

        expected = [
            (
                datetime(2016, 10, 26, 11, 59, 00),
                datetime(2016, 10, 26, 11, 59, 20)
            ),
            (
                datetime(2016, 10, 26, 11, 59, 20),
                datetime(2016, 10, 26, 11, 59, 32)
            ),
        ]
        expected.sort(key=lambda d: d[0])

        self.assertEqual(buckets, expected)


class TestGraphiteRetentions(TestCase):
    def test_get_buckets(self):
        """
        The get_buckets function should return all the buckets for the given
        retentions, with no overlap.
        """
        ret = RetentionScheme('30s:1m,1m:3m')
        now = datetime(2016, 10, 26, 12, 00, 00)
        buckets = list(ret.get_buckets(now=now))
        buckets.sort(key=lambda d: d[0])

        expected = [
            # 1 minute accuracy
            (
                datetime(2016, 10, 26, 11, 57, 00),
                datetime(2016, 10, 26, 11, 58, 00)
            ),
            (
                datetime(2016, 10, 26, 11, 58, 00),
                datetime(2016, 10, 26, 11, 59, 00)
            ),
            # 30 second accuracy
            (
                datetime(2016, 10, 26, 11, 59, 00),
                datetime(2016, 10, 26, 11, 59, 30)
            ),
            (
                datetime(2016, 10, 26, 11, 59, 30),
                datetime(2016, 10, 26, 12, 00, 00)
            ),
        ]
        expected.sort(key=lambda d: d[0])

        self.assertEqual(buckets, expected)

    def test_get_buckets_non_exact_boundaries(self):
        """
        The get_buckets function should return all the buckets for the given
        retentions, with no overlap, even if the boundaries don't match up.
        """
        ret = RetentionScheme('45s:90s,1m:3m')
        now = datetime(2016, 10, 26, 12, 00, 00)
        buckets = list(ret.get_buckets(now=now))
        buckets.sort(key=lambda d: d[0])

        expected = [
            # 1 minute accuracy
            (
                datetime(2016, 10, 26, 11, 57, 00),
                datetime(2016, 10, 26, 11, 58, 00)
            ),
            (
                datetime(2016, 10, 26, 11, 58, 00),
                datetime(2016, 10, 26, 11, 58, 30)
            ),
            # 45 second accuracy
            (
                datetime(2016, 10, 26, 11, 58, 30),
                datetime(2016, 10, 26, 11, 59, 15)
            ),
            (
                datetime(2016, 10, 26, 11, 59, 15),
                datetime(2016, 10, 26, 12, 00, 00)
            ),
        ]
        expected.sort(key=lambda d: d[0])

        self.assertEqual(buckets, expected)
