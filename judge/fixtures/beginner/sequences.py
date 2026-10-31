from collections import Counter

import random


def _cases(samples, extra):
    return [sample["input"] for sample in samples] + extra


def _min_position_oracle(input_text):
    values = list(map(int, input_text.split()))[1:]
    minimum = min(values)
    first = values.index(minimum) + 1
    last = len(values) - values[::-1].index(minimum)
    return f"{minimum} {first} {last}\n"


def problems():
    result = []
    maximum_array_case = "100000\n" + " ".join(["1000000000", "-1000000000", "0"] * 33333 + ["1000000000"]) + "\n"
    frequency_max_case = "100000\n" + " ".join(["0"] * 100000) + "\n"
    query_max_case = frequency_max_case + "1000\n" + " ".join(map(str, range(1000))) + "\n"
    rng = random.Random(211)
    generated_array = [rng.randint(-10**9, 10**9) for _ in range(24)]
    generated_array_case = f"{len(generated_array)}\n{' '.join(map(str, generated_array))}\n"

    def add(code, title, section, tags, nodes, statement, samples, explanation,
            complexity, cpp, oracle, function_practice=False, extra_cases=()):
        result.append({
            "code": code,
            "title": title,
            "section": section,
            "group": "foundations",
            "tags": tags,
            "nodes": nodes,
            "statement": statement,
            "samples": samples,
            "explanation": explanation,
            "complexity": complexity,
            "cpp": cpp,
            "oracle": oracle,
            "cases": _cases(samples, list(extra_cases)),
            "function_practice": function_practice,
        })

    digit_statement = """Cho một số nguyên không âm ~n~. Hãy xử lý các chữ số thập phân của ~n~ theo yêu cầu.

## Dữ liệu vào
Một số nguyên ~n~ (~0 ≤ n ≤ 10^{18}~).

## Dữ liệu ra
In kết quả theo yêu cầu của bài. Số ~0~ được xem là có một chữ số."""
    digit_cpp_prefix = "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long n;\n    cin >> n;\n"
    digit_cpp_suffix = "    return 0;\n}\n"
    digit_cases = ["0\n", "1\n", "9\n", "10\n", "100\n", "101\n", "999999999999999999\n", "1000000000000000000\n", "808\n"]
    add("msb_digitcount", "Đếm chữ số", "digits", ["loops"], ["loops"],
        digit_statement.replace("theo yêu cầu của bài", "và in số chữ số của nó"),
        [{"input": "407\n", "output": "3\n", "explanation": "Số 407 gồm ba chữ số."}],
        "Chia liên tiếp cho 10 và đếm số lần. Riêng n = 0 có một chữ số.", "Thời gian O(d), bộ nhớ O(1), với d là số chữ số.",
        digit_cpp_prefix + "    int count = 0;\n    do {\n        ++count;\n        n /= 10;\n    } while (n > 0);\n    cout << count << '\\n';\n" + digit_cpp_suffix,
        lambda s: f"{len(s.strip())}\n", extra_cases=digit_cases)
    add("msb_digitsum", "Tính tổng chữ số", "digits", ["loops", "functions"], ["loops", "functions"],
        digit_statement.replace("theo yêu cầu của bài", "và in tổng các chữ số của nó"),
        [{"input": "5082\n", "output": "15\n", "explanation": "5 + 0 + 8 + 2 = 15."}],
        "Hàm digitSum nhận tham số n theo giá trị (một bản sao số không âm), dùng biến cục bộ n để lần lượt lấy chữ số cuối bằng n % 10 rồi chia n cho 10. Hàm trả về tổng các chữ số; trường hợp n = 0 trả về 0.", "Thời gian O(d), bộ nhớ O(1), với d là số chữ số.",
        "#include <iostream>\nusing namespace std;\n\nlong long digitSum(long long n) {\n    long long sum = 0;\n    while (n > 0) {\n        sum += n % 10;\n        n /= 10;\n    }\n    return sum;\n}\n\nint main() {\n    long long n;\n    cin >> n;\n    cout << digitSum(n) << '\\n';\n    return 0;\n}\n",
        lambda s: f"{sum(map(int, s.strip()))}\n", True, digit_cases)
    add("msb_digitmax", "Chữ số lớn nhất", "digits", ["loops"], ["loops"],
        digit_statement.replace("theo yêu cầu của bài", "và in chữ số lớn nhất của nó"),
        [{"input": "17049\n", "output": "9\n", "explanation": "Chữ số lớn nhất trong 1, 7, 0, 4, 9 là 9."}],
        "Mỗi vòng lặp lấy chữ số cuối, cập nhật giá trị lớn nhất rồi bỏ chữ số đó. Khởi tạo bằng 0 để xử lý n = 0.", "Thời gian O(d), bộ nhớ O(1), với d là số chữ số.",
        digit_cpp_prefix + "    int best = 0;\n    do {\n        int digit = static_cast<int>(n % 10);\n        if (digit > best) best = digit;\n        n /= 10;\n    } while (n > 0);\n    cout << best << '\\n';\n" + digit_cpp_suffix,
        lambda s: f"{max(map(int, s.strip()))}\n", extra_cases=digit_cases)
    add("msb_reverseint", "Đảo chữ số", "digits", ["loops"], ["loops"],
        digit_statement.replace("theo yêu cầu của bài", "và in số tạo bởi các chữ số theo thứ tự ngược lại; các số 0 ở đầu kết quả không in ra"),
        [{"input": "12030\n", "output": "3021\n", "explanation": "Đọc các chữ số từ phải sang trái tạo 03021; số 0 ở đầu được bỏ nên kết quả là 3021."}],
        "Mỗi bước lấy chữ số cuối và nối vào kết quả bằng phép nhân 10 rồi cộng chữ số. Kết quả với n = 0 là 0.", "Thời gian O(d), bộ nhớ O(1), với d là số chữ số.",
        digit_cpp_prefix + "    long long reversed = 0;\n    do {\n        reversed = reversed * 10 + n % 10;\n        n /= 10;\n    } while (n > 0);\n    cout << reversed << '\\n';\n" + digit_cpp_suffix,
        lambda s: f"{int(s.strip()[::-1])}\n", extra_cases=digit_cases)
    add("msb_palint", "Số đối xứng", "digits", ["loops"], ["loops"],
        digit_statement.replace("theo yêu cầu của bài", "và in YES nếu các chữ số đọc từ trái sang phải giống khi đọc từ phải sang trái, ngược lại in NO"),
        [{"input": "12321\n", "output": "YES\n", "explanation": "Đọc 12321 theo hai chiều đều được cùng một số."}],
        "Lưu số ban đầu, đảo chữ số bằng phép toán số học rồi so sánh với số ban đầu. Số 0 cũng đối xứng.", "Thời gian O(d), bộ nhớ O(1), với d là số chữ số.",
        "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long n;\n    cin >> n;\n    long long original = n;\n    long long reversed = 0;\n    do {\n        reversed = reversed * 10 + n % 10;\n        n /= 10;\n    } while (n > 0);\n    cout << (original == reversed ? \"YES\" : \"NO\") << '\\n';\n    return 0;\n}\n",
        lambda s: "YES\n" if s.strip() == s.strip()[::-1] else "NO\n", extra_cases=digit_cases + ["1231\n", "12341\n", "12021\n", "123454321\n", "100000000000000001\n"])

    array_nodes = ["array-basics"]
    array_base = """Dòng đầu gồm số nguyên ~n~; dòng tiếp theo gồm ~n~ số nguyên ~a_i~.

## Dữ liệu vào
~1 ≤ n ≤ 10^5~, ~|a_i| ≤ 10^9~.

## Dữ liệu ra
In kết quả theo yêu cầu của bài."""
    array_values = ["1\n", "0\n", "-1\n", "-1000000000\n", "1000000000\n", "-5 0 5\n", "-1 -1 0 1 1\n"]
    add("msb_arraysum", "Tổng các phần tử", "arrays", ["array-basics", "numeric-safety"], array_nodes,
        array_base.replace("theo yêu cầu của bài", "là tổng tất cả phần tử. Kết quả nằm trong phạm vi số nguyên có dấu 64-bit"),
        [{"input": "4\n1000000000 -3 5 2\n", "output": "1000000004\n", "explanation": "Cộng lần lượt bốn phần tử được 1000000004."}],
        "Duyệt mỗi phần tử một lần và cộng vào biến long long để tổng không tràn kiểu 32-bit.", "Thời gian O(n), bộ nhớ O(1).",
        "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    long long sum = 0;\n    for (int i = 0; i < n; ++i) {\n        long long value;\n        cin >> value;\n        sum += value;\n    }\n    cout << sum << '\\n';\n    return 0;\n}\n",
        lambda s: f"{sum(map(int, s.split()[1:]))}\n", extra_cases=["1\n1000000000\n", "3\n1000000000 1000000000 1000000000\n", "2\n-1000000000 -1000000000\n", "5\n0 0 0 0 0\n", "6\n-1 2 -3 4 -5 6\n", "1\n-1000000000\n", "3\n1 -1 0\n", "4\n-1000000000 1000000000 -1000000000 1000000000\n", "2\n999999999 -999999999\n"])
    result[-1]["cases"].append(maximum_array_case)
    result[-1]["cases"].append(generated_array_case)
    add("msb_arraycount", "Đếm âm, không và dương", "arrays", ["array-basics"], array_nodes,
        array_base.replace("theo yêu cầu của bài", "gồm ba số lần lượt là số phần tử âm, bằng 0 và dương"),
        [{"input": "6\n-2 0 4 -1 0 7\n", "output": "2 2 2\n", "explanation": "Có hai số âm, hai số 0 và hai số dương."}],
        "Duyệt mảng, với mỗi giá trị tăng đúng một trong ba bộ đếm. Các phần tử bằng 0 thuộc nhóm riêng.", "Thời gian O(n), bộ nhớ O(1).",
        "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    int negative = 0, zero = 0, positive = 0;\n    for (int i = 0; i < n; ++i) {\n        long long value;\n        cin >> value;\n        if (value < 0) ++negative;\n        else if (value == 0) ++zero;\n        else ++positive;\n    }\n    cout << negative << ' ' << zero << ' ' << positive << '\\n';\n    return 0;\n}\n",
        lambda s: (lambda a: f"{sum(x < 0 for x in a)} {sum(x == 0 for x in a)} {sum(x > 0 for x in a)}\n")(list(map(int, s.split()[1:]))), extra_cases=[f"{len(v.split())}\n{v.strip()}\n" for v in array_values] + ["8\n-4 -3 -2 -1 1 2 3 4\n", "4\n0 0 0 0\n", "3\n-1 0 1\n", "2\n-1000000000 1000000000\n", "5\n1 1 1 1 1\n"])
    result[-1]["cases"].append(generated_array_case)
    result[-1]["cases"].append(maximum_array_case)

    find_statement = """Dòng đầu gồm ~n~ và giá trị cần tìm ~x~; dòng tiếp theo gồm ~n~ số nguyên ~a_i~. Hãy tìm vị trí xuất hiện đầu tiên và cuối cùng của ~x~.

## Dữ liệu vào
~1 ≤ n ≤ 10^5~, ~|a_i|, |x| ≤ 10^9~.

## Dữ liệu ra
In vị trí đầu tiên và cuối cùng (đánh số từ 1). Nếu ~x~ không xuất hiện, in ~-1 -1~."""
    find_cpp = "#include <iostream>\n#include <utility>\n#include <vector>\nusing namespace std;\n\npair<int, int> findPositions(const vector<int>& values, int target) {\n    int first = -1, last = -1;\n    for (int i = 0; i < static_cast<int>(values.size()); ++i) {\n        if (values[i] == target) {\n            if (first == -1) first = i + 1;\n            last = i + 1;\n        }\n    }\n    return {first, last};\n}\n\nint main() {\n    int n, x;\n    cin >> n >> x;\n    vector<int> values(n);\n    for (int& value : values) cin >> value;\n    auto positions = findPositions(values, x);\n    cout << positions.first << ' ' << positions.second << '\\n';\n    return 0;\n}\n"
    add("msb_arrayfind", "Vị trí xuất hiện đầu và cuối", "arrays", ["array-basics", "functions"], ["array-basics", "functions"],
        find_statement, [{"input": "7 4\n4 2 4 1 4 3 4\n", "output": "1 7\n", "explanation": "Giá trị 4 xuất hiện đầu tiên ở vị trí 1 và cuối cùng ở vị trí 7."}],
        "Hàm findPositions nhận mảng và giá trị cần tìm, duyệt mảng một lần rồi trả về cặp vị trí 1-based. Nếu không gặp giá trị thì cả hai vị trí giữ -1.", "Thời gian O(n), bộ nhớ O(n) để lưu mảng.", find_cpp,
        lambda s: (lambda d: (lambda n, x, a: (lambda p: f"{p[0]} {p[-1]}\n" if p else "-1 -1\n")([i + 1 for i, v in enumerate(a) if v == x]))(int(d[0]), int(d[1]), list(map(int, d[2:]))))(s.split()), True,
        ["1 5\n5\n", "1 0\n0\n", "5 2\n1 2 3 4 5\n", "5 7\n1 2 3 4 5\n", "6 -1\n-1 0 -1 2 -1 3\n", "4 1000000000\n1000000000 -1000000000 0 1000000000\n", "3 0\n0 0 0\n", "8 3\n1 3 3 2 3 1 3 4\n", "2 -1000000000\n-1000000000 1000000000\n", "4 9\n8 9 10 9\n"])
    add("msb_minpos", "Giá trị nhỏ nhất và vị trí", "arrays", ["array-basics"], array_nodes,
        array_base.replace("theo yêu cầu của bài", "gồm giá trị nhỏ nhất, vị trí xuất hiện đầu tiên và vị trí xuất hiện cuối cùng của giá trị nhỏ nhất (các vị trí đánh số từ 1)"),
        [{"input": "6\n4 -2 7 -2 0 -2\n", "output": "-2 2 6\n", "explanation": "Giá trị nhỏ nhất là -2, xuất hiện lần đầu ở vị trí 2 và lần cuối ở vị trí 6."}],
        "Khởi tạo min từ phần tử đầu tiên, duyệt mảng và so sánh từng giá trị. Khi gặp giá trị nhỏ hơn, cập nhật giá trị min và cả hai vị trí; khi bằng min, cập nhật vị trí cuối. Cách này giữ vị trí đầu tiên khi có hòa.", "Thời gian O(n), bộ nhớ O(n) để lưu mảng.",
        "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    vector<int> values(n);\n    for (int& value : values) cin >> value;\n    int minimum = values[0];\n    int first = 1, last = 1;\n    for (int i = 1; i < n; ++i) {\n        if (values[i] < minimum) {\n            minimum = values[i];\n            first = last = i + 1;\n        } else if (values[i] == minimum) {\n            last = i + 1;\n        }\n    }\n    cout << minimum << ' ' << first << ' ' << last << '\\n';\n    return 0;\n}\n",
        _min_position_oracle,
        extra_cases=["1\n5\n", "1\n-1000000000\n", "5\n2 2 2 2 2\n", "5\n1 2 3 4 5\n", "5\n5 4 3 2 1\n", "6\n0 -1 0 -1 2 -1\n", "4\n1000000000 -1000000000 0 -1000000000\n", "3\n-1000000000 -1000000000 -999999999\n", "8\n1 -5 3 -5 0 -5 2 1\n", "5\n0 1 0 2 0\n"])
    result[-1]["cases"].append(maximum_array_case)
    frequency_statement = """Dòng đầu gồm số nguyên ~n~; dòng tiếp theo gồm ~n~ số nguyên ~a_i~ trong đoạn từ 0 đến 1000.

## Dữ liệu vào
~1 ≤ n ≤ 10^5~, ~0 ≤ a_i ≤ 1000~."""
    frequency_nodes = ["array-basics"]
    frequency_tags = ["array-basics"]
    freq_cases = ["1\n0\n", "1\n1000\n", "5\n0 0 0 0 0\n", "6\n1 2 3 4 5 6\n", "8\n7 7 7 2 2 2 9 9\n", "10\n0 1000 0 1000 500 500 500 1 1 1\n", "4\n1000 999 998 997\n"]
    add("msb_freqquery", "Truy vấn tần suất", "frequency", frequency_tags, frequency_nodes,
        frequency_statement + "\nDòng tiếp theo gồm số nguyên ~q~; dòng sau gồm ~q~ giá trị truy vấn ~x~ trong đoạn từ 0 đến 1000. Với mỗi truy vấn, hãy in số lần xuất hiện của x trong mảng, mỗi kết quả trên một dòng.\n\n~1 ≤ q ≤ 1000~, ~0 ≤ x ≤ 1000~.\n\n## Dữ liệu ra\nIn ~q~ số nguyên, mỗi số trên một dòng; số thứ i là số lần giá trị truy vấn thứ i xuất hiện trong mảng.",
        [{"input": "6\n1 2 1 0 2 1\n4\n1 0 3 2\n", "output": "3\n1\n0\n2\n", "explanation": "Các giá trị 1, 0, 3, 2 lần lượt xuất hiện 3, 1, 0, 2 lần."}],
        "Dùng mảng đếm có 1001 phần tử, ban đầu đều bằng 0. Ghi nhận tần suất khi đọc mảng rồi trả lời mỗi truy vấn trực tiếp; giá trị chưa xuất hiện có tần suất 0.", "Thời gian O(n + q + 1001), bộ nhớ O(1001).",
        "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    vector<int> count(1001, 0);\n    for (int i = 0; i < n; ++i) {\n        int value;\n        cin >> value;\n        ++count[value];\n    }\n    int q;\n    cin >> q;\n    while (q--) {\n        int x;\n        cin >> x;\n        cout << count[x] << '\\n';\n    }\n    return 0;\n}\n",
        lambda s: (lambda t: (lambda n, a, q, xs: "".join(f"{a.count(x)}\n" for x in xs))(int(t[0]), list(map(int, t[1:1 + int(t[0])])), int(t[1 + int(t[0])]), list(map(int, t[2 + int(t[0]):]))))(s.split()),
        extra_cases=[f"{c}{q}{queries}\n" for c, q, queries in [("1\n0\n", "1\n", "0"), ("1\n1000\n", "3\n", "0 999 1000"), ("5\n1 1 1 1 1\n", "4\n", "1 2 0 1000"), ("6\n0 1 2 3 4 5\n", "6\n", "0 1 3 5 6 1000"), ("8\n7 7 7 2 2 2 9 9\n", "5\n", "7 2 9 0 1000"), ("4\n1000 999 998 997\n", "4\n", "997 998 999 1000"), ("10\n0 1000 0 1000 500 500 500 1 1 1\n", "6\n", "0 1 500 1000 2 999")]])
    result[-1]["cases"].append(query_max_case)
    result[-1]["cases"].append("2\n0 1000\n1\n500\n")
    add("msb_distinct", "Đếm giá trị phân biệt", "frequency", frequency_tags, frequency_nodes,
        frequency_statement + "\n## Dữ liệu ra\nIn số lượng giá trị phân biệt trong mảng.",
        [{"input": "7\n2 2 0 5 0 5 5\n", "output": "3\n", "explanation": "Các giá trị khác nhau là 0, 2 và 5."}],
        "Đánh dấu mỗi giá trị đã gặp trong mảng đếm. Sau khi đọc xong, đếm số vị trí có tần suất lớn hơn 0.", "Thời gian O(n + 1001), bộ nhớ O(1001).",
        "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    vector<int> count(1001, 0);\n    for (int i = 0; i < n; ++i) {\n        int value;\n        cin >> value;\n        ++count[value];\n    }\n    int distinct = 0;\n    for (int frequency : count) {\n        if (frequency > 0) ++distinct;\n    }\n    cout << distinct << '\\n';\n    return 0;\n}\n",
        lambda s: f"{len(set(map(int, s.split()[1:])))}\n", extra_cases=[f"{len(v.split())}\n{v}\n" for v in ["0", "1000", "0 0 0 0", "1 2 3 4 5", "7 7 7 2 2 2 9 9", "0 1000 0 1000 500 500 500 1 1 1", "1000 999 998 997"]] + ["12\n3 3 3 3 3 3 3 3 3 3 3 3\n"])
    result[-1]["cases"].extend(["6\n0 1 2 3 1000 1000\n", "7\n4 4 4 4 4 4 4\n"])
    result[-1]["cases"].append(frequency_max_case)
    add("msb_mode", "Giá trị xuất hiện nhiều nhất", "frequency", frequency_tags, frequency_nodes,
        frequency_statement + "\n## Dữ liệu ra\nIn giá trị xuất hiện nhiều nhất và số lần xuất hiện. Nếu nhiều giá trị có cùng tần suất lớn nhất, in giá trị nhỏ nhất trong số đó.",
        [{"input": "8\n4 2 4 2 3 3 4 2\n", "output": "2 3\n", "explanation": "2 và 4 cùng xuất hiện 3 lần; chọn giá trị nhỏ hơn là 2."}],
        "Đếm tần suất từng giá trị. Duyệt theo thứ tự tăng dần và chỉ cập nhật khi tần suất lớn hơn mức tốt nhất; vì vậy khi hòa, giá trị nhỏ hơn được giữ lại.", "Thời gian O(n + 1001), bộ nhớ O(1001).",
        "#include <iostream>\n#include <vector>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    vector<int> count(1001, 0);\n    for (int i = 0; i < n; ++i) {\n        int value;\n        cin >> value;\n        ++count[value];\n    }\n    int mode = 0, best = 0;\n    for (int value = 0; value <= 1000; ++value) {\n        if (count[value] > best) {\n            best = count[value];\n            mode = value;\n        }\n    }\n    cout << mode << ' ' << best << '\\n';\n    return 0;\n}\n",
        lambda s: (lambda a: (lambda counts: (lambda mode: f"{mode} {counts[mode]}\n")(min(counts, key=lambda value: (-counts[value], value))))(Counter(a)))(list(map(int, s.split()[1:]))),
        extra_cases=[f"{len(v.split())}\n{v}\n" for v in ["0", "1000", "0 0 0 0", "1 2 3 4 5", "7 7 7 2 2 2 9 9", "0 1000 0 1000 500 500 500 1 1 1", "1000 999 998 997"]] + ["12\n3 3 3 3 3 3 3 3 3 3 3 3\n"])
    result[-1]["cases"].extend(["6\n0 1 2 3 1000 1000\n", "7\n4 4 4 4 4 4 4\n"])
    result[-1]["cases"].append(frequency_max_case)
    return result
