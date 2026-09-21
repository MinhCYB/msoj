from collections import OrderedDict
from pathlib import Path

from django.apps import apps
from django.db import models


OUTPUT_PATH = Path('docs/msoj-schema-full-v2.dbml')
INCLUDED_AUTH_MODELS = {'User', 'Group', 'Permission'}

GROUP_MODELS = OrderedDict([
    ('Auth & Profile', {
        'auth.Group',
        'auth.Permission',
        'auth.User',
        'judge.Badge',
        'judge.Organization',
        'judge.OrganizationMonthlyUsage',
        'judge.OrganizationQuota',
        'judge.OrganizationRequest',
        'judge.Profile',
        'judge.WebAuthnCredential',
    }),
    ('Problem', {
        'judge.LanguageLimit',
        'judge.License',
        'judge.OrganizationProblemTag',
        'judge.Problem',
        'judge.ProblemClarification',
        'judge.ProblemData',
        'judge.ProblemGroup',
        'judge.ProblemTestCase',
        'judge.ProblemTranslation',
        'judge.ProblemType',
        'judge.Solution',
    }),
    ('Contest', {
        'judge.Contest',
        'judge.ContestAnnouncement',
        'judge.ContestMoss',
        'judge.ContestParticipation',
        'judge.ContestProblem',
        'judge.ContestSubmission',
        'judge.ContestTag',
        'judge.Rating',
    }),
    ('Submission & Runtime', {
        'judge.Judge',
        'judge.Language',
        'judge.RuntimeVersion',
        'judge.Submission',
        'judge.SubmissionSource',
        'judge.SubmissionTestCase',
    }),
    ('Blog & Comment & Notification', {
        'judge.BlogPost',
        'judge.BlogPostTag',
        'judge.BlogVote',
        'judge.Comment',
        'judge.CommentLock',
        'judge.CommentVote',
        'judge.Notification',
    }),
    ('Tag & Ticket', {
        'judge.GeneralIssue',
        'judge.Tag',
        'judge.TagData',
        'judge.TagGroup',
        'judge.TagProblem',
        'judge.Ticket',
        'judge.TicketMessage',
    }),
    ('Misc', {
        'judge.MiscConfig',
        'judge.NavigationBar',
        'urlshortener.URLShortener',
    }),
    ('Billing', {
        'billing.Plan',
        'billing.Subscription',
    }),
    ('Mentor', {
        'mentor.Topic',
        'mentor.RoadmapNode',
        'mentor.RoadmapPrerequisite',
        'mentor.BrainstormSession',
        'mentor.BrainstormMessage',
        'mentor.AIReview',
        'mentor.AIReviewApproach',
    }),
])


def included_root_models():
    return [
        model
        for model in apps.get_models()
        if model._meta.app_label in {'judge', 'urlshortener', 'billing', 'mentor'}
        or (
            model._meta.app_label == 'auth'
            and model.__name__ in INCLUDED_AUTH_MODELS
        )
    ]


def all_database_models():
    result = set(included_root_models())
    pending = list(result)
    while pending:
        model = pending.pop()
        for field in model._meta.local_many_to_many:
            through = field.remote_field.through
            if through not in result:
                result.add(through)
                pending.append(through)
    return sorted(result, key=lambda model: model._meta.db_table)


def dbml_type(field):
    if field.many_to_one or field.one_to_one:
        return 'int'
    if isinstance(field, models.BigIntegerField):
        return 'bigint'
    if isinstance(field, models.SmallIntegerField):
        return 'smallint'
    if isinstance(field, (models.AutoField, models.IntegerField)):
        return 'int'
    if isinstance(field, models.FloatField):
        return 'float'
    if isinstance(field, models.DecimalField):
        return f'decimal({field.max_digits},{field.decimal_places})'
    if isinstance(field, models.BooleanField):
        return 'boolean'
    if isinstance(field, models.DateTimeField):
        return 'timestamp'
    if isinstance(field, models.DurationField):
        return 'bigint'
    if isinstance(field, models.DateField):
        return 'date'
    if isinstance(field, models.TimeField):
        return 'time'
    if isinstance(field, models.BinaryField):
        return 'blob'
    if isinstance(field, models.JSONField):
        return 'json'
    if isinstance(field, models.TextField):
        return 'text'
    if isinstance(field, models.UUIDField):
        return 'uuid'
    if isinstance(field, (models.CharField, models.FileField, models.GenericIPAddressField)):
        return f'varchar({field.max_length})' if field.max_length else 'varchar'
    return field.get_internal_type().lower()


def column_settings(field):
    settings = []
    if field.primary_key:
        settings.append('pk')
    if field.unique and not field.primary_key:
        settings.append('unique')
    if not field.null and not field.blank:
        settings.append('not null')
    return f" [{', '.join(settings)}]" if settings else ''


def owner_label(model):
    owner = model._meta.auto_created
    return owner._meta.label if owner else model._meta.label


def group_for(model):
    label = owner_label(model)
    for group_name, labels in GROUP_MODELS.items():
        if label in labels:
            return group_name
    raise RuntimeError(f'No TableGroup configured for {model._meta.label}')


def render_table(model):
    lines = [f'Table {model._meta.db_table} {{']
    for field in model._meta.local_fields:
        lines.append(
            f'  {field.column} {dbml_type(field)}{column_settings(field)}'
        )
    unique_columns = []
    for field_names in model._meta.unique_together:
        unique_columns.append([
            model._meta.get_field(field_name).column for field_name in field_names
        ])
    for constraint in model._meta.constraints:
        if isinstance(constraint, models.UniqueConstraint) and constraint.fields:
            unique_columns.append([
                model._meta.get_field(field_name).column
                for field_name in constraint.fields
            ])
    if unique_columns:
        lines.append('')
        lines.append('  indexes {')
        for columns in unique_columns:
            lines.append(f"    ({', '.join(columns)}) [unique]")
        lines.append('  }')
    lines.append('}')
    return '\n'.join(lines)


def render_ref(model, field):
    target_model = field.remote_field.model
    target_field = field.target_field
    relation = '-' if field.one_to_one else '>'
    return (
        f'Ref: {model._meta.db_table}.{field.column} {relation} '
        f'{target_model._meta.db_table}.{target_field.column}'
    )


def generate_dbml():
    database_models = all_database_models()
    database_model_set = set(database_models)

    grouped_models = OrderedDict((name, []) for name in GROUP_MODELS)
    for model in database_models:
        grouped_models[group_for(model)].append(model)

    blocks = []
    for models_in_group in grouped_models.values():
        blocks.extend(render_table(model) for model in models_in_group)

    refs = []
    for model in database_models:
        for field in model._meta.local_fields:
            if not (field.many_to_one or field.one_to_one):
                continue
            if field.remote_field.model not in database_model_set:
                continue
            refs.append(render_ref(model, field))
    blocks.extend(sorted(set(refs)))

    for group_name, models_in_group in grouped_models.items():
        table_names = '\n'.join(
            f'  {model._meta.db_table}' for model in models_in_group
        )
        blocks.append(f'TableGroup "{group_name}" {{\n{table_names}\n}}')

    return '\n\n'.join(blocks) + '\n'


OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(generate_dbml(), encoding='utf-8')
print(OUTPUT_PATH)
