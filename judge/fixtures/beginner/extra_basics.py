

def problems():
    def oracle_rectangle(text):
        a, b = map(int, text.split())
        return f"{2 * (a + b)} {a * b}\n"

    def oracle_purchase(text):
        n, price, money = map(int, text.split())
        cost = n * price
        return f"{cost} {money - cost}\n"

    def oracle_trianglecheck(text):
        a, b, c = sorted(map(int, text.split()))
        return ("YES" if a + b > c else "NO") + "\n"

    def oracle_grade(text):
        score = int(text)
        if score >= 90:
            result = "XUAT_SAC"
        elif score >= 80:
            result = "GIOI"
        elif score >= 65:
            result = "KHA"
        elif score >= 50:
            result = "DAT"
        else:
            result = "CHUA_DAT"
        return result + "\n"

    def oracle_sumodd(text):
        n = int(text)
        odd_count = (n + 1) // 2
        return f"{odd_count * odd_count}\n"

    def oracle_power(text):
        a, n = map(int, text.split())
        return f"{pow(a, n)}\n"

    rectangle_cases = ["1 1\n", "1 1000000000\n", "1000000000 1\n", "1000000000 1000000000\n",
                       "2 3\n", "7 11\n", "999999999 1000000000\n", "42 42\n", "123456789 987654321\n",
                       "5 100\n", "31415 92653\n", "876543210 123456789\n"]
    purchase_cases = ["0 1 0\n", "0 1000000 1000000000000\n", "1 1 1\n", "1 1000000 1000000\n",
                      "1000000 1 1000000\n", "1000000 1000000 1000000000000\n", "2 3 6\n", "2 3 20\n",
                      "10 25 250\n", "123 456 100000\n", "999999 1000000 1000000000000\n", "42 100 5000\n"]
    trianglecheck_cases = ["1 1 1\n", "1 2 3\n", "2 2 3\n", "1 1 2\n", "3 4 5\n", "5 3 4\n",
                          "1000000000 1000000000 1000000000\n", "1 1000000000 1000000000\n",
                          "999999999 1 1000000000\n", "10 10 19\n", "10 10 20\n", "7 8 14\n"]
    trianglecheck_cases += ["3 1 1\n", "1 3 1\n", "5 2 2\n", "2 5 2\n"]
    grade_cases = [f"{score}\n" for score in (0, 1, 49, 50, 64, 65, 79, 80, 89, 90, 99, 100)]
    sumodd_cases = [f"{n}\n" for n in (0, 1, 2, 3, 4, 5, 10, 11, 999999, 1000000, 17, 101, 67890, 765432)]
    power_cases = ["0 0\n", "0 1\n", "0 18\n", "1 18\n", "-1 17\n", "-1 18\n",
                   "10 18\n", "-10 18\n", "-10 17\n", "2 0\n", "-2 5\n", "3 7\n",
                   "5 12\n", "7 9\n"]

    return [
        {
            "code": "msb_rectangle",
            "title": "Chu vi và diện tích hình chữ nhật",
            "section": "io",
            "group": "foundations",
            "tags": ["io-basics", "arithmetic", "numeric-safety"],
            "nodes": ["io-basics"],
            "statement": "Cho hai số nguyên dương a và b là chiều dài hai cạnh của hình chữ nhật. Hãy tính chu vi và diện tích hình chữ nhật.\n\n## Dữ liệu vào\nMột dòng gồm hai số nguyên dương a, b (~1 \\le a, b \\le 10^{9}~).\n\n## Dữ liệu ra\nIn chu vi và diện tích theo thứ tự, cách nhau bởi một dấu cách.",
            "samples": [{"input": "3 5\n", "output": "16 15\n", "explanation": "Chu vi là 2 × (3 + 5) = 16, diện tích là 3 × 5 = 15."}],
            "explanation": "Chu vi bằng ~2 \\times (a + b)~, diện tích bằng ~a \\times b~. Cả hai kết quả có thể vượt giới hạn số nguyên 32-bit, vì vậy dùng số nguyên 64-bit.",
            "complexity": "O(1) thời gian, O(1) bộ nhớ.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long a, b;\n    cin >> a >> b;\n    cout << 2 * (a + b) << ' ' << a * b << '\\n';\n    return 0;\n}\n",
            "cases": rectangle_cases,
            "oracle": oracle_rectangle,
            "function_practice": False,
        },
        {
            "code": "msb_purchase",
            "title": "Tính tiền mua hàng và tiền thừa",
            "section": "io",
            "group": "foundations",
            "tags": ["io-basics", "arithmetic", "numeric-safety"],
            "nodes": ["io-basics"],
            "statement": "Bạn mua n món hàng, mỗi món giá p đồng, và có money đồng. Biết số tiền đang có đủ để thanh toán. Hãy tính tổng tiền hàng và tiền thừa sau khi trả đủ.\n\n## Dữ liệu vào\nMột dòng gồm ba số nguyên n, p, money (~0 \\le n \\le 10^{6}~, ~1 \\le p \\le 10^{6}~, ~0 \\le money \\le 10^{12}~). Dữ liệu bảo đảm ~money \\ge n \\times p~.\n\n## Dữ liệu ra\nIn tổng tiền hàng và tiền thừa theo thứ tự, cách nhau bởi một dấu cách.",
            "samples": [{"input": "4 2500 12000\n", "output": "10000 2000\n", "explanation": "Tổng tiền là 4 × 2500 = 10000 đồng; tiền thừa là 12000 - 10000 = 2000 đồng."}],
            "explanation": "Tính tổng tiền bằng n × p, sau đó lấy money trừ tổng tiền để tìm tiền thừa. n có thể bằng 0 nên tổng tiền và tiền thừa khi đó lần lượt là 0 và money.",
            "complexity": "O(1) thời gian, O(1) bộ nhớ.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long n, p, money;\n    cin >> n >> p >> money;\n    long long cost = n * p;\n    cout << cost << ' ' << money - cost << '\\n';\n    return 0;\n}\n",
            "cases": purchase_cases,
            "oracle": oracle_purchase,
            "function_practice": False,
        },
        {
            "code": "msb_trianglecheck",
            "title": "Kiểm tra ba cạnh tam giác",
            "section": "conditions",
            "group": "foundations",
            "tags": ["conditions"],
            "nodes": ["conditions"],
            "statement": "Cho độ dài ba cạnh a, b, c là các số nguyên dương. In YES nếu chúng tạo thành một tam giác không suy biến, ngược lại in NO.\n\n## Dữ liệu vào\nMột dòng gồm ba số nguyên dương a, b, c (~1 \\le a, b, c \\le 10^{9}~).\n\n## Dữ liệu ra\nIn YES hoặc NO. Tam giác không suy biến khi tổng của từng cặp cạnh lớn hơn cạnh còn lại; trường hợp tổng bằng cạnh còn lại không tạo thành tam giác.",
            "samples": [{"input": "3 4 5\n", "output": "YES\n", "explanation": "Các tổng 3 + 4, 3 + 5 và 4 + 5 đều lớn hơn cạnh còn lại."}, {"input": "1 2 3\n", "output": "NO\n", "explanation": "1 + 2 bằng 3 nên ba cạnh chỉ tạo thành hình suy biến."}],
            "explanation": "Kiểm tra cả ba bất đẳng thức tam giác: a + b > c, a + c > b và b + c > a. Dùng số nguyên 64-bit để phép cộng an toàn với giới hạn đã cho.",
            "complexity": "O(1) thời gian, O(1) bộ nhớ.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long a, b, c;\n    cin >> a >> b >> c;\n    if (a + b > c && a + c > b && b + c > a) {\n        cout << \"YES\\n\";\n    } else {\n        cout << \"NO\\n\";\n    }\n    return 0;\n}\n",
            "cases": trianglecheck_cases,
            "oracle": oracle_trianglecheck,
            "function_practice": False,
        },
        {
            "code": "msb_grade",
            "title": "Xếp loại theo điểm số",
            "section": "conditions",
            "group": "foundations",
            "tags": ["conditions"],
            "nodes": ["conditions"],
            "statement": "Cho điểm số nguyên của một học sinh. Hãy in mức xếp loại tương ứng: từ 90 trở lên là XUAT_SAC; từ 80 đến dưới 90 là GIOI; từ 65 đến dưới 80 là KHA; từ 50 đến dưới 65 là DAT; dưới 50 là CHUA_DAT.\n\n## Dữ liệu vào\nMột số nguyên score (~0 \\le score \\le 100~).\n\n## Dữ liệu ra\nIn đúng một trong các chuỗi XUAT_SAC, GIOI, KHA, DAT, CHUA_DAT.",
            "samples": [{"input": "89\n", "output": "GIOI\n", "explanation": "Điểm 89 từ 80 trở lên nhưng nhỏ hơn 90 nên xếp loại GIOI."}, {"input": "90\n", "output": "XUAT_SAC\n", "explanation": "Điểm 90 đạt ngưỡng XUAT_SAC."}],
            "explanation": "Xét các ngưỡng từ cao xuống thấp: 90, 80, 65 rồi 50. Khi điểm nhỏ hơn tất cả các ngưỡng đó, xếp loại là CHUA_DAT.",
            "complexity": "O(1) thời gian, O(1) bộ nhớ.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    int score;\n    cin >> score;\n    if (score >= 90) {\n        cout << \"XUAT_SAC\\n\";\n    } else if (score >= 80) {\n        cout << \"GIOI\\n\";\n    } else if (score >= 65) {\n        cout << \"KHA\\n\";\n    } else if (score >= 50) {\n        cout << \"DAT\\n\";\n    } else {\n        cout << \"CHUA_DAT\\n\";\n    }\n    return 0;\n}\n",
            "cases": grade_cases,
            "oracle": oracle_grade,
            "function_practice": False,
        },
        {
            "code": "msb_sumodd",
            "title": "Tổng các số lẻ dương không vượt quá n",
            "section": "loops",
            "group": "foundations",
            "tags": ["loops", "numeric-safety"],
            "nodes": ["loops"],
            "statement": "Cho số nguyên không âm n. Tính tổng các số lẻ dương không vượt quá n. Nếu không có số nào phù hợp, tổng bằng 0.\n\n## Dữ liệu vào\nMột số nguyên n (~0 \\le n \\le 10^{6}~).\n\n## Dữ liệu ra\nIn tổng cần tìm.",
            "samples": [{"input": "10\n", "output": "25\n", "explanation": "Các số lẻ dương không vượt quá 10 là 1, 3, 5, 7, 9; tổng bằng 25."}, {"input": "0\n", "output": "0\n", "explanation": "Không có số lẻ dương nào không vượt quá 0."}],
            "explanation": "Duyệt các số từ 1 đến n, cộng vào tổng mỗi khi số đang xét là số lẻ. Khi n bằng 0, vòng lặp không thực hiện và tổng vẫn bằng 0.",
            "complexity": "O(n) thời gian, O(1) bộ nhớ.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    long long sum = 0;\n    for (int value = 1; value <= n; ++value) {\n        if (value % 2 == 1) {\n            sum += value;\n        }\n    }\n    cout << sum << '\\n';\n    return 0;\n}\n",
            "cases": sumodd_cases,
            "oracle": oracle_sumodd,
            "function_practice": False,
        },
        {
            "code": "msb_power",
            "title": "Tính lũy thừa bằng phép nhân lặp",
            "section": "loops",
            "group": "foundations",
            "tags": ["loops", "arithmetic", "numeric-safety"],
            "nodes": ["loops"],
            "statement": "Cho số nguyên a và số mũ nguyên không âm n. Tính a mũ n. Quy ước a mũ 0 bằng 1, kể cả khi a bằng 0.\n\n## Dữ liệu vào\nMột dòng gồm hai số nguyên a, n (~-10 \\le a \\le 10~, ~0 \\le n \\le 18~).\n\n## Dữ liệu ra\nIn giá trị a mũ n.",
            "samples": [{"input": "-2 5\n", "output": "-32\n", "explanation": "(-2) mũ 5 bằng -32 vì số mũ lẻ."}, {"input": "0 0\n", "output": "1\n", "explanation": "Theo quy ước của đề bài, a mũ 0 bằng 1 kể cả khi a bằng 0."}],
            "explanation": "Khởi tạo kết quả bằng 1 rồi nhân liên tiếp với a đúng n lần. Khi n bằng 0, không thực hiện phép nhân nào nên kết quả giữ nguyên là 1.",
            "complexity": "O(n) thời gian, O(1) bộ nhớ.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long a, result = 1;\n    int n;\n    cin >> a >> n;\n    for (int i = 0; i < n; ++i) {\n        result *= a;\n    }\n    cout << result << '\\n';\n    return 0;\n}\n",
            "cases": power_cases,
            "oracle": oracle_power,
            "function_practice": False,
        },
    ]
