from django.conf.urls import url
from . import views

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/reports/$', views.ReportsView.as_view(),
        name='generate-reports'),
]
