FROM praekeltfoundation/django-bootstrap:py2

COPY . /app
RUN pip install -e .

ENV DJANGO_SETTINGS_MODULE "hellomama_registration.settings"
RUN ./manage.py collectstatic --noinput
CMD ["hellomama_registration.wsgi:application"]
