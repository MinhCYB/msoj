from django.urls import path

from . import views


urlpatterns = [
    path('brainstorm/<str:problem_code>/', views.brainstorm_send, name='mentor_brainstorm_send'),
]
