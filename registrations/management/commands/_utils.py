from django.core.validators import URLValidator


def validate_and_return_url(url):
    """
    Validates a URL provided, relies on Django's URLValidator to raise an
    exception if invalid.

    Useful to use as an argument for argparse's `type` parameter to validate
    URLs provided via the command line.
    """
    URLValidator()(url)
    return url
