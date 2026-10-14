"""Bundled Font Awesome 4 icons for knowledge cards; no user-provided markup."""
ICON_CHOICES = (
    ('', 'Tự động theo nhóm kiến thức'),
    ('none', 'Không hiển thị icon'),
    ('fa-code', 'Lập trình — Code'),
    ('fa-puzzle-piece', 'Kỹ thuật thuật toán — Puzzle'),
    ('fa-database', 'Cấu trúc dữ liệu — Database'),
    ('fa-calculator', 'Toán học — Calculator'),
    ('fa-cubes', 'Quy hoạch động — Cubes'),
    ('fa-share-alt', 'Đồ thị — Graph'),
    ('fa-sitemap', 'Cây — Sitemap'),
    ('fa-font', 'Xâu ký tự — Text'),
    ('fa-area-chart', 'Hình học — Geometry'),
    ('fa-exchange', 'Luồng và cặp ghép — Flow'),
    ('fa-gamepad', 'Lý thuyết trò chơi — Game'),
    ('fa-search', 'Tìm kiếm — Search'),
    ('fa-trophy', 'Thi đấu — Trophy'),
    ('fa-folder-open', 'Nhóm kiến thức — Folder'),
    ('fa-book', 'Chuyên đề — Book'),
    ('fa-terminal', 'Nhập xuất — Terminal'),
    ('fa-list', 'Dãy và danh sách — List'),
    ('fa-code-fork', 'Phân nhánh — Branch'),
    ('fa-repeat', 'Lặp và đệ quy — Repeat'),
)
ICON_CLASSES = frozenset(value for value, _ in ICON_CHOICES if value.startswith('fa-'))
GROUP_ICONS = {
    'foundations': 'fa-code',
    'basic-algorithms': 'fa-puzzle-piece',
    'data-structures': 'fa-database',
    'number-theory': 'fa-calculator',
    'dynamic-programming': 'fa-cubes',
    'graphs': 'fa-share-alt',
    'trees': 'fa-sitemap',
    'strings': 'fa-font',
    'geometry': 'fa-area-chart',
    'games': 'fa-gamepad',
    'advanced-search': 'fa-search',
    'flow-matching': 'fa-exchange',
    'contest-skills': 'fa-trophy',
}


def resolve_node_icon(icon: str, slug: str, node_type: str) -> str:
    if icon == 'none':
        return ''
    if icon in ICON_CLASSES:
        return icon
    if node_type == 'GROUP':
        return GROUP_ICONS.get(slug, 'fa-folder-open')
    return 'fa-book'
