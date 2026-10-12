"""Staff-only writes; every admin entry point uses the same authorization."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from judge.models import Problem
from .roadmap_models import (LearningTopic, Publication, Roadmap, RoadmapNode,
                             TopicLesson, lock_roadmap_forest)


def require_write(user, obj, action):
    permission = f'mentor.{action}_{obj._meta.model_name}'
    if not user.is_active or not user.is_staff or not user.has_perm(permission):
        raise PermissionDenied


def require_publication(user, obj):
    if not hasattr(obj, 'status'):
        return
    old_status = type(obj).objects.filter(pk=obj.pk).values_list('status', flat=True).first() if obj.pk else None
    if obj.status != old_status and Publication.PUBLISHED in (obj.status, old_status):
        if not user.has_perm('mentor.publish_roadmap'):
            raise PermissionDenied


@transaction.atomic
def save_node(user, node):
    lock_roadmap_forest()
    require_write(user, node, 'change' if node.pk else 'add')
    require_publication(user, node)
    node.save()
    return node


def create_node(user, **fields):
    return save_node(user, RoadmapNode(**fields))


@transaction.atomic
def move_node(user, node_id, parent_id, position=None):
    lock_roadmap_forest()
    node = RoadmapNode.objects.get(pk=node_id)
    node.parent_id = parent_id
    if position is not None:
        node.position = position
    return save_node(user, node)


@transaction.atomic
def reorder_nodes(user, roadmap_id, parent_id, node_ids):
    lock_roadmap_forest()
    roadmap = Roadmap.objects.get(pk=roadmap_id)
    require_write(user, RoadmapNode(), 'change')
    if parent_id and not RoadmapNode.objects.filter(pk=parent_id, roadmap=roadmap).exists():
        raise ValidationError('Parent must belong to the roadmap.')
    siblings = list(RoadmapNode.objects.filter(roadmap=roadmap, parent_id=parent_id))
    by_id = {node.pk: node for node in siblings}
    if len(node_ids) != len(set(node_ids)) or set(node_ids) != set(by_id):
        raise ValidationError('Reorder must contain every sibling exactly once.')
    for position, pk in enumerate(node_ids):
        node = by_id[pk]
        node.position = position
        node.save()
    return list(RoadmapNode.objects.filter(pk__in=node_ids).order_by('position', 'pk'))


@transaction.atomic
def delete_node(user, node_id):
    lock_roadmap_forest()
    node = RoadmapNode.objects.get(pk=node_id)
    require_write(user, node, 'delete')
    return node.delete()


@transaction.atomic
def save_content(user, obj):
    if not isinstance(obj, (Roadmap, LearningTopic, TopicLesson)):
        raise TypeError('Expected roadmap, topic or lesson.')
    # Lock before reading the old publication status, to prevent concurrent
    # unprivileged writes from undoing a publish operation.
    lock_roadmap_forest()
    if isinstance(obj, TopicLesson):
        LearningTopic.objects.select_for_update().get(pk=obj.topic_id)
    elif isinstance(obj, LearningTopic) and obj.pk:
        LearningTopic.objects.select_for_update().get(pk=obj.pk)
    require_write(user, obj, 'change' if obj.pk else 'add')
    require_publication(user, obj)
    obj.save()
    return obj


def allowed_problem(user, problem_id):
    problem = Problem.get_visible_problems(user).filter(pk=problem_id).first()
    if problem is None or not problem.is_accessible_by(user):
        raise ValidationError({'problem': 'Problem is not accessible.'})
    return problem


@transaction.atomic
def save_problem_link(user, link):
    lock_roadmap_forest()
    require_write(user, link, 'change' if link.pk else 'add')
    # Reassigning a link also requires edit permission for both placements.
    require_write(user, RoadmapNode(), 'change')
    link.problem = allowed_problem(user, link.problem_id)
    link.full_clean()
    link.save()
    return link


@transaction.atomic
def delete_problem_link(user, link):
    lock_roadmap_forest()
    require_write(user, link, 'delete')
    require_write(user, RoadmapNode(), 'change')
    return link.delete()
