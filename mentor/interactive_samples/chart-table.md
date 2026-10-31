# Đọc biểu đồ cùng bảng dữ liệu

## Mục tiêu

Biểu đồ cột tóm tắt số bài luyện tập theo buổi; bảng bên cạnh giữ nguyên các giá trị để người đọc có thể đối chiếu chính xác.

```msoj-visual
{
  "version": 2,
  "id": "weekly-practice",
  "title": "Số bài luyện tập trong tuần",
  "summary": "Minh có ba buổi luyện tập, lần lượt giải 2, 5 và 3 bài.",
  "data": {
    "practice": {
      "type": "table",
      "columns": [{"id": "day", "type": "string"}, {"id": "count", "type": "number"}],
      "rows": [{"id": "mon", "day": "Thứ hai", "count": 2}, {"id": "wed", "day": "Thứ tư", "count": 5}, {"id": "fri", "day": "Thứ sáu", "count": 3}]
    }
  },
  "modules": [
    {"id": "chart", "type": "chart", "source": "practice", "kind": "bar", "x": "day", "y": "count", "caption": "Số bài theo buổi"},
    {"id": "table", "type": "table", "source": "practice", "caption": "Dữ liệu số bài theo buổi"}
  ],
  "layout": {"areas": [["chart", "table"]], "readingOrder": ["chart", "table"]}
}
```

Biểu đồ và bảng cùng trỏ đến một tập dữ liệu có kiểu; sửa dữ liệu trong tài liệu sẽ cập nhật đồng bộ cả hai cách biểu diễn.
