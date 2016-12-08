FROM praekeltfoundation/django-bootstrap:onbuild
ENV DJANGO_SETTINGS_MODULE "hellomama_registration.settings"
RUN ./manage.py collectstatic --noinput
ENV APP_MODULE "hellomama_registration.wsgi:application"
