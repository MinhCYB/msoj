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

    def test_free_user_blocked(self):
        self.client.force_login(self.free_user)

        response = self.client.post(self.url, {
            'described_approach': 'Try dynamic programming.',
            'content': 'I need help with the state.',
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['allowed'], False)
        self.assertEqual(BrainstormMessage.objects.count(), 0)

    def test_paid_user_allowed(self):
        self.client.force_login(self.paid_user)

        response = self.client.post(self.url, {
            'described_approach': 'Try dynamic programming.',
            'content': 'I need help with the state.',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['allowed'], True)
        self.assertEqual(response.json()['hint_level_granted'], 1)
        self.assertEqual(BrainstormMessage.objects.count(), 2)
        self.assertEqual(
            list(BrainstormMessage.objects.values_list('role', flat=True)),
            [BrainstormMessage.ROLE_STUDENT, BrainstormMessage.ROLE_AI],
        )

    def test_hint_level_increases_over_time(self):
        self.client.force_login(self.paid_user)
        data = {
            'described_approach': 'Try dynamic programming.',
            'content': 'I need help with the state.',
        }
        self.client.post(self.url, data)
        BrainstormSession.objects.filter(
            profile=self.paid_profile,
            problem=self.problem,
        ).update(total_active_seconds=700)

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['hint_level_granted'], 2)
