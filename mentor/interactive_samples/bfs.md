# BFS: khám phá đồ thị theo từng lớp

## Mục tiêu

Sau bài này, bạn có thể mô tả cách BFS dùng hàng đợi để duyệt một đồ thị không trọng số, giải thích vì sao khoảng cách tìm được là ngắn nhất, và lần theo `parent` để dựng một đường đi.

## Mô hình và trạng thái

Đồ thị trong bài là **vô hướng, đơn**: cạnh `{u, v}` đi được theo cả hai chiều; không có khuyên và không nhập một cạnh hai lần. Các đỉnh mang số từ `0` đến `n - 1`. BFS bắt đầu tại `source`.

Hàng đợi hoạt động theo nguyên tắc vào trước, ra trước. Thuật toán lấy một đỉnh khỏi đầu hàng đợi, rồi xét các láng giềng theo thứ tự số tăng dần. Một đỉnh được đánh dấu `visited` ngay khi được đưa vào hàng đợi, không đợi đến lượt lấy ra. Vì vậy mỗi đỉnh chỉ được xếp hàng tối đa một lần.

Các biến trong trình diễn:

- `Q`: những đỉnh đã phát hiện nhưng chưa lấy ra xử lý.
- `color`: `white` khi chưa phát hiện, `gray` khi đang chờ hoặc đang xử lý, `black` khi đã xử lý xong.
- `d`: số cạnh từ nguồn. `Infinity` là chưa biết; sau khi kết thúc, giá trị này nghĩa là không tới được.
- `pred`: đỉnh phát hiện một đỉnh lần đầu. Nguồn và đỉnh chưa phát hiện có giá trị `null`.
- Bảng trạng thái ghi rõ màu, khoảng cách và cha; màu đồ thị không phải dấu hiệu duy nhất.

## Trước, trong và sau khi chạy

Trước khi kết thúc, hàng đợi rỗng; mọi đỉnh còn `d = Infinity` nằm ngoài thành phần liên thông của nguồn.

## Ví dụ dự đoán

Với cạnh `0–1`, `0–2`, `1–3`, `2–3`, `3–4` và nguồn `0`, thứ tự láng giềng tăng dần khiến `1` và `2` được xếp hàng trước. Dự đoán: khi xử lý `1`, `3` được phát hiện và có `parent[3] = 1`; khi xử lý `2`, `3` đã được đánh dấu nên không bị xếp hàng lần nữa. Vì thế đường đi được ghi nhận tới `3` là `0 → 1 → 3`, dài hai cạnh. Đỉnh `4` có khoảng cách ba.

Chọn **Khám phá thuật toán** để xem pseudocode, đồ thị, hàng đợi và bảng trạng thái trên vùng rộng ngay trong bài. Đồ thị đầu vào có sẵn; mô phỏng tập trung vào quá trình duyệt, không trình diễn từng lệnh tạo danh sách kề. Dừng trước khi phát hiện `3`, rồi quan sát khi cạnh từ `2` tới `3` được xét. Thứ tự láng giềng tăng dần quyết định cha khi có nhiều đường ngắn nhất bằng nhau, không đổi độ dài ngắn nhất.

```msoj-visual
{
  "version": 2,
  "id": "legacy-bfs",
  "title": "Bfs",
  "summary": "Mô phỏng bfs xác định; mã nguồn chỉ dùng để đọc.",
  "data": {
    "graph": {
      "type": "graph",
      "nodes": [
        {
          "id": "v0",
          "label": "0"
        },
        {
          "id": "v1",
          "label": "1"
        },
        {
          "id": "v2",
          "label": "2"
        },
        {
          "id": "v3",
          "label": "3"
        },
        {
          "id": "v4",
          "label": "4"
        }
      ],
      "edges": [
        {
          "id": "edge-0",
          "from": "v0",
          "to": "v1",
          "directed": false
        },
        {
          "id": "edge-1",
          "from": "v0",
          "to": "v2",
          "directed": false
        },
        {
          "id": "edge-2",
          "from": "v1",
          "to": "v3",
          "directed": false
        },
        {
          "id": "edge-3",
          "from": "v2",
          "to": "v3",
          "directed": false
        },
        {
          "id": "edge-4",
          "from": "v3",
          "to": "v4",
          "directed": false
        }
      ]
    },
    "dist": {
      "type": "sequence",
      "values": [
        null,
        null,
        null,
        null,
        null
      ],
      "itemIds": [
        "vertex-0",
        "vertex-1",
        "vertex-2",
        "vertex-3",
        "vertex-4"
      ]
    },
    "parent": {
      "type": "sequence",
      "values": [
        null,
        null,
        null,
        null,
        null
      ],
      "itemIds": [
        "vertex-0",
        "vertex-1",
        "vertex-2",
        "vertex-3",
        "vertex-4"
      ]
    },
    "status": {
      "type": "sequence",
      "values": [
        "undiscovered",
        "undiscovered",
        "undiscovered",
        "undiscovered",
        "undiscovered"
      ],
      "itemIds": [
        "vertex-0",
        "vertex-1",
        "vertex-2",
        "vertex-3",
        "vertex-4"
      ]
    },
    "queue": {
      "type": "sequence",
      "values": [],
      "itemIds": []
    }
  },
  "modules": [
    {
      "id": "graph-view",
      "type": "graph",
      "source": "graph"
    },
    {
      "id": "distance-view",
      "type": "vector",
      "source": "dist",
      "caption": "Khoảng cách"
    },
    {
      "id": "parent-view",
      "type": "vector",
      "source": "parent",
      "caption": "Đỉnh cha"
    },
    {
      "id": "status-view",
      "type": "vector",
      "source": "status",
      "caption": "Trạng thái"
    },
    {
      "id": "queue-view",
      "type": "queue",
      "source": "queue"
    },
    {
      "id": "explanation",
      "type": "explanation",
      "content": [
        {
          "type": "text",
          "value": "Đồ thị vô hướng; duyệt láng giềng theo thứ tự tăng dần."
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
          "sourceCode": "#include <algorithm>\n#include <queue>\n#include <utility>\n#include <vector>\nstd::pair<std::vector<int>, std::vector<int>> bfs(const std::vector<std::vector<int>>& graph, int source) {\n    std::vector<int> distance(graph.size(), -1);\n    std::vector<int> parent(graph.size(), -1);\n    std::queue<int> queue;\n    distance[source] = 0;\n    queue.push(source);\n    while (!queue.empty()) {\n        int vertex = queue.front();\n        queue.pop();\n        auto neighbors = graph[vertex];\n        std::sort(neighbors.begin(), neighbors.end());\n        for (int next : neighbors) {\n            if (distance[next] != -1) continue;\n            distance[next] = distance[vertex] + 1;\n            parent[next] = vertex;\n            queue.push(next);\n        }\n    }\n    return {distance, parent};\n}",
          "lineIds": [
            "bfs-include-1",
            "bfs-include-2",
            "bfs-include-3",
            "bfs-include-4",
            "bfs-function-1",
            "bfs-init-1",
            "bfs-init-2",
            "bfs-init-3",
            "bfs-enqueue-1",
            "bfs-enqueue-2",
            "bfs-while-1",
            "bfs-dequeue-1",
            "bfs-dequeue-2",
            "bfs-sort-1",
            "bfs-sort-2",
            "bfs-neighbor-1",
            "bfs-skip-1",
            "bfs-discover-1",
            "bfs-parent-1",
            "bfs-enqueue-3",
            "bfs-close-1",
            "bfs-close-2",
            "bfs-return-1",
            "bfs-close-3"
          ]
        },
        {
          "language": "python",
          "sourceCode": "from collections import deque\ndef bfs(graph, source):\n    distance = [None] * len(graph)\n    parent = [None] * len(graph)\n    queue = deque()\n    distance[source] = 0\n    queue.append(source)\n    while queue:\n        vertex = queue.popleft()\n        for next_vertex in sorted(graph[vertex]):\n            if distance[next_vertex] is not None:\n                continue\n            distance[next_vertex] = distance[vertex] + 1\n            parent[next_vertex] = vertex\n            queue.append(next_vertex)\n    return distance, parent",
          "lineIds": [
            "bfs-import-1",
            "bfs-function-1",
            "bfs-init-1",
            "bfs-init-2",
            "bfs-init-3",
            "bfs-enqueue-1",
            "bfs-enqueue-2",
            "bfs-while-1",
            "bfs-dequeue-1",
            "bfs-neighbor-1",
            "bfs-skip-1",
            "bfs-skip-2",
            "bfs-discover-1",
            "bfs-parent-1",
            "bfs-enqueue-3",
            "bfs-return-1"
          ]
        }
      ]
    }
  ],
  "layout": {
    "areas": [
      ["graph-view", "graph-view", "source", "source"],
      ["distance-view", "distance-view", "parent-view", "parent-view"],
      ["status-view", "status-view", "queue-view", "queue-view"],
      ["explanation", "explanation", "explanation", "explanation"]
    ],
    "readingOrder": [
      "graph-view",
      "source",
      "distance-view",
      "parent-view",
      "status-view",
      "queue-view",
      "explanation"
    ]
  },
  "timeline": {
    "generator": "bfs",
    "input": {
      "n": 5,
      "edges": [
        [
          0,
          1
        ],
        [
          0,
          2
        ],
        [
          1,
          3
        ],
        [
          2,
          3
        ],
        [
          3,
          4
        ]
      ],
      "source": 0
    }
  }
}
```
## Vì sao BFS tìm được đường ngắn nhất?

BFS xử lý các đỉnh theo từng lớp khoảng cách: trước hết nguồn ở lớp 0, tiếp theo các đỉnh cách nguồn một cạnh, rồi lớp cách hai cạnh, v.v. Hàng đợi FIFO giữ thứ tự này. Khi một đỉnh được phát hiện lần đầu từ `u`, mọi lớp có khoảng cách nhỏ hơn đã được xử lý; do đó không tồn tại đường ngắn hơn tới đỉnh ấy. Gán `dist[v] = dist[u] + 1` và lưu `parent[v] = u` tạo ra một đường đi ngắn nhất.

## Trường hợp biên và giới hạn

Đồ thị có thể rời rạc. Các đỉnh ngoài thành phần của nguồn sẽ không bao giờ được phát hiện. Đỉnh nguồn vẫn có khoảng cách 0 khi không có cạnh. Với `n = 1`, chỉ có nguồn, hàng đợi được xử lý xong và không có cạnh nào cần xét. Đầu vào không chấp nhận `n` ngoài khoảng 1–8, nguồn không hợp lệ, đầu mút ngoài phạm vi, cạnh không đúng hai số nguyên, khuyên hoặc cạnh lặp. Đồ thị rỗng là hợp lệ.

BFS chạy trong `O(V + E)` thời gian và dùng `O(V)` bộ nhớ phụ (ngoài danh sách kề). Ở đây cạnh vô hướng đóng góp hai phần tử vào danh sách kề.

## Tự kiểm tra và luyện tập

1. Trong ví dụ, vì sao `3` chỉ vào hàng đợi một lần dù có hai cạnh nối tới nó?
2. Nếu bỏ cạnh `{3, 4}`, trạng thái cuối của `4` khác gì trạng thái của một đỉnh đã phát hiện?
3. Đổi nguồn thành `4`: hãy dự đoán lớp khoảng cách của từng đỉnh và so sánh với trình diễn.
4. Tạo một đồ thị có hai đường ngắn nhất khác nhau tới cùng một đỉnh. Đổi thứ tự số đỉnh hoặc cạnh để quan sát `parent` có thể đổi, trong khi khoảng cách ngắn nhất vẫn giữ nguyên.
