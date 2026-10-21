from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from billing.constants import FEATURE_AI_REVIEW
from billing.models import Plan, Subscription
from billing.services import is_active_for
from judge.models import Profile


class SubscriptionStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.now()
        cls.profile = Profile.objects.create(user=get_user_model().objects.create_user('learner'))
        cls.plan = Plan.objects.create(name='AI', scope=Plan.SCOPE_PERSONAL, pricing_type=Plan.PRICING_PER_DAY,
                                       price_per_day=0, features=[FEATURE_AI_REVIEW])

    def sub(self, status, end_offset_days):
        return Subscription.objects.create(
            profile=self.profile, plan=self.plan, status=status, price_paid=0,
            start_date=self.now - timedelta(days=30), end_date=self.now + timedelta(days=end_offset_days))

    def test_stored_active_past_end_date_is_effectively_expired_and_grants_nothing(self):
        stale = self.sub(Subscription.STATUS_ACTIVE, -1)
        self.assertEqual(stale.effective_status(), Subscription.STATUS_EXPIRED)
        self.assertFalse(is_active_for(self.profile, FEATURE_AI_REVIEW))

    def test_active_before_end_date_is_effective_and_grants_access(self):
        live = self.sub(Subscription.STATUS_ACTIVE, 5)
        self.assertEqual(live.effective_status(), Subscription.STATUS_ACTIVE)
        self.assertTrue(is_active_for(self.profile, FEATURE_AI_REVIEW))

    def test_cancelled_stays_cancelled_even_when_not_yet_ended(self):
        cancelled = self.sub(Subscription.STATUS_CANCELLED, 5)
        self.assertEqual(cancelled.effective_status(), Subscription.STATUS_CANCELLED)
        self.assertFalse(is_active_for(self.profile, FEATURE_AI_REVIEW))

    def test_admin_filter_buckets_match_effective_status(self):
        stale = self.sub(Subscription.STATUS_ACTIVE, -1)
        live = self.sub(Subscription.STATUS_ACTIVE, 5)
        expired = self.sub(Subscription.STATUS_EXPIRED, 5)
        cancelled = self.sub(Subscription.STATUS_CANCELLED, -1)
        staff = get_user_model().objects.create_superuser('boss', password='x')
        Profile.objects.create(user=staff)
        self.client.force_login(staff)

        def ids(value):
            response = self.client.get('/admin/billing/subscription/', {'effective_status': value})
            self.assertEqual(response.status_code, 200)
            return {s.pk for s in response.context['cl'].result_list}

        self.assertEqual(ids('active'), {live.pk})
        self.assertEqual(ids('expired'), {stale.pk, expired.pk})
        self.assertEqual(ids('cancelled'), {cancelled.pk})
