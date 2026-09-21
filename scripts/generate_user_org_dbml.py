from pathlib import Path

from django.apps import apps
from django.db import models


OUTPUT_PATH = Path('docs/msoj-schema-user-org.dbml')
MODEL_LABELS = {
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
}

MODEL_NOTES = {
    'auth.Group': [
        'natural_key(): returns the group name as its natural key.',
    ],
    'auth.Permission': [
        'natural_key(): returns the codename together with the related content type natural key.',
    ],
    'auth.User': [
        'natural_key(): returns username as the natural key.',
        'get_full_name(): combines first_name and last_name.',
        'get_short_name(): returns first_name.',
        'has_perm()/has_perms()/has_module_perms(): resolve permissions from the superuser flag and configured authentication backends.',
        'get_user_permissions()/get_group_permissions()/get_all_permissions(): collect direct, group, or combined permissions.',
    ],
    'judge.Badge': [],
    'judge.Organization': [
        'calculate_points(): computes organization performance points from members ordered by performance_points.',
        'on_user_changes(): recalculates organization points and synchronizes member_count with the members relation.',
        'admins_list: returns all profiles in the admins relation.',
        'is_admin(user): checks whether a profile belongs to admins_list.',
        '__contains__(item): tests organization membership by Profile instance or profile primary key.',
        'notice_hash: returns a shortened SHA-256 hash of notice.',
        'has_credit_left(): checks whether paid_credit plus free_credit is positive.',
        'consume_credit(consumed): deducts free credit first, then paid credit, and updates current_consumed_credit.',
        '_active_quota_agg: sums added_problems and added_storage from quotas active on the current date.',
        'max_problems: adds active quota problem grants to VNOJ_ORGANIZATION_DEFAULT_MAX_PROBLEMS.',
        'max_storage: adds active quota storage grants to VNOJ_ORGANIZATION_DEFAULT_MAX_STORAGE.',
        'current_problem_count: counts available problems owned by the organization.',
        'current_storage: sums ProblemData.zipfile_size for non-deleted organization problems.',
        'can_create_problem(): checks current problem count and storage against both maximums.',
        'can_upload_data(): checks current storage against max_storage.',
    ],
    'judge.OrganizationMonthlyUsage': [],
    'judge.OrganizationQuota': [],
    'judge.OrganizationRequest': [],
    'judge.Profile': [
        'ticket_secret: derives a ticket secret from EVENT_DAEMON_TICKET_KEY and the profile ID.',
        'notification_secret: derives a notification secret from EVENT_DAEMON_NOTIFICATION_KEY and the profile ID.',
        'unread_notification_count: reads or populates a cache with the count of unread notifications.',
        'organization: returns the first organization from the ordered organizations relation, or None.',
        'username: returns user.username.',
        'display_name: returns username_display_override when set, otherwise username.',
        'has_enough_solves: compares problem_count with VNOJ_INTERACT_MIN_PROBLEM_COUNT.',
        'is_new_user: is true for a non-staff user without enough solves.',
        'is_banned: checks that the auth user is inactive and ban_reason is present.',
        'can_be_banned_by(staff): prevents self/superuser bans and requires judge.ban_user.',
        'can_tag_problems: combines allow_tagging with add_tagproblem permission or the configured rating threshold.',
        'resolved_ace_theme: resolves the effective Ace theme from profile preferences and test_site permission.',
        'registered_contest_ids: returns IDs of contests with non-virtual participation.',
        'calculate_points(): updates points, accepted problem_count, and weighted performance_points from public-problem submissions.',
        'calculate_contribution_points(): derives contribution_points from comment scores, blog scores, and contributive tickets.',
        'update_contribution_points(delta): increments and saves contribution_points.',
        'generate_api_token(): creates and stores an HMAC API token and returns its encoded credential.',
        'generate_scratch_codes(): creates and stores TOTP recovery codes.',
        'remove_contest()/update_contest(): clears current_contest directly or when it is ended/inaccessible.',
        'check_totp_code(code): validates a TOTP code and advances last_totp_timecode.',
        'ban_user()/unban_user(): synchronize ban fields, display rank, listing state, and auth user active state.',
        'get_user_css_class(display_rank, rating): combines display rank and rating into the user CSS class.',
        'css_class: derives the display CSS class from display_rank and rating.',
        'webauthn_id: derives a stable WebAuthn identifier from SECRET_KEY and profile ID.',
    ],
    'judge.WebAuthnCredential': [
        'webauthn_user: builds a WebAuthnUser from the profile, credential ID, public key, counter, and RP ID.',
    ],
}


def root_models():
    models_by_label = {
        model._meta.label: model
        for model in apps.get_models()
        if model._meta.label in MODEL_LABELS
    }
    missing = MODEL_LABELS - models_by_label.keys()
    if missing:
        raise RuntimeError(f'Models not found in app registry: {sorted(missing)}')
    return list(models_by_label.values())


def database_models():
    roots = root_models()
    result = set(roots)
    pending = list(roots)
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


def unique_column_sets(model):
    result = [
        [model._meta.get_field(name).column for name in field_names]
        for field_names in model._meta.unique_together
    ]
    result.extend(
        [model._meta.get_field(name).column for name in constraint.fields]
        for constraint in model._meta.constraints
        if isinstance(constraint, models.UniqueConstraint) and constraint.fields
    )
    return result


def note_lines(model):
    if model._meta.auto_created:
        return []
    items = MODEL_NOTES[model._meta.label]
    if not items:
        return ['No business-significant computed property or method is declared on this model.']
    return items


def render_table(model):
    lines = [f'Table {model._meta.db_table} {{']
    for field in model._meta.local_fields:
        lines.append(f'  {field.column} {dbml_type(field)}{column_settings(field)}')

    unique_columns = unique_column_sets(model)
    if unique_columns:
        lines.extend(['', '  indexes {'])
        lines.extend(f"    ({', '.join(columns)}) [unique]" for columns in unique_columns)
        lines.append('  }')

    notes = note_lines(model)
    if notes:
        lines.extend(['', "  Note: '''"])
        lines.extend(f'  {note}' for note in notes)
        lines.append("  '''")

    lines.append('}')
    return '\n'.join(lines)


def render_ref(model, field):
    relation = '-' if field.one_to_one else '>'
    target_model = field.remote_field.model
    return (
        f'Ref: {model._meta.db_table}.{field.column} {relation} '
        f'{target_model._meta.db_table}.{field.target_field.column}'
    )


def generate_dbml():
    selected_models = database_models()
    selected_model_set = set(selected_models)
    blocks = [render_table(model) for model in selected_models]

    refs = {
        render_ref(model, field)
        for model in selected_models
        for field in model._meta.local_fields
        if (field.many_to_one or field.one_to_one)
        and field.remote_field.model in selected_model_set
    }
    blocks.extend(sorted(refs))
    return '\n\n'.join(blocks) + '\n'


OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(generate_dbml(), encoding='utf-8')
print(OUTPUT_PATH)
