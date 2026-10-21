from django.db import models
from django.db.models import CASCADE, SET_NULL
from django.utils.translation import gettext_lazy as _

from judge.models.problem import Problem, ProblemGroup, ProblemType

__all__ = ['PolygonProblem', 'PolygonTagMapping']


class PolygonProblem(models.Model):
    """A problem known to Polygon and the state of its synchronisation into MSOJ."""

    NEW = 'new'
    SYNCED = 'synced'
    OUTDATED = 'outdated'
    SKIPPED = 'skipped'
    DUPLICATE = 'duplicate'
    CONFLICT = 'conflict'
    FAILED = 'failed'
    STATUS_CHOICES = (
        (NEW, _('Not synced')),
        (SYNCED, _('Synced')),
        (OUTDATED, _('Newer revision available')),
        (SKIPPED, _('Skipped by sync rule')),
        (DUPLICATE, _('Duplicate code')),
        (CONFLICT, _('Code taken by another problem')),
        (FAILED, _('Failed')),
    )

    polygon_id = models.BigIntegerField(verbose_name=_('Polygon problem ID'), unique=True)
    owner = models.CharField(max_length=64, verbose_name=_('Polygon owner'), db_index=True)
    name = models.CharField(max_length=255, verbose_name=_('Polygon problem name'))
    code = models.CharField(max_length=64, blank=True, verbose_name=_('MSOJ problem code'), db_index=True)
    problem = models.OneToOneField(Problem, null=True, blank=True, on_delete=SET_NULL,
                                   related_name='polygon_source', verbose_name=_('MSOJ problem'))
    latest_revision = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('latest package revision'))
    synced_revision = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('synced revision'))
    tags = models.JSONField(default=list, blank=True, verbose_name=_('Polygon tags'))
    tags_revision = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('tags fetched at revision'))
    tags_error = models.TextField(blank=True, verbose_name=_('tag fetch error'))
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=NEW, db_index=True,
                              verbose_name=_('status'))
    message = models.TextField(blank=True, verbose_name=_('last message'))
    last_checked = models.DateTimeField(null=True, blank=True, verbose_name=_('last checked'))
    last_synced = models.DateTimeField(null=True, blank=True, verbose_name=_('last synced'))

    class Meta:
        verbose_name = _('Polygon problem')
        verbose_name_plural = _('Polygon problems')
        ordering = ('-polygon_id',)

    def __str__(self):
        return f'{self.name} ({self.polygon_id})'

    @property
    def needs_sync(self):
        return self.latest_revision is not None and self.synced_revision != self.latest_revision


class PolygonTagMapping(models.Model):
    """Maps a Polygon tag to MSOJ problem type/group used when a problem is synced."""

    tag = models.CharField(max_length=100, unique=True, verbose_name=_('Polygon tag'),
                           help_text=_('Case-insensitive; stored in lowercase.'))
    problem_type = models.ForeignKey(ProblemType, null=True, blank=True, on_delete=CASCADE,
                                     verbose_name=_('problem type'))
    problem_group = models.ForeignKey(ProblemGroup, null=True, blank=True, on_delete=CASCADE,
                                      verbose_name=_('problem group'),
                                      help_text=_('A problem takes the group of its first mapped tag.'))

    class Meta:
        verbose_name = _('Polygon tag mapping')
        verbose_name_plural = _('Polygon tag mappings')
        ordering = ('tag',)

    def save(self, *args, **kwargs):
        self.tag = self.tag.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.tag
