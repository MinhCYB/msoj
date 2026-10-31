"""Create independent draft examples without overwriting existing authored content."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse

from mentor.lesson_visuals import validate_visual_blocks
from mentor.roadmap_models import LearningTopic, Publication, Roadmap, TopicLesson
from mentor.roadmap_services import create_node, save_content

SAMPLES = (
    ('for-loop', 'Vòng for và bảng biến', 'Theo dõi điều kiện, biến điều khiển và tổng tích lũy.'),
    ('bfs', 'BFS và hàng đợi', 'Khám phá đồ thị theo lớp và truy vết đường đi ngắn nhất.'),
    ('dp-bitmask-matching', 'DP bitmask ghép đôi', 'Khám phá ý nghĩa trạng thái và những cách ghép được đếm.'),
    ('chart-table', 'Biểu đồ và bảng dữ liệu', 'Đọc dữ liệu qua hai cách biểu diễn đồng bộ.'),
    ('prefix-sum', 'Tổng tiền tố', 'Liên kết lựa chọn một đoạn với tổng tiền tố và tổng đoạn.'),
    ('scene-geometry', 'Hình học: đoạn thẳng', 'Di chuyển một điểm và quan sát đoạn thẳng đi theo.'),
)
SLUG = 'interactive-lessons'


class Command(BaseCommand):
    help = 'Preview/create six draft examples in a separate roadmap; never overwrites content.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--development', action='store_true')
        parser.add_argument('--user')

    def handle(self, *args, **options):
        payloads = []
        for slug, title, summary in SAMPLES:
            body = (Path(__file__).resolve().parents[2] / 'interactive_samples' / (slug + '.md')).read_text(encoding='utf-8')
            validate_visual_blocks(body)
            payloads.append((slug, title, summary, body))
        if not options['apply']:
            self.stdout.write(f'DRY-RUN: ensure {len(payloads)} draft examples; existing content stays unchanged.')
            return
        database = settings.DATABASES['default']
        if not options['development'] or not settings.DEBUG or database.get('HOST', '') not in ('', 'localhost', '127.0.0.1', '::1'):
            raise CommandError('Writes require --development, DEBUG=True and a local database.')
        user = get_user_model().objects.filter(username=options['user'], is_staff=True, is_active=True).first()
        permissions = tuple('mentor.add_' + name for name in ('roadmap', 'roadmapnode', 'learningtopic', 'topiclesson'))
        if user is None or not user.has_perms(permissions):
            raise CommandError('--apply needs active staff content-authoring permissions.')
        with transaction.atomic():
            roadmap = Roadmap.objects.select_for_update().filter(slug=SLUG).first()
            nodes = {node.slug: node for node in roadmap.nodes.select_related('learning_topic')} if roadmap else {}
            wanted = {item[0] for item in payloads}
            if not set(nodes).issubset(wanted):
                raise CommandError('Sample roadmap has unknown nodes; refusing to modify it.')
            for node in nodes.values():
                if not node.learning_topic_id or not node.learning_topic.lessons.filter(slug='interactive-example').exists():
                    raise CommandError('Existing sample is incomplete; refusing to overwrite it.')
            missing = [item for item in payloads if item[0] not in nodes]
            if LearningTopic.objects.filter(slug__in=['interactive-' + item[0] for item in missing]).exists():
                raise CommandError('A sample topic slug is already in use; refusing to overwrite it.')
            if roadmap is None:
                roadmap = save_content(user, Roadmap(title='Bài học tương tác — bản mẫu', slug=SLUG,
                    introduction='Các ví dụ trực quan để duyệt trước khi xuất bản.', status=Publication.DRAFT))
            for slug, title, summary, body in missing:
                topic = save_content(user, LearningTopic(name=title, slug='interactive-' + slug,
                    introduction=summary, status=Publication.DRAFT))
                node = create_node(user, roadmap=roadmap, title=title, slug=slug, position=len(nodes),
                    learning_topic=topic, summary=summary, status=Publication.DRAFT)
                save_content(user, TopicLesson(topic=topic, title=title, slug='interactive-example',
                    summary=summary, body=body, status=Publication.DRAFT))
                nodes[slug] = node
            self.stdout.write(self.style.SUCCESS(f'Added {len(missing)} draft examples; existing content preserved.'))
            self.stdout.write(reverse('admin:mentor_roadmap_workspace', args=[roadmap.pk]))
            for node in nodes.values():
                lesson = node.learning_topic.lessons.get(slug='interactive-example')
                self.stdout.write(reverse('admin:mentor_roadmap_preview', args=[roadmap.pk]) + f'?node={node.pk}&lesson={lesson.pk}')
