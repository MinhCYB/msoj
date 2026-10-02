from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.constants import FEATURE_AI_BRAINSTORM
from billing.models import Plan, Subscription
from judge.models import Problem, ProblemGroup, Profile

from .models import BrainstormMessage, BrainstormSession


class BrainstormSendTestCase(TestCase):
    def setUp(self):
        self.paid_user = User.objects.create_user(username='paid-user', password='testpass')
        self.free_user = User.objects.create_user(username='free-user', password='testpass')
        self.paid_profile = Profile.objects.create(user=self.paid_user)
        self.free_profile = Profile.objects.create(user=self.free_user)
        self.problem = Problem.objects.create(
            code='mentor_test_problem',
            name='Mentor test problem',
            group=ProblemGroup.objects.create(name='mentor-test', full_name='Mentor test'),
            time_limit=1,
            memory_limit=65536,
            points=100,
            is_public=True,
        )
        plan = Plan.objects.create(
            name='Brainstorm plan',
            scope=Plan.SCOPE_PERSONAL,
            pricing_type=Plan.PRICING_PER_DAY,
            price_per_day=Decimal('10.00'),
            features=[FEATURE_AI_BRAINSTORM],
        )
        Subscription.objects.create(
            profile=self.paid_profile,
            plan=plan,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
            price_paid=Decimal('10.00'),
            status=Subscription.STATUS_ACTIVE,
        )
        self.url = reverse('mentor_brainstorm_send', args=[self.problem.code])

    def test_old_post_is_retired_without_publishing(self):
        self.client.force_login(self.free_user)

        response = self.client.post(self.url, {
            'described_approach': 'Try dynamic programming.',
            'content': 'I need help with the state.',
        })

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()['error_code'], 'legacy_endpoint_retired')
        self.assertEqual(BrainstormMessage.objects.count(), 0)

    def test_paid_user_cannot_write_stub(self):
        self.client.force_login(self.paid_user)

        response = self.client.post(self.url, {
            'described_approach': 'Try dynamic programming.',
            'content': 'I need help with the state.',
        })

        self.assertEqual(response.status_code, 410)
        self.assertFalse(BrainstormMessage.objects.exists())

    def test_repeated_old_posts_do_not_create_session(self):
        self.client.force_login(self.paid_user)
        data = {
            'described_approach': 'Try dynamic programming.',
            'content': 'I need help with the state.',
        }
        self.assertEqual(self.client.post(self.url, data).status_code, 410)
        self.assertEqual(self.client.post(self.url, data).status_code, 410)
        self.assertFalse(BrainstormSession.objects.exists())
