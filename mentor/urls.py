from django.urls import path

from .review_views import submission_review
from .brainstorm_views import legacy_brainstorm, post_turn, session_state, turn_state


urlpatterns = [
    path('reviews/submissions/<int:submission_id>/', submission_review, name='mentor_submission_review'),
    path('brainstorm/turns/<int:turn_id>/', turn_state, name='mentor_brainstorm_turn'),
    path('brainstorm/<str:problem_code>/turns/', post_turn, name='mentor_brainstorm_post_turn'),
    path('brainstorm/<str:problem_code>/', legacy_brainstorm, name='mentor_brainstorm_send'),
]
