FROM praekeltfoundation/django-bootstrap:py2

COPY setup.py /app

RUN pip install -e .

COPY . /app

ENV DJANGO_SETTINGS_MODULE "hellomama_registration.settings"
RUN ./manage.py collectstatic --noinput
CMD ["hellomama_registration.wsgi:application"]
