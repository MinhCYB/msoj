# Đếm cách ghép bằng DP bitmask

## Mục tiêu

Ta có `n` người và `n` công việc. Một ô bằng `1` nghĩa là người đó có thể nhận công việc tương ứng; ô `0` nghĩa là không thể. Hãy đếm số cách ghép sao cho mỗi người và mỗi công việc xuất hiện đúng một lần.

Bài học này dùng DP trên tập hợp để đếm các cách ghép hoàn chỉnh, đồng thời cho phép quan sát từng đóng góp vào trạng thái. Ma trận ví dụ có ba cách ghép hoàn chỉnh.

```msoj-visual
{
  "version": 2,
  "id": "legacy-dp-bitmask-matching",
  "title": "Dp Bitmask Matching",
  "summary": "Mô phỏng dp-bitmask-matching xác định; mã nguồn chỉ dùng để đọc.",
  "data": {
    "compatibility": {
      "type": "matrix",
      "values": [
        [
          0,
          1,
          1
        ],
        [
          1,
          0,
          1
        ],
        [
          1,
          1,
          1
        ]
      ]
    },
    "dp": {
      "type": "sequence",
      "values": [
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0
      ],
      "itemIds": [
        "mask-0",
        "mask-1",
        "mask-2",
        "mask-3",
        "mask-4",
        "mask-5",
        "mask-6",
        "mask-7"
      ]
    },
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
                "mask": 0,
                "person": 0,
                "job": null,
                "next_mask": null
              }
            }
          ]
        }
      ]
    },
    "witness": {
      "type": "table",
      "columns": [
        {
          "id": "person",
          "type": "number"
        },
        {
          "id": "job",
          "type": "number"
        }
      ],
      "rows": []
    }
  },
  "modules": [
    {
      "id": "compatibility-view",
      "type": "matrix",
      "source": "compatibility"
    },
    {
      "id": "dp-view",
      "type": "vector",
      "source": "dp",
      "caption": "Số cách theo mask"
    },
    {
      "id": "witness-view",
      "type": "table",
      "source": "witness",
      "caption": "Một ghép cặp hợp lệ"
    },
    {
      "id": "variables-view",
      "type": "variables",
      "source": "variables"
    },
    {
      "id": "explanation",
      "type": "explanation",
      "content": [
        {
          "type": "text",
          "value": "Mỗi bit bật gán một người; quy hoạch động đếm các phép gán tương thích."
        }
      ]
    },
    {
      "id": "source",
      "type": "code",
      "caption": "Mã nguồn chỉ để đọc",
      "sources": [
        {
          "language": "cpp",
          "sourceCode": "#include <bit>\n#include <vector>\nlong long count_matchings(const std::vector<std::vector<int>>& compatible) {\n    const int n = static_cast<int>(compatible.size());\n    for (int mask = 0; mask < (1 << n); ++mask) {\n        const int person = std::popcount(static_cast<unsigned>(mask));\n        for (int job = 0; job < n; ++job) {\n            if ((mask & (1 << job)) || !compatible[person][job]) continue;\n            dp[mask | (1 << job)] += dp[mask];\n        }\n    }\n    return dp[(1 << n) - 1];\n}",
          "lineIds": [
            "dp-bitmask-matching-include-1",
            "dp-bitmask-matching-include-2",
            "dp-bitmask-matching-function-1",
            "dp-bitmask-matching-init-1",
            "dp-bitmask-matching-mask-1",
            "dp-bitmask-matching-person-1",
            "dp-bitmask-matching-job-1",
            "dp-bitmask-matching-check-1",
            "dp-bitmask-matching-transition-1",
            "dp-bitmask-matching-close-1",
            "dp-bitmask-matching-close-2",
            "dp-bitmask-matching-return-1",
            "dp-bitmask-matching-close-3"
          ]
        },
        {
          "language": "python",
          "sourceCode": "def count_matchings(compatible):\n    n = len(compatible)\n    dp = [0] * (1 << n)\n    dp[0] = 1\n    for mask in range(1 << n):\n        person = mask.bit_count()\n        for job in range(n):\n            if mask & (1 << job) or not compatible[person][job]:\n                continue\n            dp[mask | (1 << job)] += dp[mask]\n    return dp[(1 << n) - 1]",
          "lineIds": [
            "dp-bitmask-matching-function-1",
            "dp-bitmask-matching-init-1",
            "dp-bitmask-matching-init-2",
            "dp-bitmask-matching-base-1",
            "dp-bitmask-matching-mask-1",
            "dp-bitmask-matching-person-1",
            "dp-bitmask-matching-job-1",
            "dp-bitmask-matching-check-1",
            "dp-bitmask-matching-check-2",
            "dp-bitmask-matching-transition-1",
            "dp-bitmask-matching-return-1"
          ]
        }
      ]
    }
  ],
  "layout": {
    "areas": [
      ["compatibility-view", "compatibility-view", "source", "source"],
      ["dp-view", "dp-view", "witness-view", "witness-view"],
      ["variables-view", "variables-view", "variables-view", "variables-view"],
      ["explanation", "explanation", "explanation", "explanation"]
    ],
    "readingOrder": [
      "compatibility-view",
      "source",
      "dp-view",
      "witness-view",
      "variables-view",
      "explanation"
    ]
  },
  "timeline": {
    "generator": "dp-bitmask-matching",
    "input": {
      "matrix": [
        [
          0,
          1,
          1
        ],
        [
          1,
          0,
          1
        ],
        [
          1,
          1,
          1
        ]
      ]
    }
  }
}
```
## Mô hình trạng thái

Đánh số người và công việc từ `0` trong thuật toán. `mask` là tập công việc đã được dùng: bit `j` bằng `1` khi công việc `j` đã được ghép. `dp[mask]` là số cách ghép **`popcount(mask)` người đầu tiên** với đúng tập công việc trong `mask`.

Người tiếp theo luôn là `i = popcount(mask)`. Vì vậy trạng thái không cần lưu riêng chỉ số người. Ví dụ, mask `101` (bit phải nhất là công việc 0) biểu diễn việc đã dùng công việc 0 và 2; nó nằm ở lớp 2, nên hai người đầu đã được ghép.

- `dp[0] = 1`: trước khi ghép ai, có đúng một cách rỗng.
- Các trạng thái khác bắt đầu bằng 0 cách.
- Với mỗi người `i`, thử từng công việc tương thích `j` chưa dùng. Tạo `next = mask | (1 << j)` rồi cộng `dp[mask]` vào `dp[next]`.
- Các mask được xét theo thứ tự tăng dần. Thêm một bit luôn tạo số lớn hơn mask cũ, nên mọi đóng góp đến một trạng thái trước khi trạng thái ấy được xử lý.

## Quan sát trước, trong và sau

Trước khi chạy, hãy dự đoán `dp[0]` và lớp của mask `000`. Trong khi chạy, chú ý cạnh tương thích đang được thử: cạnh thành công làm tăng ô trạng thái đích; cạnh bị chặn vì công việc đã dùng hoặc không tương thích không làm thay đổi DP. Có thể chọn bất kỳ ô DP để kiểm tra các phép gán từng phần được đếm **ở đúng khung hiện tại**. Trạng thái chưa tính được phân biệt với trạng thái đã tính có giá trị 0.

Sau khi xử lý mọi mask, trạng thái đầy đủ `(1 << n) - 1` chứa số cách ghép hoàn chỉnh. Với ma trận mặc định, có ba cách: (người 1→công việc 2, người 2→công việc 1, người 3→công việc 3); (người 1→công việc 2, người 2→công việc 3, người 3→công việc 1); hoặc (người 1→công việc 3, người 2→công việc 1, người 3→công việc 2).

## Vì sao phép chuyển đúng?

Mỗi cách ghép được đếm trong `dp[mask]` đã gán đúng các công việc của mask cho đúng `popcount(mask)` người đầu. Người kế tiếp chỉ có thể nhận một công việc tương thích còn trống. Mỗi lựa chọn như vậy tạo ra đúng một cách ghép mới của tập mở rộng, nên cộng toàn bộ `dp[mask]` vào `dp[next]`.

Ngược lại, mọi cách ghép từng phần của `next` đều có một công việc cuối cùng được gán cho người cuối trong nhóm. Bỏ cặp cuối ấy đi sẽ thu được duy nhất một trạng thái trước đó và một chuyển tiếp hợp lệ. Do đó cách nào cũng được cộng đúng một lần. Bitmask bảo đảm không lặp công việc; thứ tự người bảo đảm không lặp thứ tự ghép của cùng một tập cặp.

## Đầu vào, trường hợp biên và chi phí

Ma trận phải vuông, có từ 1 đến 5 hàng, và mọi phần tử phải là số `0` hoặc `1`. Không có cách ghép hoàn chỉnh thì giá trị cuối là `0`; các trạng thái giữa chừng vẫn có thể có cách. Nếu ma trận toàn số 0, chỉ `dp[0] = 1`, còn kết quả cuối bằng 0. Nếu mọi ô là 1, kết quả là `n!`; với `n = 4`, kết quả là 24.

Có `2^n` trạng thái và mỗi trạng thái thử tối đa `n` công việc, nên thuật toán dùng thời gian `O(n·2^n)` và bộ nhớ `O(2^n)`. Bản trực quan còn giữ các phép gán từng phần để phục vụ kiểm tra trạng thái; phần ghi nhận này là chi phí bổ sung dành cho việc học, không phải yêu cầu của thuật toán DP tối ưu bộ nhớ.

## Tự kiểm tra và luyện tập

1. Vì sao `dp[0]` là 1 chứ không phải 0?
2. Tại một mask có hai bit bật, người nào được xét tiếp? Có thể suy ra mà không lưu chỉ số người không?
3. Trước khi chạy, dự đoán kết quả với ma trận toàn 1 kích thước `4 × 4`, rồi xác nhận bằng trạng thái cuối.
4. Thử ma trận toàn 0. Chọn một trạng thái ở giữa và phân biệt “chưa tính” với “đã tính nhưng có 0 cách”.
5. Tạo một ma trận nhỏ có một số cách ghép bị chặn. Theo dõi một cạnh thành công và kiểm tra các witness của ô đích có đúng bằng giá trị DP tại khung đó không.
