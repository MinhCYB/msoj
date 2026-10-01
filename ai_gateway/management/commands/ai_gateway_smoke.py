from django.core.management.base import BaseCommand, CommandError

from ai_gateway import client
from ai_gateway.errors import GatewayError
from ai_gateway.models import ModelRoute, ProviderConnection
from ai_gateway.types import Message


class Command(BaseCommand):
    help = 'Check the configured AI provider catalog; optionally run a paid generate smoke test.'

    def add_arguments(self, parser):
        parser.add_argument('--connection', required=True, help='Configured ProviderConnection slug.')
        parser.add_argument('--role', help='Enabled ModelRoute role to check against the catalog.')
        parser.add_argument('--generate', action='store_true', help='Send one potentially billable completion request.')
        parser.add_argument('--confirm-paid-request', action='store_true', help='Explicitly confirm the paid request.')

    def handle(self, *args, **options):
        if options['generate'] and (not options['confirm_paid_request'] or not options['role']):
            raise CommandError('Generate requires --role and --confirm-paid-request; ask for approval before running.')
        connection = ProviderConnection.objects.filter(slug=options['connection']).first()
        if connection is None:
            raise CommandError('Provider connection not configured.')
        try:
            catalog = client.list_models(connection)
        except GatewayError as exc:
            raise CommandError('Model discovery failed: %s' % exc.code) from None
        self.stdout.write('Model discovery: OK; count=%d' % len(catalog))
        route = None
        if options['role']:
            route = ModelRoute.objects.filter(role=options['role'], connection=connection, enabled=True).first()
            if route is None:
                raise CommandError('Enabled role is not routed through this connection.')
            self.stdout.write('Selected model in catalog: %s' % ('YES' if catalog.contains(route.model_id) else 'NO'))
            if not catalog.contains(route.model_id):
                raise CommandError('Selected model is not present in the catalog.')
        if options['generate']:
            try:
                result = client.generate(options['role'], [Message('system', 'Reply with exactly: OK'),
                                                          Message('user', 'ping')],
                                         max_tokens=8)
            except GatewayError as exc:
                raise CommandError('Generate failed: %s' % exc.code) from None
            self.stdout.write('Generate: OK; role=%s; connection=%s; requested_model=%s; returned_model=%s; '
                              'text=%r; finish_reason=%s; usage=%s' %
                              (options['role'], connection.slug, result.requested_model,
                               result.returned_model or 'not provided', result.text,
                               result.finish_reason or 'not provided', result.usage))
