"""Build reproducible beginner packages without touching runtime data."""
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import cast

from . import basics, extra_basics, extra_collections, sequences, structures
from .schema import ProblemSpec

SOURCE = 'MSOJ Beginner Pack 2026-10'
ROADMAP = 'competitive-programming'
SECTIONS = {
    'io': 'Nhập xuất và tính toán cơ bản',
    'conditions': 'Điều kiện và rẽ nhánh',
    'loops': 'Vòng lặp',
    'digits': 'Xử lý chữ số của số nguyên',
    'functions': 'Hàm và tổ chức chương trình',
    'arrays': 'Mảng một chiều và duyệt tuyến tính',
    'frequency': 'Mảng đếm và đánh dấu',
    'strings': 'Ký tự và xâu cơ bản',
    'matrices': 'Mảng hai chiều và bảng số',
    'numbers': 'Số học cơ bản',
}
SECTION_NODES = {
    'io': 'io-basics',
    'conditions': 'conditions',
    'loops': 'loops',
    'digits': 'loops',
    'functions': 'functions',
    'arrays': 'array-basics',
    'frequency': 'array-basics',
    'strings': 'string-basics',
    'matrices': 'matrix-basics',
    'numbers': 'gcd-euclid',
}
TAG_NAMES = {
    'io-basics': 'Nhập xuất và tính toán cơ bản',
    'conditions': 'Điều kiện và rẽ nhánh',
    'loops': 'Vòng lặp',
    'functions': 'Hàm và tổ chức chương trình',
    'array-basics': 'Mảng một chiều',
    'string-basics': 'Ký tự và xâu cơ bản',
    'matrix-basics': 'Mảng hai chiều',
    'arithmetic': 'Phép toán số học',
    'numeric-safety': 'An toàn số học',
    'number-theory': 'Lý thuyết số',
    'divisors': 'Ước và bội',
    'primality': 'Số nguyên tố',
    'modulo': 'Số học modulo (Modular arithmetic)',
    'gcd-euclid': 'Thuật toán Euclid',
}
REUSE = [
    {'code': 'aplusb', 'section': 'io', 'tags': ['io-basics', 'arithmetic'], 'nodes': ['io-basics']},
    {'code': 'maxab', 'section': 'conditions', 'tags': ['conditions'], 'nodes': ['conditions']},
    {'code': 'chon10_cau1', 'section': 'conditions', 'tags': ['conditions', 'numeric-safety'], 'nodes': ['conditions']},
    {'code': 'evenodd', 'section': 'conditions', 'tags': ['conditions', 'loops', 'io-basics'], 'nodes': ['conditions']},
    {'code': 'tristr', 'section': 'loops', 'tags': ['loops'], 'nodes': ['loops']},
    {'code': 'mxar', 'section': 'arrays', 'tags': ['array-basics'], 'nodes': ['array-basics']},
    {'code': 'chon10_cau2', 'section': 'strings', 'tags': ['string-basics'], 'nodes': ['string-basics']},
    {'code': 'alphabet', 'section': 'strings', 'tags': ['string-basics'], 'nodes': ['string-basics']},
    {'code': 'sorry', 'section': 'strings', 'tags': ['string-basics'], 'nodes': ['string-basics']},
    {'code': 'password', 'section': 'strings', 'tags': ['string-basics', 'modulo'], 'nodes': ['string-basics', 'modulo']},
    {'code': 'primes', 'section': 'numbers', 'tags': ['primality', 'number-theory'], 'nodes': ['prime-sieve']},
]


def load_problems() -> list[ProblemSpec]:
    problems = cast(list[ProblemSpec], basics.problems() + sequences.problems() + structures.problems()
                    + extra_basics.problems() + extra_collections.problems())
    section_order = {section: index for index, section in enumerate(SECTIONS)}
    problems.sort(key=lambda problem: section_order[problem['section']])
    seen: set[str] = set()
    for problem in problems:
        code = problem['code']
        if not re.fullmatch(r'msb_[a-z0-9_]{1,28}', code) or code in seen:
            raise ValueError(f'Invalid or repeated problem code: {code}')
        seen.add(code)
        if len(problem['title']) > 100 or problem['section'] not in SECTIONS:
            raise ValueError(f'Invalid metadata: {code}')
        if not problem['nodes'] or not problem['tags']:
            raise ValueError(f'Missing tags or roadmap placements: {code}')
        for field in ('statement', 'explanation', 'cpp'):
            if not problem[field].strip():
                raise ValueError(f'Missing {field}: {code}')
        if '## Dữ liệu vào' not in problem['statement'] or '## Dữ liệu ra' not in problem['statement']:
            raise ValueError(f'Missing input/output specification: {code}')
        problem.setdefault('complexity', '')
        problem['cases'] = list(dict.fromkeys([s['input'] for s in problem['samples']] + problem['cases']))
        if not 10 <= len(problem['cases']) <= 24:
            raise ValueError(f'Expected 10–24 unique cases: {code} ({len(problem["cases"])})')
        for sample in problem['samples']:
            if problem['oracle'](sample['input']).split() != sample['output'].split():
                raise ValueError(f'Sample disagrees with independent oracle: {code}')
    return problems



def statement(problem: ProblemSpec) -> str:
    body = problem['statement'].rstrip()
    for index, sample in enumerate(problem['samples'], 1):
        body += f'\n\n## Ví dụ {index}\n\n### Dữ liệu vào\n\n```\n{sample["input"].rstrip()}\n```'
        body += f'\n\n### Dữ liệu ra\n\n```\n{sample["output"].rstrip()}\n```'
        body += '\n\n**Giải thích:** ' + sample['explanation']
    return body + '\n'


def tutorial(problem: ProblemSpec) -> str:
    body = '## Ý tưởng\n\n' + problem['explanation'].strip()
    if problem['complexity']:
        body += '\n\n## Độ phức tạp\n\n' + problem['complexity']
    if problem['function_practice']:
        body += ('\n\n## Luyện tổ chức hàm\n\n'
                 'Tách thao tác xử lý thành hàm như mã tham khảo. Xác định tham số đầu vào, '
                 'giá trị trả về và các biến cục bộ. Khi truyền số theo giá trị, biến đổi tham số '
                 'trong hàm không làm thay đổi biến ở nơi gọi. Với mảng, dùng tham chiếu const '
                 'nếu hàm chỉ đọc để tránh sao chép. Bộ chấm kiểm tra kết quả, không kiểm tra '
                 'bạn có dùng hàm hay không.')
    return body + '\n\n## Lời giải tham khảo C++17\n\n```cpp\n' + problem['cpp'].rstrip() + '\n```\n'


def test_archive(problem: ProblemSpec) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for index, input_text in enumerate(problem['cases'], 1):
            for suffix, content in [('in', input_text), ('out', problem['oracle'](input_text))]:
                info = zipfile.ZipInfo(f'{index:02d}.{suffix}', date_time=(2026, 10, 24, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content.encode('utf-8'))
    return buffer.getvalue()


def export_problems(directory: str | Path, problems: list[ProblemSpec] | None = None):
    from .validators import validator_source

    problems = load_problems() if problems is None else problems
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = []
    for problem in problems:
        folder = directory / problem['code']
        folder.mkdir(exist_ok=True)
        files = {'statement.md': statement(problem), 'tutorial.md': tutorial(problem),
                 'solution.cpp': problem['cpp'], 'validator.cpp': validator_source(problem)}
        for name, content in files.items():
            (folder / name).write_text(content, encoding='utf-8')
        data = test_archive(problem)
        (folder / 'tests.zip').write_bytes(data)
        metadata = {key: problem[key] for key in ('code', 'title', 'section', 'group', 'tags', 'nodes', 'function_practice')}
        metadata['test_count'] = len(problem['cases'])
        metadata['tests_sha256'] = hashlib.sha256(data).hexdigest()
        (folder / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        manifest.append(metadata)
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest
