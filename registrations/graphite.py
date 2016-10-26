import re

from datetime import datetime, timedelta


class GraphiteRetention(object):
    """
    Represents one graphite retention. Provides utilities to get time buckets.
    """
    RETENTION_RE = re.compile(r'^(\d+)([a-z]+)$')
    MULTIPLIERS = {
        's': 1,
        'm': 60,
        'h': 60 * 60,
        'd': 60 * 60 * 24,
        'w': 60 * 60 * 24 * 7,
        'y': 60 * 60 * 24 * 365,
    }

    def __init__(self, retention):
        precision, duration = retention.split(':')
        self.precision = self._str_to_timedelta(precision)
        self.duration = self._str_to_timedelta(duration)

    def _str_to_timedelta(self, retention):
        match = self.RETENTION_RE.match(retention)
        seconds = int(match.group(1)) * self.MULTIPLIERS[match.group(2)]
        return timedelta(seconds=seconds)

    def get_buckets(self, now=None, finish=None):
        """
        Returns an iterator of tuples (start, end) that define the time
        buckets that this retention scheme covers.

        kwargs:
            now: timestamp of current time. Defaults to current time.
            finish: timestamp of when to stop buckets. Defaults to now.
        """
        if now is None:
            now = datetime.utcnow()
        if finish is None:
            finish = now
        start = now - self.duration

        while start < finish:
            end = start + self.precision
            if end > finish:
                end = finish
            yield (start, end)
            start = end


class GraphiteRetentions(object):
    """
    Represents multiple graphite retentions. Provides utilities to get time
    buckets across all retentions.
    """
    def __init__(self, retentions):
        self.retentions = [GraphiteRetention(r) for r in retentions.split(',')]

    def get_buckets(self, now=None):
        """
        Returns an iterator of tuples (start, end) that define the time
        buckets that all the retention schemes cover.

        kwargs:
            now: timestamp of current time. Defaults to current time.
        """
        if now is None:
            now = datetime.utcnow()
        finish = now

        for r in self.retentions:
            beginning = now
            for start, end in r.get_buckets(now=now, finish=finish):
                beginning = min(beginning, start)
                yield (start, end)
            # The next retention should end where this one started
            finish = beginning
