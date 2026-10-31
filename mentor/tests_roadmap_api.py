from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from judge.models import Organization, Submission
from .models import LearningTopic, NodeProblem, Roadmap, TopicLesson
from .roadmap_models import Publication, Visibility
from .roadmap_services import save_node
from .tests_roadmap import RoadmapFixture


class RoadmapAPITests(RoadmapFixture, TestCase):
    def progress(self, node):
        self.client.force_login(self.learner)
        return self.client.get(reverse('roadmap_progress', args=[self.roadmap.slug]), {'focus': node.pk})

    def test_distinct_progress_current_verdict_and_hidden_denominator(self):
        root = self.node('root')
        a, b = self.node('child-a', parent=root), self.node('child-b', parent=root)
        pa, pb, pc = self.problem('progress_a'), self.problem('progress_b'), self.problem('progress_c')
        hidden = self.problem('progress_private', is_public=False)
        deleted = self.problem('progress_deleted', deleted_at=timezone.now())
        archived = self.problem('progress_archive', archived_at=timezone.now())
        for node, problems in ((root, [pa]), (a, [pa, pb]), (b, [pb, pc, archived])):
            for problem in problems:
                self.link(node, problem)
        # Legacy or another privileged writer may associate restricted problems.
        NodeProblem.objects.create(node=b, problem=hidden)
        NodeProblem.objects.create(node=b, problem=deleted)
        sa = self.submission(pa, points=0, is_pretested=True)
        self.submission(pa, 'WA')
        self.submission(pb)
        self.submission(pc, 'PAC')
        self.submission(hidden)
        self.submission(deleted)
        result = self.progress(root)
        self.assertEqual(result.status_code, 200)
        data = result.json()
        # Contract checked against explicitly labelled direct/subtree results.
        from .roadmap_selectors import RoadmapSnapshot
        snapshot = RoadmapSnapshot(self.learner, self.roadmap)
        self.assertEqual(snapshot.progress(root, 'direct')['solved'], 1)
        self.assertEqual(snapshot.progress(root, 'direct')['total'], 1)
        self.assertEqual(snapshot.progress(root, 'subtree')['solved'], 2)
        self.assertEqual(snapshot.progress(root, 'subtree')['total'], 4)
        Submission.objects.filter(pk=sa.pk).update(status='QU', result=None)
        refreshed = RoadmapSnapshot(self.learner, self.roadmap)
        self.assertEqual(refreshed.progress(root, 'subtree')['solved'], 1)
        Submission.objects.filter(pk=sa.pk).update(status='D', result='WA')
        self.assertEqual(RoadmapSnapshot(self.learner, self.roadmap).progress(root, 'direct')['solved'], 0)
        self.assertNotIn(hidden.code, str(data))
        self.assertNotIn(deleted.code, str(data))
        with self.assertRaises(ValidationError):
            NodeProblem(node=a, problem=pa).full_clean()

    def test_ancestor_draft_topic_draft_scope_and_lesson_idor(self):
        root = self.node('root')
        child = self.node('child', parent=root)
        lesson = TopicLesson.objects.create(topic=self.topic, title='Lesson', slug='lesson', body='Public theory',
                                            status=Publication.PUBLISHED)
        unrelated = LearningTopic.objects.create(name='Unrelated', slug='unrelated', introduction='Private body')
        wrong = TopicLesson.objects.create(topic=unrelated, title='Secret', slug='secret', body='Secret theory',
                                           status=Publication.PUBLISHED)
        url = reverse('roadmap_node_lesson', args=[self.roadmap.slug, child.pk, lesson.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        denied = self.client.get(reverse('roadmap_node_lesson', args=[self.roadmap.slug, child.pk, wrong.pk]))
        self.assertEqual(denied.status_code, 404)
        self.assertNotIn('Secret theory', denied.content.decode())
        self.topic.status = Publication.DRAFT
        self.topic.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.link(child, self.problem('draft_topic_exercise'))
        learn_resp = self.client.get(reverse('roadmap_node_learn', args=[self.roadmap.slug, child.pk]))
        self.assertEqual(learn_resp.status_code, 200)
        learn_data = learn_resp.json()
        self.assertIsNone(learn_data['topic'])
        self.assertEqual(learn_data['lessons'], [])
        self.assertEqual(len(learn_data['problems']), 1)
        self.assertEqual(learn_data['problems'][0]['code'], 'draft_topic_exercise')
        root.status = Publication.DRAFT
        save_node(self.staff, root)
        self.assertEqual(self.client.get(reverse('roadmap_node_children', args=[self.roadmap.slug, child.pk])).status_code,
                         404)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 404)  # no implicit staff learner preview
        org = Organization.objects.create(slug='api_org', name='API org', short_name='API', about='')
        scoped = Roadmap.objects.create(title='Scoped', slug='scoped', visibility=Visibility.ORGANIZATION,
                                        organization=org, status=Publication.PUBLISHED)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('roadmap_detail', args=[scoped.slug])).status_code, 404)
        self.learner_profile.organizations.add(org)
        self.client.force_login(self.learner)
        self.assertEqual(self.client.get(reverse('roadmap_detail', args=[scoped.slug])).status_code, 200)
        self.learner_profile.organizations.remove(org)
        self.assertEqual(self.client.get(reverse('roadmap_detail', args=[scoped.slug])).status_code, 404)

    def test_shared_topics_node_exercises_and_guest_progress(self):
        a, b = self.node('a'), self.node('b')
        pa, pb = self.problem('shared_a'), self.problem('shared_b')
        self.link(a, pa)
        self.link(b, pb)
        first = self.client.get(reverse('roadmap_node_learn', args=[self.roadmap.slug, a.pk]))
        second = self.client.get(reverse('roadmap_node_learn', args=[self.roadmap.slug, b.pk]))
        self.assertEqual(first.status_code, 200)
        self.assertIn(pa.code, first.content.decode())
        self.assertNotIn(pb.code, first.content.decode())
        self.assertIn(pb.code, second.content.decode())
        from .roadmap_selectors import RoadmapSnapshot
        snapshot = RoadmapSnapshot(AnonymousUser(), self.roadmap)
        self.assertEqual(snapshot.progress(a, 'direct'),
                         {'state': 'anonymous', 'scope': 'direct', 'solved': None, 'total': 1})

    def test_child_cursor_is_scoped_and_stale_and_query_cost_is_bounded(self):
        root, outside = self.node('root'), self.node('outside')
        children = [self.node(f'child-{i}', parent=root, position=i) for i in range(4)]
        response = self.client.get(reverse('roadmap_node_children', args=[self.roadmap.slug, root.pk]), {'limit': 2})
        self.assertEqual(response.status_code, 200)
        cursor = response.json()['next_cursor']
        self.assertTrue(cursor)
        next_page = self.client.get(reverse('roadmap_node_children', args=[self.roadmap.slug, root.pk]),
                                    {'cursor': cursor, 'limit': 2})
        self.assertEqual([n['id'] for n in next_page.json()['items']], [n.pk for n in children[2:]])
        wrong = self.client.get(reverse('roadmap_node_children', args=[self.roadmap.slug, outside.pk]), {'cursor': cursor})
        self.assertEqual(wrong.status_code, 400)
        self.node('new-child', parent=root)
        stale = self.client.get(reverse('roadmap_node_children', args=[self.roadmap.slug, root.pk]), {'cursor': cursor})
        self.assertEqual(stale.status_code, 409)
        from .roadmap_selectors import RoadmapSnapshot
        with CaptureQueriesContext(connection) as small:
            snapshot = RoadmapSnapshot(AnonymousUser(), self.roadmap)
            for node in children:
                snapshot.progress(node, 'subtree')
        for i in range(4, 24):
            self.link(self.node(f'child-{i}', parent=root), self.problem(f'query_{i}'))
        with CaptureQueriesContext(connection) as large:
            snapshot = RoadmapSnapshot(AnonymousUser(), self.roadmap)
            for node in snapshot.nodes:
                snapshot.progress(node, 'subtree')
        self.assertLessEqual(len(large), len(small) + 2)
        print('Roadmap query measurement:', len(small), 'small;', len(large), 'large')

    def test_batched_problem_access_matches_existing_policy(self):
        from .roadmap_selectors import get_accessible_problem_ids
        org = Organization.objects.create(slug='parity_org', name='Parity', short_name='P', about='')
        public = self.problem('parity_public')
        private = self.problem('parity_private', is_public=False)
        scoped = self.problem('parity_scoped', is_organization_private=True, organization=org)
        authored = self.problem('parity_author', is_public=False)
        authored.authors.add(self.learner_profile)
        candidates = [public, private, scoped, authored]
        ids = [problem.pk for problem in candidates]
        for member, permissions in ((False, []), (True, []),
                                    (False, ['edit_own_problem', 'edit_public_problem']),
                                    (False, ['edit_own_problem', 'edit_all_problem']),
                                    (False, ['see_organization_problem']), (False, ['see_private_problem'])):
            self.learner_profile.organizations.clear()
            if member:
                self.learner_profile.organizations.add(org)
            self.learner.user_permissions.set(Permission.objects.filter(content_type__app_label='judge',
                                                                       codename__in=permissions))
            for cache in ('_perm_cache', '_user_perm_cache', '_group_perm_cache'):
                self.learner.__dict__.pop(cache, None)
            from judge.models import Problem
            visible = set(Problem.get_visible_problems(self.learner).values_list('pk', flat=True))
            expected = {problem.pk for problem in candidates if problem.pk in visible and
                        problem.is_accessible_by(self.learner)}
            self.assertEqual(get_accessible_problem_ids(self.learner, ids), expected)

    def test_prejoin_suppression_and_contest_only_private_discovery(self):
        from judge.models.tests.util import create_contest, create_contest_participation, create_contest_problem
        from .roadmap_selectors import get_accessible_problem_ids, RoadmapSnapshot
        node = self.node('contest-node')
        public, private = self.problem('contest_public'), self.problem('contest_private', is_public=False)
        self.link(node, public)
        self.link(node, private)
        now = timezone.now()
        contest = create_contest(key='roadmapcontest', start_time=now + timezone.timedelta(hours=1),
                                 end_time=now + timezone.timedelta(hours=3))
        participation = create_contest_participation(contest=contest, user=self.learner_profile,
                                                     real_start=now, virtual=0)
        create_contest_problem(contest=contest, problem=private)
        self.learner_profile.current_contest = participation
        self.learner_profile.save()
        self.assertEqual(get_accessible_problem_ids(self.learner, [public.pk, private.pk]), set())
        self.assertEqual(RoadmapSnapshot(self.learner, self.roadmap).progress(node)['state'], 'unavailable')
        contest.start_time = now - timezone.timedelta(hours=1)
        contest.save()
        contest.__dict__.pop('can_join', None)
        participation.contest = contest
        self.assertEqual(get_accessible_problem_ids(self.learner, [public.pk, private.pk]), {public.pk})
        self.submission(public, contest_object=contest)
        self.assertEqual(RoadmapSnapshot(self.learner, self.roadmap).progress(node)['solved'], 1)

    def test_http_subtree_is_independent_of_loaded_children_and_submission_delete(self):
        root = self.node('root')
        child = self.node('child', parent=root)
        problem = self.problem('delete_ac')
        self.link(root, problem)
        self.link(child, problem)
        submission = self.submission(problem)
        result = self.progress(root).json()
        self.assertEqual((result['subtree']['solved'], result['subtree']['total']), (1, 1))
        submission.delete()
        self.assertEqual(self.progress(root).json()['subtree']['solved'], 0)
        problem.is_public = False
        problem.save()
        self.assertEqual(self.progress(root).json()['subtree']['total'], 0)

    def test_content_state_transitions_and_serialization(self):
        empty_topic = LearningTopic.objects.create(name='Trans Topic', slug='trans-topic',
                                                   introduction='', status=Publication.PUBLISHED)
        node = self.node('trans-node', learning_topic=empty_topic)

        def get_item():
            resp = self.client.get(reverse('roadmap_detail', args=[self.roadmap.slug]))
            return next(it for it in resp.json()['items'] if it['id'] == node.id)
        node.summary = 'Learner-safe node summary'
        node.display_section = 'Section label'
        node.save()
        item = get_item()
        self.assertEqual(item['summary'], 'Learner-safe node summary')
        self.assertEqual(item['display_section'], 'Section label')

        # 1. Empty topic with no exercises -> UPCOMING, learn_url is None
        item = get_item()
        self.assertEqual(item['content_state'], 'UPCOMING')
        self.assertIsNone(item['learn_url'])

        # 2. Add nonblank introduction -> transitions to AVAILABLE
        empty_topic.introduction = 'Nonblank intro'
        empty_topic.save()
        item = get_item()
        self.assertEqual(item['content_state'], 'AVAILABLE')
        self.assertIsNotNone(item['learn_url'])

        # 3. Clear introduction -> transitions back to UPCOMING
        empty_topic.introduction = '   '
        empty_topic.save()
        item = get_item()
        self.assertEqual(item['content_state'], 'UPCOMING')
        self.assertIsNone(item['learn_url'])

        # 4. Add draft lesson -> still UPCOMING
        lesson = TopicLesson.objects.create(topic=empty_topic, title='L1', slug='l1',
                                            body='Lesson content', status=Publication.DRAFT)
        item = get_item()
        self.assertEqual(item['content_state'], 'UPCOMING')

        # 5. Add published lesson with blank body (simulating historical row) -> still UPCOMING
        blank_lesson = TopicLesson.objects.create(topic=empty_topic, title='Blank', slug='blank',
                                                  body='   ', status=Publication.DRAFT)
        TopicLesson.objects.filter(pk=blank_lesson.pk).update(status=Publication.PUBLISHED)
        item = get_item()
        self.assertEqual(item['content_state'], 'UPCOMING')

        # 6. Publish lesson with real content -> transitions to AVAILABLE
        lesson.status = Publication.PUBLISHED
        lesson.save()
        item = get_item()
        self.assertEqual(item['content_state'], 'AVAILABLE')
        self.assertIsNotNone(item['learn_url'])

        # 7. Unpublish lessons -> back to UPCOMING
        lesson.status = Publication.DRAFT
        lesson.save()
        blank_lesson.delete()
        item = get_item()
        self.assertEqual(item['content_state'], 'UPCOMING')

        # 8. Add direct problem link -> transitions to AVAILABLE
        prob = self.problem('trans_prob')
        link = self.link(node, prob)
        item = get_item()
        self.assertEqual(item['content_state'], 'AVAILABLE')
        self.assertIsNotNone(item['learn_url'])

        # 9. Delete problem link -> back to UPCOMING
        link.delete()
        item = get_item()
        self.assertEqual(item['content_state'], 'UPCOMING')
        self.assertIsNone(item['learn_url'])

    def test_direct_subtree_readiness_independence(self):
        empty_topic = LearningTopic.objects.create(name='Indep Topic', slug='indep-topic',
                                                   introduction='', status=Publication.PUBLISHED)
        parent = self.node('indep-parent', learning_topic=empty_topic)
        child = self.node('indep-child', parent=parent, learning_topic=empty_topic)
        self.link(child, self.problem('child_only_prob'))

        # HTTP read parent root: has subtree problems, but NO direct content -> UPCOMING
        roots = self.client.get(reverse('roadmap_detail', args=[self.roadmap.slug])).json()['items']
        parent_item = next(it for it in roots if it['id'] == parent.id)
        self.assertEqual(parent_item['content_state'], 'UPCOMING')
        self.assertIsNone(parent_item['learn_url'])
        self.assertEqual(parent_item['subtree_progress']['total'], 1)
        self.assertEqual(parent_item['progress']['total'], 0)

        # HTTP read child: has direct problem -> AVAILABLE
        children = self.client.get(reverse('roadmap_node_children', args=[self.roadmap.slug, parent.id])).json()['items']
        child_item = next(it for it in children if it['id'] == child.id)
        self.assertEqual(child_item['content_state'], 'AVAILABLE')
        self.assertIsNotNone(child_item['learn_url'])

    def test_contest_suppression_does_not_affect_readiness(self):
        from judge.models.tests.util import create_contest, create_contest_participation
        node = self.node('suppressed-node')
        prob = self.problem('suppressed_direct_prob')
        self.link(node, prob)

        # Create a contest with can_join=False
        now = timezone.now()
        contest = create_contest(key='suppressed_contest', name='Suppressed Contest', is_visible=True,
                                 start_time=now + timezone.timedelta(hours=2),
                                 end_time=now + timezone.timedelta(hours=4))
        participation = create_contest_participation(contest=contest, user=self.learner_profile,
                                                     real_start=now, virtual=0)
        self.learner_profile.current_contest = participation
        self.learner_profile.save()

        # Progress should be suppressed
        self.client.force_login(self.learner)
        roots = self.client.get(reverse('roadmap_detail', args=[self.roadmap.slug])).json()['items']
        item = next(it for it in roots if it['id'] == node.id)
        self.assertEqual(item['progress']['state'], 'unavailable')
        self.assertEqual(item['progress']['total'], 0)

        # BUT content_state and learn_url must NOT be conflated with AC suppression
        self.assertEqual(item['content_state'], 'AVAILABLE')
        self.assertIsNotNone(item['learn_url'])
    def test_focus_metadata_content_state_and_learn_url(self):
        empty_topic = LearningTopic.objects.create(name='Focus Empty', slug='focus-empty',
                                                   introduction='', status=Publication.PUBLISHED)
        empty_node = self.node('focus-empty-node', learning_topic=empty_topic)
        ready_node = self.node('focus-ready-node')  # self.topic has 'Topic intro'

        # 1. Empty focus node
        resp_empty = self.client.get(reverse('roadmap_detail', args=[self.roadmap.slug]),
                                     {'focus': empty_node.pk})
        self.assertEqual(resp_empty.status_code, 200)
        data_empty = resp_empty.json()
        self.assertEqual(data_empty['focus']['content_state'], 'UPCOMING')
        self.assertIsNone(data_empty['focus']['learn_url'])

        # 2. Ready focus node
        resp_ready = self.client.get(reverse('roadmap_detail', args=[self.roadmap.slug]),
                                     {'focus': ready_node.pk})
        self.assertEqual(resp_ready.status_code, 200)
        data_ready = resp_ready.json()
        self.assertEqual(data_ready['focus']['content_state'], 'AVAILABLE')
        self.assertEqual(
            data_ready['focus']['learn_url'],
            reverse('roadmap_node_learn', args=[self.roadmap.slug, ready_node.pk])
        )
