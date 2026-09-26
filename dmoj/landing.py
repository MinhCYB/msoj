"""Presentation-only data for the MSOJ landing page.

Prices here are examples, not billing.Plan data or an offer to purchase.
Keeping them separate from the template makes replacing the source later safe.
"""

from django.views.generic import TemplateView


EXAMPLE_PLANS = (
    {'name': 'Gói theo ngày (minh họa)', 'pricing_type': 'per_day',
     'amount': 10000, 'duration_days': None, 'features': ('Luyện tập trên hệ thống bài tập',)},
    {'name': 'Gói thời hạn (minh họa)', 'pricing_type': 'fixed',
     'amount': 100000, 'duration_days': 30, 'features': ('Luyện tập trên hệ thống bài tập',)},
)


class LandingView(TemplateView):
    template_name = 'landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'MSOJ'
        context['example_plans'] = EXAMPLE_PLANS
        return context
