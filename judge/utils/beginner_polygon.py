import re
import subprocess
import time

import requests

from judge.utils.polygon_api import API_URL, PolygonAPIError
from judge.fixtures.beginner.schema import ProblemSpec


PACK_MARKER = 'MSOJ beginner pack 2026-10'
TESTSET = 'tests'


def _call_once(client, method: str, **params):
    """Make one signed request; never replay a possibly-mutating Polygon operation."""
    params = {key: str(value).lower() if isinstance(value, bool) else value for key, value in params.items()}
    client._throttle()
    try:
        response = client.session.post(
            API_URL + method, data=client._signed(method, params), timeout=(120, 300)
        )
    except requests.RequestException as exc:
        raise PolygonAPIError(f'{method} request failed ({type(exc).__name__}); not retried') from None
    try:
        if response.status_code >= 500 or response.status_code == 429:
            raise PolygonAPIError(f'{method} returned HTTP {response.status_code}; not retried')
        if method == 'problem.testInput':
            if response.status_code >= 400:
                raise PolygonAPIError(f'{method} returned HTTP {response.status_code}')
            return response.text
        try:
            data = response.json()
        except ValueError:
            raise PolygonAPIError(f'{method} returned HTTP {response.status_code} without JSON') from None
        if data.get('status') != 'OK':
            raise PolygonAPIError(f'{method} failed (HTTP {response.status_code})')
        return data.get('result')
    finally:
        response.close()


def _to_tex(markdown: str) -> str:
    markdown = markdown.replace('~', '$')
    markdown = markdown.replace('≤', r'\le ').replace('≥', r'\ge ')
    try:
        result = subprocess.run(
            ['pandoc', '--from=markdown+tex_math_dollars', '--to=latex', '--no-highlight'],
            input=markdown, text=True, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PolygonAPIError(f'Could not convert Markdown to TeX ({type(exc).__name__})') from None
    return result.stdout.strip()


def _statement_parts(problem: dict):
    parts = re.split(r'^## Dữ liệu vào\s*$|^## Dữ liệu ra\s*$', problem['statement'], flags=re.M)
    if len(parts) != 3:
        raise ValueError(f"{problem['code']}: statement must contain input/output headings")
    return tuple(_to_tex(part.strip()) for part in parts)


def upload_problem(client, problem: ProblemSpec, validator: str, wait_for_package: bool = True) -> dict:
    """Create or safely resume one private MSOJ beginner problem on Polygon."""
    code = problem['code']
    name = code.replace('_', '-')
    candidates = _call_once(client, 'problems.list', name=name) or []
    matches = [item for item in candidates if item.get('name') == name and not item.get('deleted')]
    matches.sort(key=lambda item: item.get('owner') != 'ms24')
    remote = matches[0] if matches else None
    fresh = remote is None
    if fresh:
        remote = _call_once(client, 'problem.create', name=name)
    problem_id = remote.get('id') if isinstance(remote, dict) else None
    if not problem_id:
        raise PolygonAPIError(f'Polygon did not return an id for {name}')
    if fresh:
        _call_once(client, 'problem.saveNote', problemId=problem_id, note=PACK_MARKER)
    else:
        note = _call_once(client, 'problem.note', problemId=problem_id)
        if remote.get('owner') != 'ms24' or remote.get('accessType') not in ('OWNER', 'WRITE'):
            raise PolygonAPIError(f'Refusing to edit Polygon problem {name} without ownership and OWNER/WRITE access')
        if note != PACK_MARKER:
            empty_created = (not note and remote.get('accessType') == 'OWNER'
                             and not _call_once(client, 'problem.tests', problemId=problem_id, testset=TESTSET)
                             and not _call_once(client, 'problem.solutions', problemId=problem_id)
                             and not _call_once(client, 'problem.statements', problemId=problem_id))
            if not empty_created:
                raise PolygonAPIError(f'Refusing to overwrite unmarked Polygon problem {name}')
            _call_once(client, 'problem.saveNote', problemId=problem_id, note=PACK_MARKER)
    common = {'problemId': problem_id}
    _call_once(client, 'problem.updateInfo', **common, timeLimit=2000, memoryLimit=256,
               inputFile='stdin', outputFile='stdout', interactive=False,
               wellFormed=problem['code'] not in ('msb_reversestr', 'msb_wordcount'),
               skipDuplicatedTestsValidation=problem['code'] in ('msb_reversestr', 'msb_wordcount'))
    _call_once(client, 'problem.saveFile', **common, type='source', name='validator.cpp',
               sourceType='cpp.g++17', file=validator)
    _call_once(client, 'problem.setValidator', **common, validator='validator.cpp')
    checker = 'std::fcmp.cpp' if code == 'msb_reversestr' else 'std::wcmp.cpp'
    _call_once(client, 'problem.setChecker', **common, checker=checker)
    _call_once(client, 'problem.saveSolution', **common, name='main.cpp', file=problem['cpp'],
               sourceType='cpp.g++17', tag='MA')

    cases = problem['cases']
    existing_tests = _call_once(client, 'problem.tests', **common, testset=TESTSET) or []
    if any(test.get('index', 0) > len(cases) for test in existing_tests):
        raise PolygonAPIError(f'Refusing to keep unexpected extra tests for {name}')
    sample_by_input = {sample['input']: sample for sample in problem['samples']}
    generated_lines = []
    needs_generator = lambda text: not text.strip() or '  ' in text or text.removesuffix('\n') != text.removesuffix('\n').strip()
    if any(needs_generator(text) for text in cases):
        generator = ('#include <iostream>\n#include <string>\nusing namespace std;\n'
                     'int main(int argc,char** argv){if(argc<2)return 1;string s=argv[1];'
                     'if(s=="words"){for(int i=0;i<50000;++i)cout<<"x ";cout<<"\\n";return 0;}'
                     'for(size_t i=0;i<s.size();i+=2)cout<<char(stoi(s.substr(i,2),nullptr,16));}\n')
        _call_once(client, 'problem.saveFile', **common, type='source', name='genline.cpp',
                   sourceType='cpp.g++17', file=generator)
    for index, input_text in enumerate(cases, 1):
        if needs_generator(input_text):
            previous = next((test for test in existing_tests if test.get('index') == index), None)
            if previous is not None and previous.get('manual'):
                old_input = _call_once(client, 'problem.testInput', **common, testset=TESTSET, testIndex=index)
                if old_input.split() != input_text.split():
                    raise PolygonAPIError(f'Refusing to replace unrelated manual test {index} for {name}')
                _call_once(client, 'problem.deleteTest', **common, testset=TESTSET, testIndex=index)
            argument = 'words' if input_text == 'x ' * 50000 + '\n' else input_text.encode().hex()
            generated_lines.append(f'genline {argument} > {index}')
            continue
        existing = next((test for test in existing_tests if test.get('index') == index), None)
        if existing is not None:
            previous = _call_once(client, 'problem.testInput', **common, testset=TESTSET, testIndex=index)
            if previous.replace('\r\n', '\n') != input_text.replace('\r\n', '\n'):
                raise PolygonAPIError(f'Refusing to replace different existing test {index} for {name}')
            continue
        params = dict(common, testset=TESTSET, testIndex=index, testInput=input_text)
        sample = sample_by_input.get(input_text)
        if sample:
            params.update(testUseInStatements=True, testInputForStatements=sample['input'],
                          testOutputForStatements=sample['output'], verifyInputOutputForStatements=True)
        _call_once(client, 'problem.saveTest', **params)
    if generated_lines:
        _call_once(client, 'problem.saveScript', **common, testset=TESTSET, source='\n'.join(generated_lines))
        for index, input_text in enumerate(cases, 1):
            sample = sample_by_input.get(input_text)
            if needs_generator(input_text) and sample:
                _call_once(client, 'problem.saveTest', **common, testset=TESTSET, testIndex=index,
                           testUseInStatements=True, testInputForStatements=sample['input'],
                           testOutputForStatements=sample['output'], verifyInputOutputForStatements=True)

    tags = list(dict.fromkeys(problem['tags'] + ['msoj-beginner']))
    _call_once(client, 'problem.saveTags', **common, tags=','.join(tags))
    legend, statement_input, statement_output = _statement_parts(problem)
    notes = _to_tex('\n\n'.join(f'Ví dụ {i}: {sample["explanation"]}'
                                for i, sample in enumerate(problem['samples'], 1)))
    from judge.fixtures.beginner.catalog import tutorial as authored_tutorial
    tutorial = _to_tex(authored_tutorial(problem))
    _call_once(client, 'problem.saveStatement', **common, lang='vietnamese', name=problem['title'],
               legend=legend, input=statement_input, output=statement_output, notes=notes, tutorial=tutorial)
    _call_once(client, 'problem.saveGeneralTutorial', **common, tutorial=tutorial)
    _call_once(client, 'problem.commitChanges', **common,
               message='Upload MSOJ beginner pack', minorChanges=True)
    updated = _call_once(client, 'problems.list', id=problem_id) or []
    revision = next((item.get('revision') for item in updated if item.get('id') == problem_id), None)
    _call_once(client, 'problem.buildPackage', **common, full=True, verify=True)
    result = {'id': problem_id, 'name': name,
              'url': f'https://polygon.codeforces.com/problem/{problem_id}',
              'revision': revision, 'package_pending': True, 'tags': tags,
              'test_count': len(cases)}
    if wait_for_package:
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            packages = _call_once(client, 'problem.packages', **common) or []
            ready = [package for package in packages
                     if package.get('type') == 'linux' and package.get('state') == 'READY'
                     and (revision is None or package.get('revision') == revision)]
            if ready:
                package = max(ready, key=lambda item: item.get('id', 0))
                result.update(package_pending=False, package_id=package.get('id'))
                break
            time.sleep(15)
        else:
            raise PolygonAPIError(f'Package build timed out for {name}')
    return result


def refresh_authored_content(client, problem: ProblemSpec) -> dict:
    """Refresh only marked authored metadata and append newly reviewed test cases."""
    from judge.fixtures.beginner.catalog import tutorial as authored_tutorial

    name = problem['code'].replace('_', '-')
    rows = _call_once(client, 'problems.list', name=name) or []
    matches = [p for p in rows if p.get('name') == name and p.get('owner') == 'ms24']
    if len(matches) != 1 or matches[0].get('accessType') not in ('OWNER', 'WRITE'):
        raise PolygonAPIError(f'Expected one owned authored source for {name}')
    remote = matches[0]
    common = {'problemId': remote['id']}
    if _call_once(client, 'problem.note', **common) != PACK_MARKER or remote.get('modified'):
        raise PolygonAPIError(f'Refusing to refresh unmarked or uncommitted source {name}')
    _call_once(client, 'problem.updateInfo', **common,
               wellFormed=problem['code'] not in ('msb_reversestr', 'msb_wordcount'),
               skipDuplicatedTestsValidation=problem['code'] in ('msb_reversestr', 'msb_wordcount'))
    tests = _call_once(client, 'problem.tests', **common, testset=TESTSET) or []
    if len(tests) > len(problem['cases']):
        raise PolygonAPIError(f'Unexpected additional tests for {name}')
    for index in range(len(tests) + 1, len(problem['cases']) + 1):
        _call_once(client, 'problem.saveTest', **common, testset=TESTSET, testIndex=index,
                   testInput=problem['cases'][index - 1])
    legend, statement_input, statement_output = _statement_parts(problem)
    notes = _to_tex('\n\n'.join(f'Ví dụ {i}: {sample["explanation"]}'
                                for i, sample in enumerate(problem['samples'], 1)))
    tutorial = _to_tex(authored_tutorial(problem))
    _call_once(client, 'problem.saveStatement', **common, lang='vietnamese', name=problem['title'],
               legend=legend, input=statement_input, output=statement_output, notes=notes, tutorial=tutorial)
    _call_once(client, 'problem.saveGeneralTutorial', **common, tutorial=tutorial)
    _call_once(client, 'problem.commitChanges', **common, message='Review beginner statements and edge cases', minorChanges=True)
    current = _call_once(client, 'problems.list', id=remote['id']) or []
    revision = next(p['revision'] for p in current if p['id'] == remote['id'])
    _call_once(client, 'problem.buildPackage', **common, full=True, verify=True)
    return {'id': remote['id'], 'name': name, 'revision': revision, 'package_pending': True,
            'test_count': len(problem['cases']), 'tags': problem['tags'] + ['msoj-beginner']}
