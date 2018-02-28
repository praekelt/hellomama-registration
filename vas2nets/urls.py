from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^api/v1/fetch_voice_data/$',
        views.FetchVoiceDataView.as_view()),
    url(r'^api/v1/sync_welcome_audio/$',
        views.SyncWelcomeAudioView.as_view()),
]
