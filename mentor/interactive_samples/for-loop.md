# Vòng lặp `for`: cộng từ 1 đến 4

Vòng `for` lặp lại thân lệnh. Hãy dự đoán tổng sau mỗi lượt rồi xem các bước trong mô phỏng.

```msoj-visual
{
  "version": 2,
  "id": "legacy-for-loop",
  "title": "For Loop",
  "summary": "Mô phỏng for-loop xác định; mã nguồn chỉ dùng để đọc.",
  "data": {
    "variables": {
      "type": "variables",
      "scopes": [
        {
          "id": "main-scope",
          "name": "main",
          "frames": [
            {
              "id": "main-frame",
              "procedure": "main",
              "parameters": {},
              "locals": {
                "start": 1,
                "end": 4,
                "step": 1,
                "i": null,
                "sum": 0
              }
            }
          ]
        }
      ]
    },
    "iterations": {
      "type": "sequence",
      "values": [],
      "itemIds": []
    }
  },
  "modules": [
    {
      "id": "variables-view",
      "type": "variables",
      "source": "variables"
    },
    {
      "id": "iterations-view",
      "type": "vector",
      "source": "iterations"
    },
    {
      "id": "explanation",
      "type": "explanation",
      "content": [
        {
          "type": "text",
          "value": "Mỗi lượt cộng i vào tổng khi i <= end."
        }
      ]
    },
    {
      "id": "output",
      "type": "output",
      "text": ""
    },
    {
      "id": "source",
      "type": "code",
      "caption": "Mã nguồn chỉ để đọc",
      "sources": [
        {
          "language": "cpp",
          "sourceCode": "#include <iostream>\nint main() {\n    int start = 1, end = 4, step = 1;\n    int sum = 0;\n    for (int i = start; i <= end; i += step) {\n        sum += i;\n    }\n    std::cout << sum << '\\n';\n    return 0;\n}",
          "lineIds": [
            "for-loop-init-1",
            "for-loop-init-2",
            "for-loop-init-3",
            "for-loop-init-4",
            "for-loop-loop-1",
            "for-loop-add-1",
            "for-loop-loop-end-1",
            "for-loop-print-1",
            "for-loop-return-1",
            "for-loop-end-1"
          ]
        },
        {
          "language": "python",
          "sourceCode": "start, end, step = 1, 4, 1\ntotal = 0\nfor i in range(start, end + 1, step):\n    total += i\nprint(total)",
          "lineIds": [
            "for-loop-init-1",
            "for-loop-init-2",
            "for-loop-loop-1",
            "for-loop-add-1",
            "for-loop-print-1"
          ]
        }
      ]
    }
  ],
  "layout": {
    "areas": [
      ["iterations-view", "iterations-view", "source", "source"],
      ["variables-view", "variables-view", "output", "output"],
      ["explanation", "explanation", "explanation", "explanation"]
    ],
    "readingOrder": [
      "iterations-view",
      "source",
      "variables-view",
      "output",
      "explanation"
    ]
  },
  "timeline": {
    "generator": "for-loop",
    "input": {
      "start": 1,
      "end": 4,
      "step": 1
    }
  }
}
```
## Ví dụ

Code trong mô phỏng tính tổng từ `start` đến `end`, mỗi lượt tăng `step`.
Với cấu hình ban đầu `start = 1`, `end = 4`, `step = 1`, kết quả in ra là `10`.

Ba phần trong `for (khởi_tạo; điều_kiện; cập_nhật)` chạy theo thứ tự: gán `i = start` một lần; kiểm tra `i <= end`; nếu đúng thì chạy thân; sau thân mới tăng `i` bằng `i += step`, rồi kiểm tra lại. Code và bảng biến hiện cạnh nhau; bấm **Tiếp** hoặc **Trước** để đối chiếu từng dòng, **Đặt lại** để trở về trước khi chạy.

Trong ví dụ này không có biến toàn cục. `start`, `end`, `step`, `i` và `sum` đều được khai báo trong `main()`, nên nằm trong khung biến cục bộ của hàm. `i` khai báo trước vòng `for`, vì vậy vẫn tồn tại sau khi vòng lặp dừng; các biến cục bộ chỉ hết thời gian sống khi `main()` kết thúc.

Các lượt đầu: `i = 1` làm `sum` từ 0 thành 1; `i = 2` làm tổng thành 3; `i = 3` làm tổng thành 6; `i = 4` làm tổng thành 10. Sau đó `i` tăng thành 5; lần kiểm tra `5 <= 4` sai nên 5 không được cộng.

Nếu khởi tạo `i = 5` mà vẫn kiểm tra `i <= 4`, điều kiện sai ngay từ đầu: thân vòng lặp chạy 0 lần và `sum` vẫn bằng 0.

**Lỗi thường gặp:** dùng `< 4` khi muốn tính cả 4; cập nhật biến sai hoặc quên cập nhật; nghĩ thân vòng lặp chạy ít nhất một lần.

**Thử:** dự đoán tổng khi giới hạn đổi thành 3, rồi thử cấu hình không có lượt lặp.

Tham khảo: [W3Schools C++ For Loop](https://www.w3schools.com/cpp/cpp_for_loop.asp).
