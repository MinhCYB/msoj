import random
from math import isqrt


def problems():
    result = []
    rng = random.Random(2401)

    def add(code, title, section, group, tags, nodes, statement, samples,
            explanation, complexity, cpp, oracle, extra_cases):
        result.append({
            "code": code,
            "title": title,
            "section": section,
            "group": group,
            "tags": tags,
            "nodes": nodes,
            "statement": statement,
            "samples": samples,
            "explanation": explanation,
            "complexity": complexity,
            "cpp": cpp,
            "cases": [sample["input"] for sample in samples] + extra_cases,
            "oracle": oracle,
            "function_practice": False,
        })

    array_nodes = ["arrays-and-strings"]
    array_tags = ["arrays-and-strings", "array-basics"]
    reverse_samples = [
        {"input": "5\n1 2 3 4 5\n", "output": "5 4 3 2 1\n", "explanation": "Các phần tử được in theo thứ tự từ cuối về đầu."},
        {"input": "1\n-7\n", "output": "-7\n", "explanation": "Mảng có một phần tử nên thứ tự không thay đổi."},
    ]
    reverse_cpp = "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    vector<int> values(n);\n    for (int& value : values) cin >> value;\n    for (auto it = values.rbegin(); it != values.rend(); ++it) {\n        if (it != values.rbegin()) cout << ' ';\n        cout << *it;\n    }\n    cout << '\\n';\n    return 0;\n}\n"
    reverse_oracle = lambda s: " ".join(map(str, map(int, s.split()[1:][::-1]))) + "\n"
    reverse_statement = """Dòng đầu gồm số nguyên ~n~; dòng tiếp theo gồm ~n~ số nguyên có dấu ~a_i~. Hãy in các phần tử theo thứ tự ngược lại, từ phần tử cuối đến phần tử đầu.

## Dữ liệu vào
Dòng đầu gồm số nguyên ~n~. Dòng thứ hai gồm ~n~ số nguyên ~a_i~.

~1 ≤ n ≤ 10^5~, ~|a_i| ≤ 10^9~.

## Dữ liệu ra
In các phần tử theo thứ tự ngược lại trên một dòng, cách nhau bởi một dấu cách."""
    reverse_extras = ["1\n0\n", "2\n-1000000000 1000000000\n", "4\n0 0 0 0\n", "5\n-1 -2 -3 -4 -5\n", "6\n1 -1 2 -2 3 -3\n", "7\n7 6 5 4 3 2 1\n", "3\n1000000000 0 -1000000000\n", "8\n2 2 1 1 0 0 -1 -1\n"]
    reverse_values = [rng.randint(-10**9, 10**9) for _ in range(32)]
    reverse_extras.append(f"{len(reverse_values)}\n{' '.join(map(str, reverse_values))}\n")
    reverse_max = [rng.randint(-10**9, 10**9) for _ in range(100000)]
    reverse_extras.append(f"100000\n{' '.join(map(str, reverse_max))}\n")
    add("msb_reversearray", "In mảng theo thứ tự ngược", "arrays", "foundations", array_tags, array_nodes, reverse_statement, reverse_samples,
        "Duyệt mảng từ phần tử cuối về đầu và in trực tiếp, không cần tạo thêm mảng đảo.", "~O(n)~ thời gian, ~O(n)~ bộ nhớ để lưu mảng.", reverse_cpp, reverse_oracle, reverse_extras)

    frequency_tags = ["arrays-and-strings", "frequency-array"]
    freq_statement = """Dòng đầu gồm số nguyên ~n~; dòng tiếp theo gồm ~n~ số nguyên ~a_i~ trong đoạn từ 0 đến 1000. Hãy tìm số nguyên không âm nhỏ nhất không xuất hiện trong dãy.

## Dữ liệu vào
Dòng đầu gồm số nguyên ~n~. Dòng thứ hai gồm ~n~ số nguyên ~a_i~.

~1 ≤ n ≤ 10^5~, ~0 ≤ a_i ≤ 1000~.

## Dữ liệu ra
In số nguyên không âm nhỏ nhất không xuất hiện trong dãy."""
    missing_samples = [
        {"input": "5\n0 1 2 4 5\n", "output": "3\n", "explanation": "Các số 0, 1, 2 đều có mặt; số 3 là số không xuất hiện nhỏ nhất."},
        {"input": "4\n0 1 2 3\n", "output": "4\n", "explanation": "Các số 0 đến 3 có mặt nên đáp án là 4."},
    ]
    missing_cpp = "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    bool present[1001] = {};\n    for (int i = 0, value; i < n; ++i) {\n        cin >> value;\n        present[value] = true;\n    }\n    int answer = 0;\n    while (answer <= 1000 && present[answer]) ++answer;\n    cout << answer << '\\n';\n    return 0;\n}\n"
    def missing_oracle(s):
        values = set(map(int, s.split()[1:]))
        answer = 0
        while answer in values:
            answer += 1
        return f"{answer}\n"
    missing_extras = ["1\n0\n", "1\n1000\n", "5\n1 1 1 1 1\n", "5\n1 2 3 4 5\n", "6\n0 0 1 1 2 2\n", "4\n1000 999 998 997\n", "7\n0 1 2 3 4 5 6\n", "8\n0 1 2 3 4 5 6 8\n", "6\n995 996 997 998 999 1000\n"]
    missing_extras.append("1001\n" + " ".join(map(str, range(1001))) + "\n")
    missing_extras.append("100000\n" + " ".join([str(i % 1000 + 1) for i in range(100000)]) + "\n")
    add("msb_missing", "Số không xuất hiện nhỏ nhất", "frequency", "foundations", frequency_tags, array_nodes, freq_statement, missing_samples,
        "Đánh dấu các giá trị đã gặp, sau đó kiểm tra từ 0 tăng dần. Nếu mọi số từ 0 đến 1000 đều xuất hiện thì đáp án là 1001.", "~O(n + 1001)~ thời gian, ~O(1001)~ bộ nhớ.", missing_cpp, missing_oracle, missing_extras)

    repeat_samples = [
        {"input": "4\n2 1 1 2\n", "output": "1\n", "explanation": "Quét từ trái sang phải, phần tử đầu tiên gặp lại giá trị đã thấy là 1."},
        {"input": "5\n0 1 2 3 4\n", "output": "-1\n", "explanation": "Không có giá trị nào xuất hiện lần thứ hai."},
    ]
    repeat_cpp = "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    bool seen[1001] = {};\n    for (int i = 0, value; i < n; ++i) {\n        cin >> value;\n        if (seen[value]) {\n            cout << value << '\\n';\n            return 0;\n        }\n        seen[value] = true;\n    }\n    cout << -1 << '\\n';\n    return 0;\n}\n"
    def repeat_oracle(s):
        seen = set()
        for value in map(int, s.split()[1:]):
            if value in seen:
                return f"{value}\n"
            seen.add(value)
        return "-1\n"
    repeat_statement = """Dòng đầu gồm số nguyên ~n~; dòng tiếp theo gồm ~n~ số nguyên ~a_i~ trong đoạn từ 0 đến 1000. Quét dãy từ trái sang phải. Hãy in giá trị của phần tử đầu tiên mà giá trị đó đã xuất hiện trước đó. Nếu không có phần tử như vậy, in ~-1~.

## Dữ liệu vào
Dòng đầu gồm số nguyên ~n~. Dòng thứ hai gồm ~n~ số nguyên ~a_i~.

~1 ≤ n ≤ 10^5~, ~0 ≤ a_i ≤ 1000~.

## Dữ liệu ra
In giá trị đầu tiên được gặp lại khi quét từ trái sang phải, hoặc in ~-1~ nếu mọi giá trị đều khác nhau."""
    repeat_extras = ["1\n0\n", "1\n1000\n", "2\n7 7\n", "4\n1 2 3 1\n", "5\n4 3 2 1 0\n", "5\n9 8 8 9 7\n", "6\n1000 0 1000 0 1 1\n", "7\n0 1 2 3 4 5 6\n", "8\n5 4 3 2 1 0 5 4\n", "5\n0 0 1 2 3\n"]
    repeat_extras.append("100000\n" + " ".join([str(i % 1001) for i in range(100000)]) + "\n")
    add("msb_firstrepeat", "Giá trị đầu tiên xuất hiện lặp", "frequency", "foundations", frequency_tags, array_nodes, repeat_statement, repeat_samples,
        "Đánh dấu từng giá trị khi quét từ trái sang phải và dừng ở lần đầu gặp lại. Kết quả in ra là giá trị của phần tử, không phải vị trí (chỉ số) của nó; đây cũng không nhất thiết là giá trị trùng nhỏ nhất.", "~O(n)~ thời gian, ~O(1001)~ bộ nhớ.", repeat_cpp, repeat_oracle, repeat_extras)

    string_nodes = ["arrays-and-strings"]
    string_tags = ["arrays-and-strings", "string-basics"]
    char_samples = [
        {"input": "banana\na\n", "output": "3\n", "explanation": "Ký tự a xuất hiện ba lần trong banana."},
        {"input": "abc\nz\n", "output": "0\n", "explanation": "Ký tự z không xuất hiện trong chuỗi."},
    ]
    char_cpp = "#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    string s;\n    char c;\n    cin >> s >> c;\n    int count = 0;\n    for (char ch : s) {\n        if (ch == c) ++count;\n    }\n    cout << count << '\\n';\n    return 0;\n}\n"
    def char_oracle(data):
        text, target = data.split()
        return f"{sum(ch == target for ch in text)}\n"

    char_statement = """Dòng đầu gồm chuỗi chữ thường ~S~ không rỗng. Dòng thứ hai gồm một ký tự chữ thường ~c~. Hãy đếm số lần ~c~ xuất hiện trong ~S~.

## Dữ liệu vào
Dòng đầu gồm chuỗi ~S~. Dòng thứ hai gồm ký tự ~c~.

~1 ≤ |S| ≤ 10^5~; ~S~ và ~c~ chỉ gồm các chữ cái tiếng Anh viết thường.

## Dữ liệu ra
In số lần ký tự ~c~ xuất hiện trong ~S~."""
    char_extras = ["a\na\n", "z\na\n", "aaaaaa\na\n", "abcdef\nf\n", "mississippi\ns\n", "programming\nm\n", "abcabcabc\nc\n", "xylophone\no\n", "qwertyuiop\nz\n"]
    char_extras.append("a" * 100000 + "\na\n")
    char_extras.append("abcdefghijklmnopqrstuvwxyz\na\n")
    add("msb_charcount", "Đếm ký tự", "strings", "foundations", string_tags, string_nodes, char_statement, char_samples,
        "Duyệt chuỗi một lần và tăng bộ đếm khi ký tự hiện tại bằng ~c~.", "~O(|S|)~ thời gian, ~O(1)~ bộ nhớ phụ.", char_cpp, char_oracle, char_extras)

    case_samples = [
        {"input": "HeLLo\n", "output": "hello\nHELLO\n", "explanation": "Chữ cái được chuyển sang chữ thường hoặc chữ hoa tương ứng."},
        {"input": "abcXYZ\n", "output": "abcxyz\nABCXYZ\n", "explanation": "Hai dòng lần lượt là dạng chữ thường và chữ hoa."},
    ]
    case_cpp = "#include <iostream>\n#include <string>\nusing namespace std;\n\nint main() {\n    string s;\n    cin >> s;\n    for (char ch : s) {\n        if ('A' <= ch && ch <= 'Z') ch = static_cast<char>(ch - 'A' + 'a');\n        cout << ch;\n    }\n    cout << '\\n';\n    for (char ch : s) {\n        if ('a' <= ch && ch <= 'z') ch = static_cast<char>(ch - 'a' + 'A');\n        cout << ch;\n    }\n    cout << '\\n';\n    return 0;\n}\n"
    case_oracle = lambda s: s.strip().lower() + "\n" + s.strip().upper() + "\n"
    case_statement = """Cho chuỗi không rỗng ~S~ chỉ gồm các chữ cái tiếng Anh viết hoa hoặc viết thường. Hãy in chuỗi sau khi chuyển toàn bộ chữ cái thành chữ thường, rồi in chuỗi sau khi chuyển toàn bộ chữ cái thành chữ hoa.

## Dữ liệu vào
Một dòng gồm chuỗi ~S~.

~1 ≤ |S| ≤ 10^5~; ~S~ chỉ gồm các chữ cái tiếng Anh ~A-Z~ và ~a-z~.

## Dữ liệu ra
In hai dòng: dòng đầu là ~S~ viết thường, dòng sau là ~S~ viết hoa."""
    case_extras = ["a\n", "Z\n", "ABC\n", "xyz\n", "AbCdEf\n", "AaZz\n", "Programming\n", "qWeRtY\n", "abcdefghijklmnopqrstuvwxyz\n", "ABCDEFGHIJKLMNOPQRSTUVWXYZ\n", "aBcD" * 25 + "\n"]
    case_extras.append("aZ" * 50000 + "\n")
    add("msb_caseconvert", "Chuyển đổi chữ hoa và chữ thường", "strings", "foundations", string_tags, string_nodes, case_statement, case_samples,
        "Duyệt chuỗi và đổi từng chữ cái theo mã ASCII; đầu vào chỉ chứa chữ cái tiếng Anh nên không có quy tắc Unicode cần xử lý.", "~O(|S|)~ thời gian, ~O(1)~ bộ nhớ phụ ngoài chuỗi đầu vào.", case_cpp, case_oracle, case_extras)

    matrix_samples = [
        {"input": "2 3\n1 5 2\n-4 -2 -8\n", "output": "5\n-2\n", "explanation": "Giá trị lớn nhất của từng hàng lần lượt là 5 và -2."},
        {"input": "1 1\n-9\n", "output": "-9\n", "explanation": "Ma trận một ô có giá trị lớn nhất là -9."},
    ]
    matrix_cpp = "#include <iostream>\n#include <algorithm>\nusing namespace std;\n\nint main() {\n    int n, m;\n    cin >> n >> m;\n    for (int i = 0; i < n; ++i) {\n        int maximum, value;\n        cin >> maximum;\n        for (int j = 1; j < m; ++j) {\n            cin >> value;\n            maximum = max(maximum, value);\n        }\n        cout << maximum << '\\n';\n    }\n    return 0;\n}\n"
    def rowmax_oracle(s):
        tokens = list(map(int, s.split()))
        n, m = tokens[:2]
        values = tokens[2:]
        return "".join(f"{max(values[i*m:(i+1)*m])}\n" for i in range(n))
    matrix_statement = """Dòng đầu gồm hai số nguyên ~n~ và ~m~ là số hàng và số cột của ma trận. Tiếp theo là ~n~ dòng, mỗi dòng có ~m~ số nguyên ~a_{i,j}~. Với mỗi hàng, hãy in giá trị lớn nhất trên hàng đó.

## Dữ liệu vào
Dòng đầu gồm ~n~ và ~m~. Mỗi dòng trong ~n~ dòng tiếp theo gồm ~m~ số nguyên.

~1 ≤ n, m ≤ 200~, ~|a_{i,j}| ≤ 10^9~.

## Dữ liệu ra
In ~n~ dòng; dòng thứ ~i~ là giá trị lớn nhất của hàng thứ ~i~."""
    matrix_extras = ["1 4\n-5 -2 -9 -3\n", "3 1\n7\n-8\n0\n", "2 2\n-1 -2\n-3 -4\n", "2 4\n1 2 3 4\n4 3 2 1\n", "3 2\n-1000000000 1000000000\n0 0\n-5 -6\n", "4 3\n2 2 2\n-1 -1 -1\n9 0 9\n-8 4 3\n", "1 5\n0 0 0 0 0\n", "5 1\n-10\n-20\n-30\n-40\n-50\n", "2 3\n-9 -7 -8\n-6 -5 -4\n"]
    matrix_extras.append("200 200\n" + (" ".join(["-1000000000", "1000000000"] * 100) + "\n") * 200)
    add("msb_rowmax", "Giá trị lớn nhất trên từng hàng", "matrices", "foundations", ["arrays-and-strings", "matrix-basics"], array_nodes, matrix_statement, matrix_samples,
        "Đọc từng hàng, giữ giá trị lớn nhất của hàng đó rồi in ngay; không cần lưu toàn bộ ma trận.", "~O(nm)~ thời gian, ~O(1)~ bộ nhớ phụ.", matrix_cpp, rowmax_oracle, matrix_extras)

    divisor_samples = [
        {"input": "6\n", "output": "12\n", "explanation": "Các ước dương của 6 là 1, 2, 3, 6 và tổng bằng 12."},
        {"input": "1\n", "output": "1\n", "explanation": "Số 1 chỉ có một ước dương là 1."},
    ]
    divisor_cpp = "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    long long sum = 0;\n    for (int divisor = 1; divisor <= n; ++divisor) {\n        if (n % divisor == 0) sum += divisor;\n    }\n    cout << sum << '\\n';\n    return 0;\n}\n"
    def divisor_oracle(text):
        n = int(text)
        total = 0
        for d in range(1, isqrt(n) + 1):
            if n % d == 0:
                total += d
                if d * d != n:
                    total += n // d
        return f"{total}\n"
    divisor_statement = """Cho số nguyên dương ~n~. Hãy tính tổng tất cả các ước dương của ~n~.

## Dữ liệu vào
Một số nguyên dương ~n~ (~1 ≤ n ≤ 10^6~).

## Dữ liệu ra
In tổng các ước dương của ~n~. Kết quả vừa kiểu số nguyên 64 bit có dấu."""
    divisor_extras = ["2\n", "3\n", "4\n", "9\n", "12\n", "13\n", "16\n", "28\n", "36\n", "100\n", "360\n", "999983\n", "1000000\n"]
    add("msb_divisorsum", "Tổng các ước dương", "numbers", "number-theory", ["programming-basics", "number-theory", "divisors", "numeric-safety"], ["programming-basics", "implementation"], divisor_statement, divisor_samples,
        "Thử lần lượt các số từ 1 đến ~n~; nếu số đó chia hết ~n~, cộng nó vào tổng. Kiểu số nguyên 64 bit đủ chứa kết quả theo giới hạn đề bài.", "~O(n)~ thời gian, ~O(1)~ bộ nhớ phụ.", divisor_cpp, divisor_oracle, divisor_extras)

    return result
