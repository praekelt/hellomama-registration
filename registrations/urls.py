from django.conf.urls import url, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'user', views.UserViewSet)
router.register(r'group', views.GroupViewSet)
router.register(r'source', views.SourceViewSet)
router.register(r'webhook', views.HookViewSet)
router.register(r'registrations', views.RegistrationGetViewSet)


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browseable API.
urlpatterns = [
    url(r'^api/v1/registration/(?P<id>.+)/',
        views.RegistrationPostPatch.as_view()),
    url(r'^api/v1/registration/', views.RegistrationPostPatch.as_view()),
    url(r'^api/v1/user/token/$', views.UserView.as_view(),
        name='create-user-token'),
    url(r'^api/v1/', include(router.urls)),
    url(r'^api/v1/extregistration/$',
        views.ThirdPartyRegistrationView.as_view()),
    url(r'^api/v1/addregistration/$',
        views.AddRegistrationView.as_view()),
    url(r'^api/v1/personnelcode/$',
        views.PersonnelCodeView.as_view()),
    url(r'^api/v1/send_public_notifications/$',
        views.SendPublicRegistrationNotificationView.as_view()),
    url(r'^api/v1/missedcall_notification/',
        views.MissedCallNotification.as_view()),
    url(r'^api/v1/user_details/$',
        views.UserDetailList.as_view()),
]
