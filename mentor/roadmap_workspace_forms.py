"""Small, contextual forms for the roadmap authoring workspace."""
from django import forms
from django.db.models import Q
from django.utils.text import slugify

from judge.models import Problem
from judge.widgets import AdminHeavySelect2Widget, AdminMartorWidget, Select2Widget
from mentor.roadmap_models import (
    LearningTopic, NodeProblem, Publication, RoadmapNode, RoadmapPrerequisite,
)


def unique_slug(model, title, **scope):
    base = slugify(title)[:75] or 'chuyen-de'
    candidate, suffix = base, 2
    while model.objects.filter(slug=candidate, **scope).exists():
        candidate = f'{base}-{suffix}'
        suffix += 1
    return candidate


class PlacementForm(forms.ModelForm):
    content_source = forms.ChoiceField(label='Nội dung học', required=False,
        choices=(('new', 'Tạo bộ nội dung riêng (mặc định)'), ('reuse', 'Dùng lại nội dung có sẵn')))
    reuse_topic = forms.ModelChoiceField(label='Bộ nội dung dùng lại', required=False,
        queryset=LearningTopic.objects.none())

    class Meta:
        model = RoadmapNode
        fields = ('title', 'parent', 'difficulty', 'summary', 'display_section', 'icon',
                  'is_optional_review', 'slug')
        labels = {'title': 'Tên nhóm / chuyên đề', 'parent': 'Nằm trong nhóm',
            'difficulty': 'Độ khó', 'summary': 'Mô tả ngắn trên lộ trình',
            'display_section': 'Phân cụm trong nhóm', 'icon': 'Biểu tượng',
            'is_optional_review': 'Chuyên đề ôn tập (không khóa nội dung)', 'slug': 'Mã đường dẫn'}
        widgets = {'summary': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'display_section': 'Các chuyên đề cùng nhóm cha và cùng tên phân cụm sẽ được hiển thị chung. Để trống nếu không cần phân cụm.',
            'is_optional_review': 'Chỉ đánh dấu nội dung ôn tập; không bắt buộc hoàn thành để mở chuyên đề khác.',
            'slug': 'Để trống khi tạo mới để tự sinh. Không đổi mã đường dẫn nếu đang có liên kết sử dụng.'}

    def __init__(self, *args, roadmap, node_type='TOPIC', user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.roadmap = roadmap
        if not self.instance.pk:
            self.instance.type = node_type
        self.fields['slug'].required = bool(self.instance.pk)
        parents = RoadmapNode.objects.filter(roadmap=roadmap)
        if self.instance.pk:
            parents = parents.exclude(pk__in=self.instance.get_descendants(include_self=True).values('pk'))
        self.fields['parent'].queryset = parents.order_by('tree_id', 'lft')
        self.fields['parent'].empty_label = 'Gốc lộ trình'
        self.fields['parent'].widget = Select2Widget()
        self.fields['parent'].label_from_instance = lambda item: '— ' * item.level + item.title
        self.fields['parent'].widget.choices = self.fields['parent'].choices
        if self.instance.pk or self.instance.type == RoadmapNode.Type.GROUP:
            self.fields.pop('content_source')
            self.fields.pop('reuse_topic')
        else:
            self.fields['content_source'].initial = 'new'
            topics = LearningTopic.objects.all()
            if roadmap.organization_id:
                topics = topics.filter(Q(visibility='PUBLIC') | Q(organization_id=roadmap.organization_id))
            else:
                topics = topics.filter(visibility='PUBLIC')
            if not (user.has_perm('mentor.view_learningtopic') or user.has_perm('mentor.change_learningtopic')):
                topics = topics.none()
            self.fields['reuse_topic'].queryset = topics.order_by('name')

    def clean(self):
        data = super().clean()
        if not self.instance.pk and not data.get('slug'):
            data['slug'] = unique_slug(RoadmapNode, data.get('title', ''), roadmap=self.instance.roadmap)
        if data.get('content_source') == 'reuse' and not data.get('reuse_topic'):
            self.add_error('reuse_topic', 'Chọn bộ nội dung cần dùng lại.')
        return data


class TopicIntroductionForm(forms.ModelForm):
    confirm_shared = forms.BooleanField(label='Tôi hiểu thay đổi này áp dụng cho mọi nơi dùng chung nội dung', required=False)

    class Meta:
        model = LearningTopic
        fields = ('name', 'introduction')
        labels = {'name': 'Tên trong thư viện nội dung', 'introduction': 'Giới thiệu chuyên đề'}
        widgets = {'introduction': AdminMartorWidget(attrs={'data-markdownfy-url': '/roadmap/markdown-preview/'})}

    def clean_confirm_shared(self):
        confirmed = self.cleaned_data['confirm_shared']
        if self.instance.pk and self.instance.roadmap_nodes.count() > 1 and not confirmed:
            raise forms.ValidationError('Xác nhận phạm vi ảnh hưởng trước khi lưu nội dung dùng chung.')
        return confirmed


class ProblemLinkForm(forms.ModelForm):
    class Meta:
        model = NodeProblem
        fields = ('problem',)
        labels = {'problem': 'Tìm bài luyện theo mã hoặc tên'}
        widgets = {'problem': AdminHeavySelect2Widget(data_view='problem_select2')}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['problem'].queryset = Problem.get_visible_problems(user)


class PrerequisiteLinkForm(forms.ModelForm):
    class Meta:
        model = RoadmapPrerequisite
        fields = ('prerequisite', 'reason')
        labels = {'prerequisite': 'Nên học chuyên đề này trước', 'reason': 'Vì sao nên học trước?'}
        widgets = {'reason': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, node, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.node = node
        self.fields['prerequisite'].queryset = RoadmapNode.objects.filter(
            roadmap=node.roadmap).exclude(pk=node.pk).order_by('tree_id', 'lft')


class PublicationForm(forms.Form):
    target = forms.ChoiceField(label='Phạm vi thay đổi', choices=())
    status = forms.ChoiceField(label='Trạng thái mới', choices=Publication.choices)
    confirm = forms.BooleanField(label='Tôi đã xem phạm vi ảnh hưởng và muốn áp dụng thay đổi này')

    def __init__(self, *args, node=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('node', 'Chỉ nhóm / chuyên đề này')] if node else [('roadmap', 'Toàn lộ trình')]
        if node and node.learning_topic_id:
            choices.append(('topic', 'Bộ nội dung dùng chung của chuyên đề'))
        self.fields['target'].choices = choices
        self.fields['target'].initial = 'node' if node else 'roadmap'
        self.fields['status'].initial = node.status if node else Publication.DRAFT
