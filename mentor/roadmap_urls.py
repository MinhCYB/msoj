"""URL routing for Mentor Roadmap v2 Phase 1 read APIs."""
from django.urls import path

from .roadmap_pages import roadmap_markdown_preview
from .roadmap_views import (
    roadmap_detail_view,
    roadmap_list_view,
    roadmap_node_children_view,
    roadmap_node_learn_view,
    roadmap_node_lesson_view,
    roadmap_node_lesson_questions_view,
    roadmap_node_lesson_state_view,
    roadmap_progress_view,
)

urlpatterns = [
    path('roadmap/markdown-preview/', roadmap_markdown_preview, name='roadmap_markdown_preview'),
    path('roadmaps/', roadmap_list_view, name='roadmap_list'),
    path('roadmap/<slug:slug>/', roadmap_detail_view, name='roadmap_detail'),
    path('roadmap/<slug:slug>/nodes/<int:node_id>/children/', roadmap_node_children_view, name='roadmap_node_children'),
    path('roadmap/<slug:slug>/nodes/<int:node_id>/learn/', roadmap_node_learn_view, name='roadmap_node_learn'),
    path('roadmap/<slug:slug>/nodes/<int:node_id>/lessons/<int:lesson_id>/', roadmap_node_lesson_view, name='roadmap_node_lesson'),
    path('roadmap/<slug:slug>/nodes/<int:node_id>/lessons/<int:lesson_id>/questions/', roadmap_node_lesson_questions_view, name='roadmap_node_lesson_questions'),
    path('roadmap/<slug:slug>/nodes/<int:node_id>/lessons/<int:lesson_id>/state/', roadmap_node_lesson_state_view, name='roadmap_node_lesson_state'),
    path('roadmap/<slug:slug>/progress/', roadmap_progress_view, name='roadmap_progress'),
]
