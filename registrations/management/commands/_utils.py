from django.core.validators import URLValidator


def validate_and_return_url(url):
    URLValidator()(url)
    return url
