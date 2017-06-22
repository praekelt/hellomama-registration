from django.conf.urls import url, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'changes', views.ChangeGetViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/', include(router.urls)),
    url(r'^api/v1/change/', views.ChangePost.as_view()),
    url(r'^api/v1/optout/', views.ReceiveIdentityStoreOptout.as_view(),
        name="identity_store_optout"),
    url(r'^api/v1/optout_admin/',
        views.ReceiveAdminOptout.as_view(),
        name="optout_admin"),
    url(r'^api/v1/change_admin/',
        views.ReceiveAdminChange.as_view(),
        name="change_admin")
]
