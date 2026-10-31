from django.test import Client, TestCase
from django.urls import reverse
from lxml import html
from .models import LearningTopic, TopicLesson, TopicLessonQAMessage, TopicLessonState
from .roadmap_models import Publication
from .tests_roadmap import RoadmapFixture



class RoadmapLearningTests(RoadmapFixture, TestCase):
    def page(self, node, lesson=None, **query):
        name = 'roadmap_node_lesson' if lesson else 'roadmap_node_learn'
        args = [self.roadmap.slug, node.pk] + ([lesson.pk] if lesson else [])
        return self.client.get(reverse(name, args=args), query, HTTP_ACCEPT='text/html')

    def test_learn_document_lists_published_nonblank_lessons_only_in_order(self):
        node = self.node('document')
        later = TopicLesson.objects.create(topic=self.topic, title='Later published', slug='later',
                                           body='Later body', status=Publication.PUBLISHED, position=20)
        first = TopicLesson.objects.create(topic=self.topic, title='First published', slug='first',
                                           body='First body', status=Publication.PUBLISHED, position=2)
        TopicLesson.objects.create(topic=self.topic, title='Draft secret', slug='draft-secret',
                                   body='Draft body', status=Publication.DRAFT, position=3)
        blank = TopicLesson.objects.create(topic=self.topic, title='Blank secret', slug='blank-secret',
                                           body=' ', status=Publication.DRAFT, position=4)
        TopicLesson.objects.filter(pk=blank.pk).update(status=Publication.PUBLISHED)
        unrelated_topic = LearningTopic.objects.create(name='Unrelated', slug='unrelated', status=Publication.PUBLISHED)
        TopicLesson.objects.create(topic=unrelated_topic, title='Unrelated secret', slug='unrelated',
                                   body='Unrelated body', status=Publication.PUBLISHED)

        response = self.page(node)
        self.assertEqual(response.status_code, 200)
        lessons = response.context['document_lessons']
        self.assertEqual([lesson['id'] for lesson in lessons], [first.pk, later.pk])
        articles = html.fromstring(response.content).xpath('//article[contains(@class, "rm-document-lesson")]')
        self.assertEqual([article.get('id') for article in articles],
                         [f'rm-lesson-{first.pk}', f'rm-lesson-{later.pk}'])
        self.assertIn('First body', articles[0].text_content())
        self.assertIn('Later body', articles[1].text_content())
        content = response.content.decode()
        for secret in ('Draft secret', 'Draft body', 'Blank secret', 'Unrelated secret', 'Unrelated body'):
            self.assertNotIn(secret, content)

    def test_document_state_and_history_are_scoped_to_lesson_and_revision(self):
        node = self.node('document-state')
        first = TopicLesson.objects.create(topic=self.topic, title='First chapter', slug='first-chapter',
                                           body='First body', status=Publication.PUBLISHED, position=1)
        second = TopicLesson.objects.create(topic=self.topic, title='Second chapter', slug='second-chapter',
                                            body='Second body', status=Publication.PUBLISHED, position=2)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.learner)
        TopicLessonState.objects.create(user=self.learner, lesson=first, content_revision=1, offset=700)
        TopicLessonState.objects.create(user=self.learner, lesson=second, content_revision=1,
                                        offset=1700, position_version=5000)
        TopicLessonQAMessage.objects.create(user=self.learner, lesson=first, content_revision=1,
                                            role=TopicLessonQAMessage.Role.USER, content='First-only question')
        TopicLessonQAMessage.objects.create(user=self.learner, lesson=second, content_revision=1,
                                            role=TopicLessonQAMessage.Role.USER, content='Second chapter question')
        TopicLessonQAMessage.objects.create(user=self.learner, lesson=second, content_revision=1,
                                            role=TopicLessonQAMessage.Role.ASSISTANT, content='Second chapter answer')
        TopicLessonQAMessage.objects.create(user=self.learner, lesson=second, content_revision=0,
                                            role=TopicLessonQAMessage.Role.USER, content='Stale revision question')
        TopicLessonState.objects.create(user=self.staff, lesson=second, content_revision=1, offset=9900)
        TopicLessonQAMessage.objects.create(user=self.staff, lesson=second, content_revision=1,
                                            role=TopicLessonQAMessage.Role.USER, content='Other account private question')

        response = self.page(node)
        csrf_token = html.fromstring(response.content).xpath(
            '//form[contains(@class, "rm-tutor-form")]//input[@name="csrfmiddlewaretoken"]/@value'
        )[0]
        lessons = {item['id']: item for item in response.context['document_lessons']}
        first_state = lessons[first.pk]['lecture_state']
        second_state = lessons[second.pk]['lecture_state']
        self.assertEqual(first_state['resume_offset'], 700)
        self.assertEqual([item['content'] for item in first_state['messages']], ['First-only question'])
        self.assertEqual(second_state['resume_offset'], 1700)
        self.assertEqual([item['content'] for item in second_state['messages']],
                         ['Second chapter question', 'Second chapter answer'])

        second.summary = 'Updated chapter content'
        second.save()
        refreshed = self.page(node).context['document_lessons']
        second_state = next(item['lecture_state'] for item in refreshed if item['id'] == second.pk)
        self.assertEqual(second_state['resume_offset'], 0)
        self.assertEqual(second_state['messages'], [])
        self.assertEqual(second_state['position_version'], 5000)
        self.assertEqual(self.page(node).context['resume_lesson_id'], first.pk)
        state_url = reverse('roadmap_node_lesson_state', args=[self.roadmap.slug, node.pk, second.pk])
        response = self.client.post(state_url, data={'offset': 2400,
                                   'content_revision': second.content_revision, 'position_version': 5001},
                                   content_type='application/json', HTTP_X_CSRFTOKEN=csrf_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.page(node).context['resume_lesson_id'], second.pk)
        state = TopicLessonState.objects.get(user=self.learner, lesson=second)
        self.assertEqual((state.content_revision, state.offset), (second.content_revision, 2400))

    def test_legacy_lesson_html_redirects_but_json_keeps_lesson_body(self):
        node = self.node('legacy-lesson')
        lesson = TopicLesson.objects.create(topic=self.topic, title='Inline chapter', slug='inline-chapter',
                                            body='JSON lesson body', status=Publication.PUBLISHED, position=1)
        html_response = self.page(node, lesson)
        self.assertEqual(html_response.status_code, 302)
        self.assertEqual(html_response['Location'],
                         f"{reverse('roadmap_node_learn', args=[self.roadmap.slug, node.pk])}#rm-lesson-{lesson.pk}")

        json_response = self.client.get(reverse('roadmap_node_lesson', args=[self.roadmap.slug, node.pk, lesson.pk]))
        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(json_response.json()['lesson']['body'], 'JSON lesson body')


    def test_reused_topic_keeps_node_exercises_and_fresh_ac(self):
        a, b = self.node('a', type='GROUP'), self.node('b')
        early = TopicLesson.objects.create(topic=self.topic, title='Early', slug='early', body='Body', status='PUBLISHED', position=1)
        late = TopicLesson.objects.create(topic=self.topic, title='Late', slug='late', body='Body', status='PUBLISHED', position=2)
        p, q = self.problem('practice_a'), self.problem('practice_b')
        self.link(a, p)
        self.link(b, q)
        self.client.force_login(self.learner)
        for node, problem in ((a, p), (b, q)):
            data = self.page(node).context['learning']
            self.assertEqual([item['id'] for item in data['lessons']], [early.pk, late.pk])
            self.assertEqual([item['id'] for item in data['problems']], [problem.pk])
            self.assertEqual(data['topic']['introduction'], self.topic.introduction)
        submission = self.submission(p)
        lesson_json = self.client.get(reverse('roadmap_node_lesson', args=[self.roadmap.slug, a.pk, early.pk]))
        self.assertEqual(lesson_json.json()['navigation']['next_lesson_url'],
                         reverse('roadmap_node_lesson', args=[self.roadmap.slug, a.pk, late.pk]))
        self.assertEqual(self.page(a).context['learning']['progress']['solved'], 1)
        submission.result = 'WA'
        submission.save()
        self.assertEqual(self.page(a).context['learning']['progress']['solved'], 0)
        self.topic.status = Publication.DRAFT
        self.topic.save()
        # Draft topic with problem falls back to exercises-only: topic/lessons omitted
        page_a = self.page(a)
        self.assertEqual(page_a.status_code, 200)
        learning_a = page_a.context['learning']
        self.assertIsNone(learning_a['topic'])
        self.assertEqual(learning_a['lessons'], [])
        self.assertEqual([item['id'] for item in learning_a['problems']], [p.pk])
        # Direct lesson access returns 404 because topic is DRAFT
        self.assertEqual(self.page(b, early).status_code, 404)

    def test_direct_urls_and_preview_do_not_bypass_visibility(self):
        node = self.node('topic')
        draft = TopicLesson.objects.create(topic=self.topic, title='Secret draft', slug='draft', body='Secret')
        other = LearningTopic.objects.create(name='Other', slug='other')
        wrong = TopicLesson.objects.create(topic=other, title='Wrong', slug='wrong', body='Secret', status='PUBLISHED')
        self.assertEqual(self.page(node, draft).status_code, 404)
        self.assertEqual(self.page(node, wrong).status_code, 404)
        private = self.problem('hidden_practice', is_public=False)
        self.link(node, private)
        self.assertEqual(self.page(node).context['learning']['problems'], [])
        preview_url = reverse('roadmap_markdown_preview')
        self.assertEqual(self.client.post(preview_url, {'content': 'Secret'}).status_code, 403)
        self.client.force_login(self.learner)
        self.assertEqual(self.client.post(preview_url, {'content': 'Secret'}).status_code, 403)

    def test_preview_sanitization_and_markdown_rendering(self):
        source = '# Heading\n\n<script>alert(1)</script>\n\n[unsafe](javascript:alert(1))\n\n![image](/static/icons/logo.svg)\n\n```cpp\nint x = 1;\n```\n\n|a|b|\n|-|-|\n|1|2|'
        self.client.force_login(self.staff)
        preview = html.fromstring(self.client.post(reverse('roadmap_markdown_preview'), {'content': source}).content).xpath('//div[contains(@class,"rm-prose")]')[0]
        self.assertEqual(preview.xpath('.//script | .//@onclick | .//a[starts-with(@href,"javascript:")]'), [])
        self.assertEqual(preview.xpath('.//td/text()'), ['1', '2'])
    def test_empty_published_topic_learn_endpoint_returns_404(self):
        empty_topic = LearningTopic.objects.create(name='Empty Topic', slug='empty-topic',
                                                   introduction='', status='PUBLISHED')
        empty_node = self.node('empty-node', learning_topic=empty_topic)
        self.client.force_login(self.learner)
        self.assertEqual(self.page(empty_node).status_code, 404)

    def test_topic_only_without_problems_returns_200(self):
        theory_topic = LearningTopic.objects.create(name='Theory Only', slug='theory-only',
                                                    introduction='Pure theory', status='PUBLISHED')
        theory_node = self.node('theory-node', learning_topic=theory_topic)
        self.client.force_login(self.learner)
        page = self.page(theory_node)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context['learning']['topic']['introduction'], 'Pure theory')
        self.assertEqual(page.context['learning']['problems'], [])

    def test_lesson_readiness_blank_body_and_draft_status(self):
        topic = LearningTopic.objects.create(name='Lesson Topic', slug='lesson-topic',
                                             introduction='', status='PUBLISHED')
        node = self.node('lesson-node', learning_topic=topic)
        self.client.force_login(self.learner)

        # 1. Draft lesson does not make node ready; direct access is 404
        draft_lesson = TopicLesson.objects.create(topic=topic, title='Draft', slug='draft',
                                                  body='Some content', status='DRAFT')
        self.assertEqual(self.page(node).status_code, 404)
        self.assertEqual(self.page(node, draft_lesson).status_code, 404)

        # 2. Creating published lesson with blank body raises model ValidationError
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            TopicLesson.objects.create(topic=topic, title='Blank', slug='blank',
                                       body='   ', status='PUBLISHED')
        # Explicitly simulate corrupted/historical row via queryset.update
        blank_lesson = TopicLesson.objects.create(topic=topic, title='Blank', slug='blank',
                                                  body='   ', status='DRAFT')
        TopicLesson.objects.filter(pk=blank_lesson.pk).update(status='PUBLISHED')
        self.assertEqual(self.page(node).status_code, 404)
        self.assertEqual(self.page(node, blank_lesson).status_code, 404)

        # 3. Nonblank published lesson makes node ready; direct access is 200
        valid_lesson = TopicLesson.objects.create(topic=topic, title='Valid', slug='valid',
                                                  body='Real content', status='PUBLISHED')
        self.assertEqual(self.page(node).status_code, 200)
        self.assertEqual(self.page(node, valid_lesson).status_code, 302)

    def test_hidden_linked_topic_fallback_and_permission_retention(self):
        from judge.models import Organization
        from .roadmap_models import Visibility
        org = Organization.objects.create(name='Private learning org', slug='private-learning-org')
        private_topic = LearningTopic.objects.create(
            name='Private Topic', slug='private-topic',
            visibility=Visibility.ORGANIZATION, organization=org,
            introduction='Secret Guide', status='PUBLISHED'
        )
        private_lesson = TopicLesson.objects.create(
            topic=private_topic, title='Private Lesson', slug='private-lesson',
            body='Secret theory', status='PUBLISHED'
        )
        # Node belongs to public roadmap, linked to org topic (wait, scope check: org topic on public roadmap?)
        # As enforced in clean(): topic org requires roadmap org. So create org roadmap:
        org_roadmap = self.roadmap.__class__.objects.create(
            title='Org Roadmap', slug='org-roadmap', visibility=Visibility.ORGANIZATION,
            organization=org, status='PUBLISHED'
        )
        from .roadmap_services import create_node
        org_node = create_node(self.staff, roadmap=org_roadmap, title='Org Node', slug='org-node',
                               learning_topic=private_topic, status='PUBLISHED')
        prob = self.problem('org_accessible_prob')
        self.link(org_node, prob)

        self.client.force_login(self.learner)
        # Learner is not in org -> roadmap itself is unauthorized
        learn_url = reverse('roadmap_node_learn', args=[org_roadmap.slug, org_node.pk])
        self.assertEqual(self.client.get(learn_url, HTTP_ACCEPT='text/html').status_code, 404)

        # Now add user to org -> both roadmap and private topic become authorized
        self.learner_profile.organizations.add(org)
        resp_auth = self.client.get(learn_url, HTTP_ACCEPT='text/html')
        self.assertEqual(resp_auth.status_code, 200)
        data_auth = resp_auth.context['learning']
        self.assertEqual(data_auth['topic']['introduction'], 'Secret Guide')
        self.assertEqual([l['id'] for l in data_auth['lessons']], [private_lesson.pk])

        # Now change topic to DRAFT: user still in org, roadmap accessible, but topic is DRAFT
        private_topic.status = 'DRAFT'
        private_topic.save()
        resp_draft_fallback = self.client.get(learn_url, HTTP_ACCEPT='text/html')
        self.assertEqual(resp_draft_fallback.status_code, 200)
        data_fallback = resp_draft_fallback.context['learning']
        self.assertIsNone(data_fallback['topic'])
        self.assertEqual(data_fallback['lessons'], [])
        self.assertEqual(len(data_fallback['problems']), 1)
        self.assertEqual(data_fallback['problems'][0]['code'], 'org_accessible_prob')
        # Lesson direct URL returns 404
        lesson_url = reverse('roadmap_node_lesson', args=[org_roadmap.slug, org_node.pk, private_lesson.pk])
        self.assertEqual(self.client.get(lesson_url, HTTP_ACCEPT='text/html').status_code, 404)
