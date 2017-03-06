# NOTE: Python 3 compatibility
try:
    from urlparse import urlparse, parse_qs
except ImportError:
    from urllib.parse import urlparse, parse_qs


def parse_cursor_params(cursor):
    parse_result = urlparse(cursor)
    params = parse_qs(parse_result.query)
    return dict([(key, value[0]) for key, value in params.items()])
