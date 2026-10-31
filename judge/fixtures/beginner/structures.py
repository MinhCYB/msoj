"""Original, deterministic beginner string, matrix and arithmetic exercises."""
import math
import random


def _cpp(body, headers=()):
    return '\n'.join('#include <' + h + '>' for h in ('iostream',) + headers) + '\nusing namespace std;\n' + body + '\n'


def _entry(code, title, section, statement, sample, explanation, complexity, cpp, cases, oracle,
           tags, nodes, function_practice=False):
    return dict(code=code, title=title, section=section,
                group='number-theory' if section == 'numbers' else 'foundations',
                statement=statement, samples=[dict(input=sample[0], output=sample[1], explanation=sample[2])],
                explanation=explanation, complexity=complexity, cpp=cpp,
                cases=list(dict.fromkeys([sample[0]] + cases)), oracle=oracle,
                tags=tags, nodes=nodes, function_practice=function_practice)


def _matrix(text):
    values = list(map(int, text.split()))
    n, m = values[:2]
    return [values[2 + i * m:2 + (i + 1) * m] for i in range(n)]


def _matrix_input(a):
    return f'{len(a)} {len(a[0])}\n' + '\n'.join(' '.join(map(str, row)) for row in a) + '\n'


def _rowscols(text):
    a = _matrix(text)
    return ' '.join(str(sum(row)) for row in a) + '\n' + ' '.join(str(sum(col)) for col in zip(*a)) + '\n'


def _diagonals(text):
    values = list(map(int, text.split()))
    n = values[0]
    a = values[1:]
    return f'{sum(a[i * n + i] for i in range(n))} {sum(a[i * n + n - 1 - i] for i in range(n))}\n'


def _border(text):
    a = _matrix(text)
    return str(sum(value for i, row in enumerate(a) for j, value in enumerate(row)
                   if i == 0 or j == 0 or i == len(a) - 1 or j == len(row) - 1)) + '\n'


def _maxpos(text):
    a = _matrix(text)
    maximum = max(map(max, a))
    for i, row in enumerate(a):
        if maximum in row:
            return f'{maximum} {i + 1} {row.index(maximum) + 1}\n'


def _divisors(text):
    n = int(text)
    low, high = [], []
    for d in range(1, math.isqrt(n) + 1):
        if n % d == 0:
            low.append(d)
            if d * d != n:
                high.append(n // d)
    values = low + high[::-1]
    return str(len(values)) + '\n' + ' '.join(map(str, values)) + '\n'


def _prime(text):
    n = int(text)
    return ('YES' if n >= 2 and all(n % d for d in range(2, math.isqrt(n) + 1)) else 'NO') + '\n'


def _gcdlcm(text):
    a, b = map(int, text.split())
    g = math.gcd(a, b)
    return f'{g} {a // g * b}\n'


def _modsum(text):
    values = list(map(int, text.split()))
    return str(sum(values[2:]) % values[1]) + '\n'


def problems():
    rng = random.Random(32024)
    result = []
    strings = ['', 'a', 'aa', 'ab', 'aba', 'abba', 'abcde', 'a b a', '  a ', 'A1b2', '   ', 'ab' * 50000]
    result.append(_entry('msb_reversestr', 'Đảo ngược dòng ký tự', 'strings',
        'Cho một dòng ký tự ~S~. Hãy in các ký tự của dòng theo thứ tự ngược lại. Giữ nguyên mọi dấu cách.\n\n'
        '## Dữ liệu vào\nMột dòng có từ ~0~ đến ~10^5~ ký tự ASCII in được (mã 32 đến 126), không tính ký tự xuống dòng. Dòng có thể rỗng hoặc có dấu cách ở đầu và cuối.\n\n'
        '## Dữ liệu ra\nMột dòng là ~S~ sau khi đảo ngược.\n',
        ('ab cd\n', 'dc ba\n', 'Dấu cách cũng là một ký tự và được giữ trong kết quả.'),
        'Dùng `getline` để đọc cả dòng. Duyệt chỉ số từ cuối dòng về đầu rồi in ký tự tương ứng. '
        'Nếu dòng rỗng, chỉ in xuống dòng. Không dùng phép trừ trên độ dài kiểu không dấu khi độ dài bằng 0.',
        'Thời gian O(|S|), bộ nhớ O(|S|) để lưu dòng.',
        _cpp('int main() {\n    string s;\n    getline(cin, s);\n    for (int i = static_cast<int>(s.size()) - 1; i >= 0; --i) cout << s[i];\n    cout << "\\n";\n}', ('string',)),
        [s + '\n' for s in strings], lambda t: t.removesuffix('\n')[::-1] + '\n',
        ['string-basics'], ['string-basics']))
    result.append(_entry('msb_palinstr', 'Xâu đối xứng', 'strings',
        'Một xâu đối xứng đọc từ trái sang phải giống như từ phải sang trái. Hãy kiểm tra xâu ~S~ có đối xứng hay không.\n\n'
        '## Dữ liệu vào\nMột dòng chứa xâu ~S~ chỉ gồm chữ cái tiếng Anh in thường, ~1 \\le |S| \\le 10^5~.\n\n'
        '## Dữ liệu ra\nIn `YES` nếu xâu đối xứng, ngược lại in `NO`.\n',
        ('abacaba\n', 'YES\n', 'Các cặp ký tự cách đều hai đầu đều giống nhau.'),
        'So sánh ký tự tại vị trí i với ký tự tại vị trí |S|-1-i. Chỉ cần xét nửa đầu. '
        'Một ký tự luôn tạo thành xâu đối xứng; cần kiểm tra cả độ dài chẵn lẫn lẻ.',
        'Thời gian O(|S|), bộ nhớ O(|S|) để lưu xâu.',
        _cpp('int main() {\n    string s; cin >> s;\n    bool ok = true;\n    for (int i = 0; i < static_cast<int>(s.size()) / 2; ++i) {\n        if (s[i] != s[s.size() - 1 - i]) ok = false;\n    }\n    cout << (ok ? "YES" : "NO") << "\\n";\n}', ('string',)),
        [s + '\n' for s in ['a', 'aa', 'ab', 'aba', 'abba', 'abca', 'abcba', 'aab', 'baa', 'a' * 100000, 'a' * 99999 + 'b']],
        lambda t: ('YES' if t.strip() == t.strip()[::-1] else 'NO') + '\n',
        ['string-basics'], ['string-basics']))
    lines = ['', ' ', 'a', ' a', 'a ', ' a ', 'a  b', '   a   b   c  ', 'hello world', 'one    two', 'x ' * 50000]
    result.append(_entry('msb_wordcount', 'Đếm từ trong dòng', 'strings',
        'Một từ là một nhóm chữ cái liên tiếp, được ngăn với từ khác bởi một hoặc nhiều dấu cách. Hãy đếm số từ trong một dòng.\n\n'
        '## Dữ liệu vào\nMột dòng dài từ ~0~ đến ~10^5~ ký tự, chỉ gồm chữ cái tiếng Anh và dấu cách ASCII (mã 32). Có thể có dấu cách đầu/cuối dòng hoặc dòng rỗng.\n\n'
        '## Dữ liệu ra\nMột số nguyên là số từ trong dòng.\n',
        ('  Hoc   lap trinh  \n', '3\n', 'Ba từ là Hoc, lap và trinh; các dấu cách thừa không tạo thêm từ.'),
        'Một từ bắt đầu tại ký tự khác dấu cách nếu đó là ký tự đầu dòng hoặc ký tự ngay trước là dấu cách. '
        'Đếm các vị trí bắt đầu từ. Cách này xử lý được dòng rỗng và nhiều dấu cách liên tiếp.',
        'Thời gian O(|S|), bộ nhớ O(|S|) để lưu dòng.',
        _cpp('int main() {\n    string s; getline(cin, s);\n    int count = 0;\n    for (int i = 0; i < static_cast<int>(s.size()); ++i) {\n        if (s[i] != \' \' && (i == 0 || s[i - 1] == \' \')) ++count;\n    }\n    cout << count << "\\n";\n}', ('string',)),
        [s + '\n' for s in lines], lambda t: str(len(t.split())) + '\n',
        ['string-basics'], ['string-basics']))

    matrices = [[[0]], [[-7]], [[5, -2, 5]], [[1], [-2], [3]], [[1, 2], [3, 4]],
                [[-1, -2], [-3, -4]], [[9, 9], [9, 9]], [[1, 2, 3], [4, 5, 6]],
                [[0] * 4 for _ in range(3)], [[10**9] * 200 for _ in range(200)]]
    matrices += [[[rng.randint(-100, 100) for _ in range(m)] for _ in range(n)]
                 for n, m in [(2, 3), (3, 2), (5, 7), (7, 5)]]
    matrix_limits = ('## Dữ liệu vào\nDòng đầu chứa hai số nguyên ~n, m~ (~1 \\le n,m \\le 200~). '
                     'Tiếp theo là ~n~ dòng, mỗi dòng chứa ~m~ số nguyên ~a_{ij}~, ~|a_{ij}| \\le 10^9~.\n\n')
    matrix_tags = ['matrix-basics', 'numeric-safety']
    result.append(_entry('msb_rowscols', 'Tổng theo hàng và cột', 'matrices',
        'Cho bảng số có ~n~ hàng và ~m~ cột. Tính tổng các phần tử trên từng hàng và từng cột.\n\n' + matrix_limits +
        '## Dữ liệu ra\nDòng đầu in ~n~ tổng hàng theo thứ tự từ trên xuống. Dòng thứ hai in ~m~ tổng cột từ trái sang phải. Các số trên cùng dòng cách nhau bởi dấu cách.\n',
        ('2 3\n1 2 3\n4 5 6\n', '6 15\n5 7 9\n', 'Hàng đầu có tổng 6, hàng sau có tổng 15; cột đầu có tổng 1+4=5.'),
        'Duyệt từng ô khi đọc dữ liệu, cộng giá trị vào tổng của hàng và cột tương ứng. '
        'Không cần lưu toàn bộ bảng. Dùng long long vì tổng một hàng có thể tới ~2 \\times 10^{11}~.',
        'Thời gian O(nm), bộ nhớ O(n+m).',
        _cpp('int main() {\n    int n, m; cin >> n >> m;\n    vector<long long> rows(n, 0), cols(m, 0);\n    for (int i = 0; i < n; ++i) for (int j = 0; j < m; ++j) {\n        long long x; cin >> x; rows[i] += x; cols[j] += x;\n    }\n    for (int i = 0; i < n; ++i) cout << (i ? " " : "") << rows[i];\n    cout << "\\n";\n    for (int j = 0; j < m; ++j) cout << (j ? " " : "") << cols[j];\n    cout << "\\n";\n}', ('vector',)),
        [_matrix_input(a) for a in matrices], _rowscols, matrix_tags, ['matrix-basics']))
    square_sizes = [1, 2, 3, 4, 5, 7, 9, 20, 50, 200]
    square_inputs = [str(n) + '\n' + '\n'.join(' '.join(str(rng.randint(-10**9, 10**9)) for _ in range(n)) for _ in range(n)) + '\n' for n in square_sizes]
    result.append(_entry('msb_diagonals', 'Hai đường chéo', 'matrices',
        'Cho bảng vuông ~n \\times n~. Tính riêng tổng các phần tử trên đường chéo chính và đường chéo phụ. Ô chính giữa, nếu có, được tính trong cả hai tổng.\n\n'
        '## Dữ liệu vào\nDòng đầu chứa ~n~ (~1 \\le n \\le 200~). Tiếp theo là ~n~ dòng, mỗi dòng có ~n~ số nguyên ~a_{ij}~, ~|a_{ij}| \\le 10^9~.\n\n'
        '## Dữ liệu ra\nIn hai số: tổng đường chéo chính rồi tổng đường chéo phụ.\n',
        ('3\n1 2 3\n4 5 6\n7 8 9\n', '15 15\n', 'Đường chéo chính gồm 1,5,9; đường chéo phụ gồm 3,5,7.'),
        'Với chỉ số bắt đầu từ 0, đường chéo chính có i=j, đường chéo phụ có i+j=n-1. '
        'Dùng hai câu if độc lập, không dùng else if: ô giữa của bảng kích thước lẻ thuộc cả hai đường chéo.',
        'Thời gian O(n²) để đọc bảng, bộ nhớ phụ O(1).',
        _cpp('int main() {\n    int n; cin >> n; long long mainSum = 0, otherSum = 0;\n    for (int i = 0; i < n; ++i) for (int j = 0; j < n; ++j) {\n        long long x; cin >> x;\n        if (i == j) mainSum += x;\n        if (i + j == n - 1) otherSum += x;\n    }\n    cout << mainSum << " " << otherSum << "\\n";\n}'),
        square_inputs, _diagonals, matrix_tags, ['matrix-basics']))
    result.append(_entry('msb_border', 'Tổng các ô ở biên', 'matrices',
        'Cho bảng ~n~ hàng, ~m~ cột. Một ô ở biên nếu thuộc hàng đầu, hàng cuối, cột đầu hoặc cột cuối. Tính tổng các ô ở biên, mỗi ô chỉ tính một lần.\n\n' + matrix_limits +
        '## Dữ liệu ra\nMột số nguyên là tổng các ô ở biên.\n',
        ('3 3\n1 2 3\n4 100 6\n7 8 9\n', '40\n', 'Chỉ ô giữa có giá trị 100 không thuộc biên.'),
        'Duyệt mỗi ô đúng một lần. Nếu ít nhất một trong bốn điều kiện biên đúng, cộng giá trị của ô. '
        'Không cộng riêng từng cạnh vì sẽ đếm lặp góc và sai khi bảng chỉ có một hàng hoặc một cột.',
        'Thời gian O(nm), bộ nhớ phụ O(1).',
        _cpp('int main() {\n    int n, m; cin >> n >> m; long long sum = 0;\n    for (int i = 0; i < n; ++i) for (int j = 0; j < m; ++j) {\n        long long x; cin >> x;\n        if (i == 0 || i == n - 1 || j == 0 || j == m - 1) sum += x;\n    }\n    cout << sum << "\\n";\n}'),
        [_matrix_input(a) for a in matrices], _border, matrix_tags, ['matrix-basics']))
    result.append(_entry('msb_matrixmax', 'Vị trí lớn nhất trong bảng', 'matrices',
        'Tìm giá trị lớn nhất trong bảng và vị trí đầu tiên đạt giá trị đó khi duyệt từ trên xuống, trong mỗi hàng từ trái sang phải. Hàng và cột được đánh số từ 1.\n\n' + matrix_limits +
        '## Dữ liệu ra\nIn ba số: giá trị lớn nhất, số hàng và số cột của vị trí được chọn.\n',
        ('2 3\n2 9 1\n9 3 9\n', '9 1 2\n', 'Có ba ô bằng 9; ô hàng 1 cột 2 xuất hiện trước khi duyệt theo hàng.'),
        'Khởi tạo đáp án bằng ô đầu tiên, không dùng 0 vì toàn bộ bảng có thể âm. '
        'Chỉ cập nhật khi gặp giá trị lớn hơn hẳn, nhờ đó giữ được vị trí đầu tiên khi có nhiều cực đại.',
        'Thời gian O(nm), bộ nhớ phụ O(1).',
        _cpp('int main() {\n    int n, m; cin >> n >> m;\n    long long best = 0; int row = 1, col = 1;\n    for (int i = 1; i <= n; ++i) for (int j = 1; j <= m; ++j) {\n        long long x; cin >> x;\n        if ((i == 1 && j == 1) || x > best) { best = x; row = i; col = j; }\n    }\n    cout << best << " " << row << " " << col << "\\n";\n}'),
        [_matrix_input(a) for a in matrices], _maxpos,
        ['matrix-basics'], ['matrix-basics']))

    result.append(_entry('msb_divisors', 'Liệt kê các ước dương', 'numbers',
        'Cho số nguyên dương ~n~. Hãy đếm và liệt kê tất cả các ước dương của ~n~ theo thứ tự tăng dần.\n\n'
        '## Dữ liệu vào\nMột số nguyên ~n~, ~1 \\le n \\le 10^5~.\n\n'
        '## Dữ liệu ra\nDòng đầu in số ước dương. Dòng thứ hai in các ước theo thứ tự tăng dần, cách nhau bởi dấu cách.\n',
        ('12\n', '6\n1 2 3 4 6 12\n', 'Sáu số được liệt kê đều chia 12 không dư.'),
        'Duyệt d từ 1 đến n; d là ước khi n%d bằng 0. Đếm ở lượt đầu và in các ước ở lượt sau. '
        'Giới hạn cho phép hai lượt duyệt đơn giản; không cần lưu danh sách. Số 1 có đúng một ước là 1.',
        'Thời gian O(n), bộ nhớ phụ O(1).',
        _cpp('int main() {\n    int n; cin >> n; int count = 0;\n    for (int d = 1; d <= n; ++d) if (n % d == 0) ++count;\n    cout << count << "\\n";\n    bool first = true;\n    for (int d = 1; d <= n; ++d) if (n % d == 0) {\n        if (!first) cout << " ";\n        cout << d; first = false;\n    }\n    cout << "\\n";\n}'),
        [str(n) + '\n' for n in [1, 2, 3, 4, 6, 12, 16, 25, 36, 97, 99991, 100000]],
        _divisors, ['number-theory', 'divisors', 'loops'], ['arithmetic-functions', 'loops']))
    result.append(_entry('msb_prime', 'Kiểm tra một số nguyên tố', 'numbers',
        'Số nguyên tố là số nguyên lớn hơn 1 chỉ có hai ước dương là 1 và chính nó. Kiểm tra số ~n~ có phải số nguyên tố hay không.\n\n'
        '## Dữ liệu vào\nMột số nguyên ~n~, ~0 \\le n \\le 10^9~.\n\n'
        '## Dữ liệu ra\nIn `YES` nếu ~n~ là số nguyên tố, ngược lại in `NO`.\n',
        ('29\n', 'YES\n', '29 không chia hết cho số nguyên nào từ 2 đến 5, nên là số nguyên tố.'),
        'Tách hàm `isPrime(n)` trả về bool: `n < 2` thì trả false; thử các ước từ 2 trong khi `d * d <= n`. '
        'Nếu n có ước khác 1 và chính nó thì ít nhất một ước không lớn hơn căn bậc hai của n. '
        'Biến d chỉ thuộc phạm vi hàm; main đọc n, gọi hàm và in kết quả. Dùng `1LL * d * d` để tính tích bằng kiểu 64 bit.',
        'Thời gian O(√n), bộ nhớ phụ O(1).',
        _cpp('bool isPrime(int n) {\n    if (n < 2) return false;\n    for (int d = 2; 1LL * d * d <= n; ++d) if (n % d == 0) return false;\n    return true;\n}\nint main() {\n    int n; cin >> n;\n    cout << (isPrime(n) ? "YES" : "NO") << "\\n";\n}'),
        [str(n) + '\n' for n in [0, 1, 2, 3, 4, 9, 25, 49, 97, 99991, 999800009, 999999937, 1000000000]],
        _prime, ['number-theory', 'primality', 'functions', 'loops'], ['prime-sieve', 'functions'], True))
    gcd_cases = [(1, 1), (1, 10**9), (10**9, 1), (12, 18), (18, 12), (7, 13), (24, 24),
                 (10**9, 10**9), (999999937, 999999929), (1024, 64), (123456789, 987654321)]
    result.append(_entry('msb_gcdlcm', 'Ước chung lớn nhất và bội chung nhỏ nhất', 'numbers',
        'Cho hai số nguyên dương ~a,b~. Tính ước chung lớn nhất (ƯCLN) và bội chung nhỏ nhất (BCNN) của chúng.\n\n'
        '## Dữ liệu vào\nHai số nguyên ~a,b~, ~1 \\le a,b \\le 10^9~.\n\n'
        '## Dữ liệu ra\nIn ƯCLN rồi BCNN trên cùng một dòng, cách nhau bởi dấu cách.\n',
        ('12 18\n', '6 36\n', 'Ước chung lớn nhất là 6; số dương nhỏ nhất chia hết cho cả 12 và 18 là 36.'),
        'Viết hàm `gcd(a,b)` theo Euclid: liên tục thay (a,b) bằng (b,a%b) đến khi b=0, rồi trả về a. '
        'Hai tham số truyền theo giá trị nên thay đổi trong hàm không làm mất a,b ban đầu của main. '
        'BCNN bằng `a / ƯCLN * b`. Chia trước nhân và dùng long long để lưu kết quả tới ~10^{18}~.',
        'Thời gian O(log(min(a,b))), bộ nhớ phụ O(1).',
        _cpp('long long gcd(long long a, long long b) {\n    while (b != 0) { long long r = a % b; a = b; b = r; }\n    return a;\n}\nint main() {\n    long long a, b; cin >> a >> b;\n    long long g = gcd(a, b);\n    cout << g << " " << a / g * b << "\\n";\n}'),
        [f'{a} {b}\n' for a, b in gcd_cases], _gcdlcm,
        ['number-theory', 'gcd-euclid', 'functions', 'numeric-safety'], ['gcd-euclid', 'functions'], True))
    mod_cases = ['1 1\n0\n', '1 7\n7\n', '1 7\n6\n', '2 7\n6 1\n', '3 10\n0 0 0\n',
                 '3 10\n11 12 13\n', '2 1000000000\n1000000000 1000000000\n',
                 '4 2\n1 1 1 1\n', '5 3\n1 2 3 4 5\n',
                 '100000 999999937\n' + ' '.join(['1000000000'] * 100000) + '\n']
    result.append(_entry('msb_modsum', 'Phần dư của tổng', 'numbers',
        'Cho ~n~ số nguyên không âm và số nguyên dương ~m~. Tính phần dư khi chia tổng các số đã cho cho ~m~.\n\n'
        '## Dữ liệu vào\nDòng đầu chứa ~n,m~ (~1 \\le n \\le 10^5~, ~1 \\le m \\le 10^9~). '
        'Dòng thứ hai chứa ~n~ số nguyên ~a_i~, ~0 \\le a_i \\le 10^9~.\n\n'
        '## Dữ liệu ra\nMột số nguyên trong đoạn từ 0 đến m-1 là phần dư cần tìm.\n',
        ('3 7\n5 6 8\n', '5\n', 'Tổng bằng 19, chia 7 có phần dư 5.'),
        'Sau mỗi số x, cập nhật remainder=(remainder+x)%m. Bất biến: remainder luôn là phần dư của tổng các số đã đọc. '
        'Dùng long long cho phép cộng và nhớ trường hợp m=1 cho kết quả 0. Không cần lưu mảng.',
        'Thời gian O(n), bộ nhớ phụ O(1).',
        _cpp('int main() {\n    int n; long long m; cin >> n >> m; long long remainder = 0;\n    for (int i = 0; i < n; ++i) { long long x; cin >> x; remainder = (remainder + x) % m; }\n    cout << remainder << "\\n";\n}'),
        mod_cases, _modsum, ['number-theory', 'modulo', 'loops'], ['modulo', 'loops']))
    return result
