import random


def problems():
    def oracle_expression(text):
        a, b, c = map(int, text.split())
        return f"{(a + b) * c}\n"

    def oracle_divmod(text):
        n, k = map(int, text.split())
        return f"{n // k} {n % k}\n"

    def oracle_time(text):
        t = int(text)
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{h} {m} {s}\n"

    def oracle_compare(text):
        a, b = map(int, text.split())
        return ("LESS" if a < b else "GREATER" if a > b else "EQUAL") + "\n"

    def oracle_leapyear(text):
        year = int(text)
        leap = year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)
        return ("YES" if leap else "NO") + "\n"

    def oracle_ticket(text):
        age = int(text)
        price = 0 if age < 6 else 10000 if age < 18 else 20000 if age < 60 else 15000
        return f"{price}\n"

    def oracle_sum(text):
        n = int(text)
        return f"{n * (n + 1) // 2}\n"

    def oracle_countmultiples(text):
        values = list(map(int, text.split()))
        _, k = values[:2]
        return str(sum(value % k == 0 for value in values[2:])) + "\n"

    def oracle_factorial(text):
        n = int(text)
        result = 1
        for value in range(2, n + 1):
            result *= value
        return f"{result}\n"

    expression_cases = ["0 0 0\n", "1 2 3\n", "-1000000000 1000000000 1000000000\n", "-5 -7 -3\n", "1000000000 1000000000 -1000000000\n"]
    expression_rng = random.Random(211)
    expression_cases += [f"{expression_rng.randint(-1000000000, 1000000000)} {expression_rng.randint(-1000000000, 1000000000)} {expression_rng.randint(-1000000000, 1000000000)}\n" for _ in range(7)]

    divmod_cases = ["0 1\n", "10 3\n", "1000000000000 1\n", "1000000000000 1000000\n", "1 1000000\n"]
    divmod_rng = random.Random(212)
    divmod_cases += [f"{divmod_rng.randint(0, 10**12)} {divmod_rng.randint(1, 10**6)}\n" for _ in range(7)]

    time_cases = ["0\n", "59\n", "60\n", "3600\n", "3661\n", "86400\n", "1000000000\n"]
    time_rng = random.Random(213)
    time_cases += [f"{time_rng.randint(0, 10**9)}\n" for _ in range(5)]

    compare_cases = ["1 2\n", "2 1\n", "-5 -5\n", "0 -1\n", "1000000000 -1000000000\n"]
    compare_rng = random.Random(214)
    compare_cases += [f"{compare_rng.randint(-10**9, 10**9)} {compare_rng.randint(-10**9, 10**9)}\n" for _ in range(7)]

    leapyear_cases = ["1\n", "4\n", "100\n", "400\n", "1900\n", "2000\n", "2024\n", "9999\n"]
    leapyear_rng = random.Random(215)
    leapyear_cases += [f"{leapyear_rng.randint(1, 9999)}\n" for _ in range(4)]

    ticket_cases = ["0\n", "5\n", "6\n", "17\n", "18\n", "59\n", "60\n", "120\n"]
    ticket_rng = random.Random(216)
    ticket_cases += [f"{ticket_rng.randint(0, 120)}\n" for _ in range(4)]

    sum_cases = ["0\n", "1\n", "2\n", "10\n", "1000000\n"]
    sum_rng = random.Random(217)
    sum_cases += [f"{sum_rng.randint(0, 1000000)}\n" for _ in range(7)]

    multiples_cases = ["1 1\n0\n", "3 3\n-3 0 4\n", "4 2\n1 3 5 7\n", "3 1000\n-1000000 1000000 0\n",
                       "1 7\n-1\n", "1 7\n7\n", "10000 1\n" + " ".join(["-1000000"] * 10000) + "\n"]
    multiples_rng = random.Random(218)
    for n in (2, 10, 100, 1000, 10000):
        k = multiples_rng.randint(1, 1000)
        multiples_cases.append(f"{n} {k}\n" + " ".join(str(multiples_rng.randint(-10**6, 10**6)) for _ in range(n)) + "\n")

    factorial_cases = [f"{n}\n" for n in range(21)]

    return [
        {
            "code": "msb_expression",
            "title": "Tính biểu thức đơn giản",
            "section": "io",
            "group": "foundations",
            "tags": ["programming-basics", "arithmetic", "numeric-safety"],
            "nodes": ["programming-basics", "io-and-numeric-safety"],
            "statement": "Cho ba số nguyên ~a~, ~b~, ~c~. Hãy tính giá trị biểu thức ~(a+b)\u00d7c~.\n\n## Dữ liệu vào\nMột dòng gồm ba số nguyên ~a~, ~b~, ~c~ (~|a|, |b|, |c| \u2264 10^9~).\n\n## Dữ liệu ra\nIn giá trị của ~(a+b)\u00d7c~.",
            "samples": [{"input": "2 3 4\n", "output": "20\n", "explanation": "Cộng trước: ~2+3=5~, sau đó ~5\u00d74=20~."}],
            "explanation": "Đọc ba số nguyên, tính tổng ~a+b~ rồi nhân tổng đó với ~c~. Phép tính trung gian và kết quả có thể vượt phạm vi số nguyên 32-bit; dùng kiểu số nguyên 64-bit trong C++.\n\nĐộ phức tạp thời gian: ~O(1)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long a, b, c;\n    cin >> a >> b >> c;\n    cout << (a + b) * c << '\\n';\n    return 0;\n}\n",
            "cases": expression_cases,
            "oracle": oracle_expression,
            "function_practice": False,
        },
        {
            "code": "msb_divmod",
            "title": "Chia đều đồ vật",
            "section": "io",
            "group": "foundations",
            "tags": ["programming-basics", "io-basics", "arithmetic"],
            "nodes": ["programming-basics", "io-and-numeric-safety"],
            "statement": "Có ~n~ đồ vật cần chia đều cho ~k~ người. Hãy cho biết mỗi người nhận được bao nhiêu đồ vật và còn dư bao nhiêu.\n\n## Dữ liệu vào\nMột dòng gồm hai số nguyên ~n~ và ~k~ (~0 \\le n \\le 10^{12}~, ~1 \\le k \\le 10^6~).\n\n## Dữ liệu ra\nIn thương nguyên và số dư, theo thứ tự, cách nhau bởi một dấu cách.",
            "samples": [{"input": "17 5\n", "output": "3 2\n", "explanation": "Mỗi người nhận ~3~ đồ vật; còn lại ~2~ đồ vật."}],
            "explanation": "Dùng phép chia nguyên để tìm thương ~n/k~ và phép chia lấy dư để tìm ~n%k~. Mẫu số luôn dương nên phép chia và số dư có ý nghĩa trực tiếp.\n\nĐộ phức tạp thời gian: ~O(1)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long n, k;\n    cin >> n >> k;\n    cout << n / k << ' ' << n % k << '\\n';\n    return 0;\n}\n",
            "cases": divmod_cases,
            "oracle": oracle_divmod,
            "function_practice": False,
        },
        {
            "code": "msb_time",
            "title": "Đổi giây thành giờ, phút, giây",
            "section": "io",
            "group": "foundations",
            "tags": ["programming-basics", "arithmetic", "io-basics"],
            "nodes": ["programming-basics", "io-and-numeric-safety"],
            "statement": "Cho tổng thời gian ~t~ tính bằng giây. Hãy đổi thành số giờ, phút và giây. Số giờ không giới hạn trong một ngày.\n\n## Dữ liệu vào\nMột số nguyên ~t~ (~0 \u2264 t \u2264 10^9~).\n\n## Dữ liệu ra\nIn số giờ, số phút còn lại và số giây còn lại, cách nhau bởi dấu cách.",
            "samples": [{"input": "3661\n", "output": "1 1 1\n", "explanation": "~3661~ giây gồm ~1~ giờ, ~1~ phút và ~1~ giây."}],
            "explanation": "Một giờ có ~3600~ giây. Chia ~t~ cho ~3600~ để lấy số giờ; tiếp tục chia phần dư cho ~60~ để lấy phút và số giây còn lại. Không lấy số giờ theo modulo 24.\n\nĐộ phức tạp thời gian: ~O(1)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long t;\n    cin >> t;\n    long long hours = t / 3600;\n    long long remainder = t % 3600;\n    long long minutes = remainder / 60;\n    long long seconds = remainder % 60;\n    cout << hours << ' ' << minutes << ' ' << seconds << '\\n';\n    return 0;\n}\n",
            "cases": time_cases,
            "oracle": oracle_time,
            "function_practice": False,
        },
        {
            "code": "msb_compare",
            "title": "So sánh hai số",
            "section": "conditions",
            "group": "foundations",
            "tags": ["programming-basics", "conditions"],
            "nodes": ["programming-basics", "casework"],
            "statement": "Cho hai số nguyên ~a~ và ~b~. Hãy xác định số nào nhỏ hơn hoặc hai số có bằng nhau.\n\n## Dữ liệu vào\nMột dòng gồm hai số nguyên ~a~ và ~b~ (~|a|, |b| \u2264 10^9~).\n\n## Dữ liệu ra\nIn ~LESS~ nếu ~a<b~, ~EQUAL~ nếu ~a=b~, hoặc ~GREATER~ nếu ~a>b~.",
            "samples": [{"input": "7 3\n", "output": "GREATER\n", "explanation": "Vì ~7>3~, kết quả là ~GREATER~."}],
            "explanation": "Dùng cấu trúc điều kiện để lần lượt kiểm tra ~a<b~ và ~a>b~. Nếu cả hai đều sai thì hai số bằng nhau.\n\nĐộ phức tạp thời gian: ~O(1)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    long long a, b;\n    cin >> a >> b;\n    if (a < b) cout << \"LESS\\n\";\n    else if (a > b) cout << \"GREATER\\n\";\n    else cout << \"EQUAL\\n\";\n    return 0;\n}\n",
            "cases": compare_cases,
            "oracle": oracle_compare,
            "function_practice": False,
        },
        {
            "code": "msb_leapyear",
            "title": "Năm nhuận theo lịch Gregory",
            "section": "conditions",
            "group": "foundations",
            "tags": ["programming-basics", "conditions"],
            "nodes": ["programming-basics", "casework"],
            "statement": "Theo lịch Gregory, một năm nhuận chia hết cho ~400~, hoặc chia hết cho ~4~ nhưng không chia hết cho ~100~. Cho năm ~y~, hãy xác định năm đó có nhuận không.\n\n## Dữ liệu vào\nMột số nguyên ~y~ (~1 \u2264 y \u2264 9999~).\n\n## Dữ liệu ra\nIn ~YES~ nếu là năm nhuận, ngược lại in ~NO~.",
            "samples": [{"input": "1900\n", "output": "NO\n", "explanation": "~1900~ chia hết cho ~100~ nhưng không chia hết cho ~400~, nên không phải năm nhuận."}, {"input": "2000\n", "output": "YES\n", "explanation": "~2000~ chia hết cho ~400~, nên là năm nhuận."}],
            "explanation": "Kiểm tra điều kiện chia hết cho ~400~ trước. Nếu không, năm chỉ nhuận khi chia hết cho ~4~ và không chia hết cho ~100~. Thứ tự điều kiện này xử lý đúng các năm tròn thế kỷ.\n\nĐộ phức tạp thời gian: ~O(1)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    int year;\n    cin >> year;\n    if (year % 400 == 0 || (year % 4 == 0 && year % 100 != 0)) cout << \"YES\\n\";\n    else cout << \"NO\\n\";\n    return 0;\n}\n",
            "cases": leapyear_cases,
            "oracle": oracle_leapyear,
            "function_practice": False,
        },
        {
            "code": "msb_ticket",
            "title": "Tính giá vé theo độ tuổi",
            "section": "conditions",
            "group": "foundations",
            "tags": ["programming-basics", "conditions"],
            "nodes": ["programming-basics", "casework"],
            "statement": "Giá vé phụ thuộc vào tuổi: dưới ~6~ tuổi được miễn phí; từ ~6~ đến ~17~ tuổi giá ~10000~ đồng; từ ~18~ đến ~59~ tuổi giá ~20000~ đồng; từ ~60~ tuổi trở lên giá ~15000~ đồng. Hãy tính giá vé.\n\n## Dữ liệu vào\nMột số nguyên ~age~ (~0 \u2264 age \u2264 120~).\n\n## Dữ liệu ra\nIn giá vé phải trả bằng đồng.",
            "samples": [{"input": "17\n", "output": "10000\n", "explanation": "Tuổi ~17~ thuộc nhóm từ ~6~ đến ~17~, nên giá vé là ~10000~ đồng."}, {"input": "60\n", "output": "15000\n", "explanation": "Tuổi ~60~ thuộc nhóm từ ~60~ trở lên."}],
            "explanation": "Xét các mốc tuổi theo thứ tự tăng dần: dưới ~6~, dưới ~18~, dưới ~60~, còn lại. Mỗi nhánh gán đúng giá đã cho.\n\nĐộ phức tạp thời gian: ~O(1)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    int age;\n    cin >> age;\n    if (age < 6) cout << 0 << '\\n';\n    else if (age < 18) cout << 10000 << '\\n';\n    else if (age < 60) cout << 20000 << '\\n';\n    else cout << 15000 << '\\n';\n    return 0;\n}\n",
            "cases": ticket_cases,
            "oracle": oracle_ticket,
            "function_practice": False,
        },
        {
            "code": "msb_sum",
            "title": "Tính tổng từ 1 đến n",
            "section": "loops",
            "group": "foundations",
            "tags": ["programming-basics", "loops", "numeric-safety"],
            "nodes": ["programming-basics"],
            "statement": "Cho số nguyên không âm ~n~. Hãy tính tổng ~1+2+...+n~ bằng cách lặp cộng lần lượt các số từ ~1~ đến ~n~. Quy ước tổng bằng ~0~ khi ~n=0~.\n\n## Dữ liệu vào\nMột số nguyên ~n~ (~0 \u2264 n \u2264 10^6~).\n\n## Dữ liệu ra\nIn tổng cần tìm.",
            "samples": [{"input": "5\n", "output": "15\n", "explanation": "Cộng lần lượt được ~1+2+3+4+5=15~."}, {"input": "0\n", "output": "0\n", "explanation": "Không có số nào trong dãy cần cộng nên tổng là ~0~."}],
            "explanation": "Khởi tạo tổng bằng ~0~, sau đó dùng vòng lặp cộng từng giá trị từ ~1~ đến ~n~. Dùng kiểu số nguyên 64-bit để lưu tổng.\n\nĐộ phức tạp thời gian: ~O(n)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    long long total = 0;\n    for (int value = 1; value <= n; ++value) {\n        total += value;\n    }\n    cout << total << '\\n';\n    return 0;\n}\n",
            "cases": sum_cases,
            "oracle": oracle_sum,
            "function_practice": False,
        },
        {
            "code": "msb_countmultiples",
            "title": "Đếm bội số của k",
            "section": "loops",
            "group": "foundations",
            "tags": ["programming-basics", "loops", "conditions"],
            "nodes": ["programming-basics"],
            "statement": "Cho dãy gồm ~n~ số nguyên và số nguyên dương ~k~. Đếm số phần tử chia hết cho ~k~. Giá trị 0 cũng chia hết cho ~k~.\n\n## Dữ liệu vào\nDòng đầu chứa ~n,k~ (~1 \\le n \\le 10^4~, ~1 \\le k \\le 1000~). Dòng thứ hai chứa ~n~ số nguyên ~a_i~, ~|a_i| \\le 10^6~.\n\n## Dữ liệu ra\nMột số nguyên là số phần tử chia hết cho ~k~.",
            "samples": [{"input": "5 3\n-6 0 2 9 10\n", "output": "3\n", "explanation": "Ba phần tử chia hết cho 3 là -6, 0 và 9."}],
            "explanation": "Đọc từng phần tử và kiểm tra phần dư khi chia cho k. Tăng biến đếm nếu phần dư bằng 0, kể cả khi phần tử âm hoặc bằng 0. Không cần lưu cả dãy.\n\nThời gian O(n), bộ nhớ phụ O(1).",
            "cpp": "#include <iostream>\nusing namespace std;\nint main() {\n    int n, k; cin >> n >> k;\n    int count = 0;\n    for (int i = 0; i < n; ++i) {\n        int x; cin >> x;\n        if (x % k == 0) ++count;\n    }\n    cout << count << '\\n';\n}\n",
            "cases": multiples_cases,
            "oracle": oracle_countmultiples,
            "function_practice": False,
        },
        {
            "code": "msb_factorial",
            "title": "Tính giai thừa",
            "section": "loops",
            "group": "foundations",
            "tags": ["programming-basics", "loops", "numeric-safety"],
            "nodes": ["programming-basics"],
            "statement": "Với số nguyên không âm ~n~, giai thừa được định nghĩa là ~n!=1\u00d72\u00d7...\u00d7n~ khi ~n>0~, và ~0!=1~. Hãy tính ~n!~.\n\n## Dữ liệu vào\nMột số nguyên ~n~ (~0 \u2264 n \u2264 20~).\n\n## Dữ liệu ra\nIn giá trị của ~n!~.",
            "samples": [{"input": "5\n", "output": "120\n", "explanation": "~5!=1\u00d72\u00d73\u00d74\u00d75=120~."}, {"input": "0\n", "output": "1\n", "explanation": "Theo định nghĩa, ~0!=1~."}],
            "explanation": "Khởi tạo tích bằng ~1~, rồi lần lượt nhân với các số từ ~2~ đến ~n~. Khởi tạo như vậy cũng cho đúng trường hợp ~n=0~. Kết quả lớn nên dùng kiểu số nguyên 64-bit; với ~n \u2264 20~, giá trị vẫn nằm trong phạm vi kiểu này.\n\nĐộ phức tạp thời gian: ~O(n)~; bộ nhớ: ~O(1)~.",
            "cpp": "#include <iostream>\nusing namespace std;\n\nint main() {\n    int n;\n    cin >> n;\n    long long result = 1;\n    for (int value = 2; value <= n; ++value) {\n        result *= value;\n    }\n    cout << result << '\\n';\n    return 0;\n}\n",
            "cases": factorial_cases,
            "oracle": oracle_factorial,
            "function_practice": False,
        },
    ]
