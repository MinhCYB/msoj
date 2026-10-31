"""Learning content and the existing Mentor roadmap's tree representation."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

from .roadmap_icons import ICON_CHOICES

class Publication(models.TextChoices):
    DRAFT = 'DRAFT', 'Bản nháp'
    PUBLISHED = 'PUBLISHED', 'Đã xuất bản'


class Visibility(models.TextChoices):
    PUBLIC = 'PUBLIC', 'Công khai'
    ORGANIZATION = 'ORGANIZATION', 'Trong tổ chức'


class PublishedContent(models.Model):
    status = models.CharField(max_length=10, choices=Publication.choices, default=Publication.DRAFT, verbose_name='Trạng thái')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ScopedContent(PublishedContent):
    visibility = models.CharField(max_length=12, choices=Visibility.choices, default=Visibility.PUBLIC, verbose_name='Phạm vi truy cập')
    organization = models.ForeignKey('judge.Organization', null=True, blank=True, on_delete=models.PROTECT, verbose_name='Tổ chức')

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if (self.visibility == Visibility.ORGANIZATION) != bool(self.organization_id):
            raise ValidationError({'organization': 'Organization scope requires exactly one organization.'})


class Roadmap(ScopedContent):
    title = models.CharField(max_length=200, verbose_name='Tên lộ trình')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Mã đường dẫn')
    introduction = models.TextField(blank=True, verbose_name='Giới thiệu')
    tree_revision = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        ordering = ('pk',)
        verbose_name = 'Lộ trình học'
        verbose_name_plural = 'Lộ trình học'
        permissions = [('publish_roadmap', 'Publish learning content and roadmaps')]
        constraints = [
            models.CheckConstraint(check=Q(status__in=Publication.values), name='mentor_roadmap_status'),
            models.CheckConstraint(check=(Q(visibility='PUBLIC', organization__isnull=True) |
                                          Q(visibility='ORGANIZATION', organization__isnull=False)),
                                   name='mentor_roadmap_scope'),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            if self.pk:
                old = type(self).objects.get(pk=self.pk)
                if (old.visibility, old.organization_id) != (self.visibility, self.organization_id):
                    if self.nodes.exists():
                        raise ValidationError('Cannot change the scope of a populated roadmap.')
                self.tree_revision = old.tree_revision + 1
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class LearningTopic(ScopedContent):
    name = models.CharField(max_length=100, verbose_name='Tên bộ nội dung')
    slug = models.SlugField(max_length=100, unique=True, verbose_name='Mã đường dẫn')
    introduction = models.TextField(blank=True, verbose_name='Giới thiệu')
    content_revision = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        ordering = ('name', 'pk')
        verbose_name = 'Bộ nội dung chuyên đề'
        verbose_name_plural = 'Thư viện nội dung'
        constraints = [
            models.CheckConstraint(check=Q(status__in=Publication.values), name='mentor_topic_status'),
            models.CheckConstraint(check=(Q(visibility='PUBLIC', organization__isnull=True) |
                                          Q(visibility='ORGANIZATION', organization__isnull=False)),
                                   name='mentor_topic_scope'),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            if self.pk:
                old = type(self).objects.select_for_update().get(pk=self.pk)
                if (old.visibility, old.organization_id) != (self.visibility, self.organization_id):
                    if self.roadmap_nodes.exists():
                        raise ValidationError('Cannot change the scope of a topic in use.')
                self.content_revision = old.content_revision + 1
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class TopicLesson(PublishedContent):
    topic = models.ForeignKey(LearningTopic, related_name='lessons', on_delete=models.PROTECT, verbose_name='Bộ nội dung')
    title = models.CharField(max_length=200, verbose_name='Tên bài giảng')
    slug = models.SlugField(max_length=100, verbose_name='Mã đường dẫn')
    position = models.PositiveIntegerField(default=0, verbose_name='Thứ tự')
    body = models.TextField(blank=True, verbose_name='Nội dung bài giảng')
    summary = models.TextField(blank=True, default='', verbose_name='Tóm tắt')
    content_revision = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        ordering = ('position', 'pk')
        verbose_name = 'Bài giảng'
        verbose_name_plural = 'Bài giảng'
        constraints = [
            models.UniqueConstraint(fields=('topic', 'slug'), name='mentor_lesson_slug'),
            models.CheckConstraint(check=Q(status__in=Publication.values), name='mentor_lesson_status'),
        ]

    def clean(self):
        super().clean()
        if self.status == Publication.PUBLISHED and not self.body.strip():
            raise ValidationError({'body': 'Published lessons require content.'})
        from .lesson_visuals import validate_visual_blocks
        for field in ('body', 'summary'):
            try:
                validate_visual_blocks(getattr(self, field))
            except ValidationError as exc:
                raise ValidationError({field: exc.messages}) from None

    def save(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            topic_ids = [self.topic_id]
            if self.pk:
                old = type(self).objects.select_for_update().get(pk=self.pk)
                topic_ids.append(old.topic_id)
                self.content_revision = old.content_revision + 1
            list(LearningTopic.objects.select_for_update().filter(pk__in=topic_ids).order_by('pk'))
            self.full_clean()
            super().save(*args, **kwargs)
            LearningTopic.objects.filter(pk__in=topic_ids).update(content_revision=F('content_revision') + 1)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            LearningTopic.objects.select_for_update().get(pk=self.topic_id)
            result = super().delete(*args, **kwargs)
            LearningTopic.objects.filter(pk=self.topic_id).update(content_revision=F('content_revision') + 1)
            return result

    def __str__(self):
        return self.title


def lock_roadmap_forest():
    # MPTT root insertion/moves also change tree_id across roadmaps. Serialize
    # the forest in PK order, not merely the destination roadmap's subtree.
    return list(Roadmap.objects.select_for_update().order_by('pk'))


class RoadmapNode(MPTTModel):
    class Type(models.TextChoices):
        GROUP = 'GROUP', 'Nhóm'
        TOPIC = 'TOPIC', 'Chuyên đề'

    class Difficulty(models.TextChoices):
        BASIC = 'BASIC', 'Cơ bản'
        INTERMEDIATE = 'INTERMEDIATE', 'Trung cấp'
        ADVANCED = 'ADVANCED', 'Nâng cao'

    roadmap = models.ForeignKey(Roadmap, related_name='nodes', on_delete=models.PROTECT)
    parent = TreeForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.PROTECT)
    learning_topic = models.ForeignKey(LearningTopic, null=True, blank=True,
                                      related_name='roadmap_nodes', on_delete=models.PROTECT)
    title = models.CharField(max_length=200, verbose_name='Tiêu đề')
    slug = models.SlugField(max_length=100, verbose_name='Đường dẫn')
    summary = models.TextField(blank=True, default='', verbose_name='Mô tả ngắn')
    display_section = models.CharField(max_length=100, blank=True, default='', verbose_name='Nhóm hiển thị')
    type = models.CharField(max_length=5, choices=Type.choices, default=Type.TOPIC)
    icon = models.CharField(max_length=24, blank=True, default='', choices=ICON_CHOICES,
                            verbose_name='Icon',
                            help_text='Chọn biểu tượng cho thẻ kiến thức. Tự động dùng icon theo nhóm; có thể chọn không hiển thị.')
    position = models.PositiveIntegerField(default=0)
    difficulty = models.CharField(max_length=12, choices=Difficulty.choices, null=True, blank=True)
    status = models.CharField(max_length=10, choices=Publication.choices, default=Publication.DRAFT)
    is_optional_review = models.BooleanField(default=False,
                                            help_text='Optional review node; does not enforce prerequisite gating.')

    class MPTTMeta:
        order_insertion_by = ('position', 'slug')

    class Meta:
        verbose_name = 'Nhóm / chuyên đề'
        verbose_name_plural = 'Cấu trúc lộ trình (nâng cao)'
        index_together = (('tree_id', 'lft'),)
        constraints = [
            models.UniqueConstraint(fields=('roadmap', 'slug'), name='mentor_node_slug'),
            models.CheckConstraint(check=Q(type__in=('GROUP', 'TOPIC')), name='mentor_node_type'),
            models.CheckConstraint(check=Q(status__in=Publication.values), name='mentor_node_status'),
            models.CheckConstraint(check=(Q(difficulty__isnull=True) |
                                          Q(difficulty__in=('BASIC', 'INTERMEDIATE', 'ADVANCED'))),
                                   name='mentor_node_difficulty'),
        ]

    def clean(self):
        super().clean()
        if self.parent_id:
            parent = type(self).objects.filter(pk=self.parent_id).first()
            if parent is None:
                raise ValidationError({'parent': 'Parent does not exist.'})
            if parent.roadmap_id != self.roadmap_id:
                raise ValidationError({'parent': 'Parent must belong to the same roadmap.'})
            if self.pk:
                current = type(self).objects.get(pk=self.pk)
                if parent.pk == self.pk or (parent.tree_id == current.tree_id and
                                           current.lft <= parent.lft <= current.rght):
                    raise ValidationError({'parent': 'A node cannot be moved into its own subtree.'})
        if self.pk and type(self).objects.get(pk=self.pk).roadmap_id != self.roadmap_id:
            raise ValidationError({'roadmap': 'Cross-roadmap moves are not supported.'})
        if self.learning_topic_id:
            topic = LearningTopic.objects.filter(pk=self.learning_topic_id).first()
            roadmap = Roadmap.objects.filter(pk=self.roadmap_id).first()
            if topic is None or roadmap is None:
                raise ValidationError('Topic and roadmap must exist.')
            if topic.visibility == Visibility.ORGANIZATION and (
                    roadmap.visibility != Visibility.ORGANIZATION or
                    topic.organization_id != roadmap.organization_id):
                raise ValidationError({'learning_topic': 'Topic and roadmap scopes are incompatible.'})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            # Refresh structural state: another serialized move may have shifted
            # intervals since this instance was fetched by an admin form.
            if self.pk:
                old = type(self).objects.get(pk=self.pk)
                for name in ('lft', 'rght', 'tree_id', 'level'):
                    setattr(self, name, getattr(old, name))
                self._mptt_cached_fields = old._mptt_cached_fields.copy()
            self._state.fields_cache.pop('parent', None)
            self.full_clean(exclude=('lft', 'rght', 'tree_id', 'level'))
            super().save(*args, **kwargs)
            Roadmap.objects.filter(pk=self.roadmap_id).update(tree_revision=F('tree_revision') + 1)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            self.refresh_from_db()
            result = super().delete(*args, **kwargs)
            Roadmap.objects.filter(pk=self.roadmap_id).update(tree_revision=F('tree_revision') + 1)
            return result

    def __str__(self):
        return self.title


class NodeProblem(models.Model):
    node = models.ForeignKey(RoadmapNode, related_name='problem_links', on_delete=models.CASCADE)
    problem = models.ForeignKey('judge.Problem', related_name='mentor_roadmap_links', on_delete=models.PROTECT)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('position', 'pk')
        verbose_name = 'Liên kết bài luyện'
        verbose_name_plural = 'Liên kết bài luyện (nâng cao)'
        constraints = [models.UniqueConstraint(fields=('node', 'problem'), name='mentor_node_problem')]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            old_node_id = type(self).objects.filter(pk=self.pk).values_list('node_id', flat=True).first() if self.pk else None
            self.full_clean()
            super().save(*args, **kwargs)
            if old_node_id and old_node_id != self.node_id:
                RoadmapNode.objects.get(pk=old_node_id).full_clean(exclude=('lft', 'rght', 'tree_id', 'level'))
            Roadmap.objects.filter(nodes__pk__in=[self.node_id, old_node_id]).distinct().update(
                tree_revision=F('tree_revision') + 1)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            node = RoadmapNode.objects.get(pk=self.node_id)
            result = super().delete(*args, **kwargs)
            node.full_clean()
            Roadmap.objects.filter(pk=node.roadmap_id).update(tree_revision=F('tree_revision') + 1)
            return result

    def __str__(self):
        return f'{self.node} — {self.problem}'


class RoadmapPrerequisite(models.Model):
    node = models.ForeignKey(RoadmapNode, on_delete=models.PROTECT, related_name='prerequisites')
    reason = models.TextField(blank=True, default='', verbose_name='Lý do')
    prerequisite = models.ForeignKey(RoadmapNode, on_delete=models.PROTECT, related_name='required_by')

    class Meta:
        unique_together = ('node', 'prerequisite')
        verbose_name = 'Quan hệ nên học trước'
        verbose_name_plural = 'Quan hệ nên học trước (nâng cao)'

    def clean(self):
        super().clean()
        if not self.node_id or not self.prerequisite_id:
            return
        if self.node_id == self.prerequisite_id:
            raise ValidationError({'prerequisite': 'Một chuyên đề không thể yêu cầu học chính nó trước.'})
        node = RoadmapNode.objects.filter(pk=self.node_id).only('roadmap_id').first()
        prerequisite = RoadmapNode.objects.filter(pk=self.prerequisite_id).only('roadmap_id').first()
        if node is None or prerequisite is None:
            raise ValidationError('Cả hai chuyên đề phải tồn tại.')
        if node.roadmap_id != prerequisite.roadmap_id:
            raise ValidationError({'prerequisite': 'Hai chuyên đề phải thuộc cùng một lộ trình.'})

        # Edges point dependent -> prerequisite. Reject a back-edge.
        adjacency = {}
        links = type(self).objects.filter(node__roadmap_id=node.roadmap_id)
        if self.pk:
            links = links.exclude(pk=self.pk)
        for dependent_id, prerequisite_id in links.values_list('node_id', 'prerequisite_id'):
            adjacency.setdefault(dependent_id, []).append(prerequisite_id)
        pending = [self.prerequisite_id]
        visited = set()
        while pending:
            current = pending.pop()
            if current == self.node_id:
                raise ValidationError({'prerequisite': 'Quan hệ này tạo thành vòng học trước; hãy chọn chuyên đề khác.'})
            if current not in visited:
                visited.add(current)
                pending.extend(adjacency.get(current, ()))

    def save(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            self.full_clean()
            result = super().save(*args, **kwargs)
            Roadmap.objects.filter(nodes__pk__in=(self.node_id, self.prerequisite_id)).distinct().update(
                tree_revision=F('tree_revision') + 1)
            return result

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            lock_roadmap_forest()
            node_ids = (self.node_id, self.prerequisite_id)
            result = super().delete(*args, **kwargs)
            Roadmap.objects.filter(nodes__pk__in=node_ids).distinct().update(tree_revision=F('tree_revision') + 1)
            return result

    def __str__(self):
        return f'{self.node} requires {self.prerequisite}'


class TopicLessonState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_lesson_states')
    lesson = models.ForeignKey(TopicLesson, on_delete=models.CASCADE, related_name='learner_states')
    content_revision = models.PositiveIntegerField()
    offset = models.PositiveIntegerField(default=0)
    position_version = models.PositiveBigIntegerField(default=0)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-last_accessed_at', 'pk')
        verbose_name = 'Tiến độ đọc bài giảng'
        verbose_name_plural = 'Tiến độ đọc (chỉ xem)'
        constraints = [
            models.UniqueConstraint(fields=('user', 'lesson'), name='mentor_lesson_user_state'),
            models.CheckConstraint(check=Q(offset__gte=0, offset__lte=10000), name='mentor_lesson_state_offset_range'),
        ]

    def __str__(self):
        return f'{self.user_id} - {self.lesson_id} (rev {self.content_revision}, offset {self.offset})'


class LessonQARole(models.TextChoices):
    USER = 'user', 'User'
    ASSISTANT = 'assistant', 'Assistant'


class TopicLessonQAMessage(models.Model):
    Role = LessonQARole

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_lesson_qa_messages')
    lesson = models.ForeignKey(TopicLesson, on_delete=models.CASCADE, related_name='qa_messages')
    content_revision = models.PositiveIntegerField()
    role = models.CharField(max_length=10, choices=LessonQARole.choices)
    content = models.TextField()
    section = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'pk')
        verbose_name = 'Hội thoại bài giảng'
        verbose_name_plural = 'Hội thoại bài giảng (chỉ xem)'
        indexes = [
            models.Index(fields=('user', 'lesson', 'content_revision'), name='mentor_qa_user_lesson_rev_idx'),
        ]
        constraints = [
            models.CheckConstraint(check=Q(role__in=('user', 'assistant')), name='mentor_lesson_qa_role_valid'),
        ]

    def __str__(self):
        return f'{self.get_role_display()} on {self.lesson_id} rev {self.content_revision}'


class TopicLessonQAAttempt(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        REJECTED = 'rejected', 'Rejected'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mentor_lesson_qa_attempts')
    lesson = models.ForeignKey(TopicLesson, on_delete=models.CASCADE, related_name='qa_attempts')
    content_revision = models.PositiveIntegerField()
    claim_token = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at', 'pk')
        verbose_name = 'Lần hỏi AI bài giảng'
        verbose_name_plural = 'Lần hỏi AI bài giảng (chỉ xem)'
        indexes = [
            models.Index(fields=('user', 'status'), name='mentor_qa_user_status_idx'),
            models.Index(fields=('user', 'lesson', 'content_revision'), name='mentor_qa_att_user_rev_idx'),
            models.Index(fields=('user', 'created_at'), name='mentor_qa_att_user_time_idx'),
        ]
        constraints = [
            models.CheckConstraint(check=Q(status__in=('active', 'succeeded', 'failed', 'rejected')), name='mentor_lesson_qa_status_valid'),
        ]

    def __str__(self):
        return f'{self.user_id} - {self.lesson_id} rev {self.content_revision} ({self.status})'
