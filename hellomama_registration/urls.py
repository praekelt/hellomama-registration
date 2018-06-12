import os
from django.conf.urls import include, url
from django.contrib import admin
from registrations import views
from rest_framework.authtoken.views import obtain_auth_token
import rest_framework_docs.urls

admin.site.site_header = os.environ.get('REGISTRATIONS_TITLE',
                                        'HelloMama Registration Admin')


urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api/auth/',
        include('rest_framework.urls', namespace='rest_framework')),
    url(r'^api/token-auth/', obtain_auth_token),
    url(r'^api/metrics/', views.MetricsView.as_view()),
    url(r'^api/health/', views.HealthcheckView.as_view()),
    url(r'^docs/', include(rest_framework_docs.urls)),
    url(r'^', include('registrations.urls')),
    url(r'^', include('changes.urls')),
    url(r'^', include('uniqueids.urls')),
    url(r'^', include('reports.urls')),
    url(r'^', include('vas2nets.urls')),
]
