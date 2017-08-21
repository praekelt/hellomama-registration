from django.conf.urls import url, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'reporttasks', views.ReportTaskStatusViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/reports/$', views.ReportsView.as_view(),
        name='generate-reports'),
    url(r'^api/v1/', include(router.urls)),
]
