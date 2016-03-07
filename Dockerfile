FROM praekeltfoundation/django-bootstrap
ENV DJANGO_SETTINGS_MODULE "hellomama_registration.settings"
RUN django-admin collectstatic --noinput
CMD ["hellomama_registration.wsgi:application"]
