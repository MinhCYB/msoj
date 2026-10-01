from django.urls import path

from . import views
from .review_views import submission_review


urlpatterns = [
    path('reviews/submissions/<int:submission_id>/', submission_review, name='mentor_submission_review'),
    path('brainstorm/<str:problem_code>/', views.brainstorm_send, name='mentor_brainstorm_send'),
]
