# Tổng tiền tố cho một đoạn con

Chỉ số 0-based, đoạn nửa mở `[l, r)`. Tổng tiền tố có thêm phần tử đầu bằng 0.

```msoj-visual
{"version":2,"id":"prefix-sum-range","title":"Tổng tiền tố và tổng đoạn","summary":"Đổi l, r để xem vùng chọn và tổng đoạn. Khi l lớn hơn r, đoạn rỗng có tổng 0.","data":{"values":{"type":"sequence","values":[3,-2,5,1,4]}},"modules":[{"id":"array","type":"vector","source":"values","caption":"Mảng A — đoạn [l, r)"},{"id":"prefix","type":"vector","source":"values","caption":"Tổng tiền tố P"},{"id":"formula","type":"explanation","content":[{"type":"text","value":"Tổng đoạn = "},{"type":"value","source":"interval-total","key":"value"}]}],"layout":{"areas":[["array"],["prefix"],["formula"]],"readingOrder":["array","prefix","formula"]},"controls":[{"id":"left","label":"l — chỉ số đầu","type":"number","min":0,"max":5,"step":1,"value":1},{"id":"right","label":"r — cận cuối không kể","type":"number","min":0,"max":5,"step":1,"value":4}],"bindings":[{"id":"selected-range","operation":"slice","args":["values","left","right"],"target":"array"},{"id":"prefix-values","operation":"prefix-sum","args":["values"],"target":"prefix"},{"id":"interval-total","operation":"range-sum","args":["values","left","right"],"target":"formula"}]}
```

`[1, 4)` có tổng 4; `[2, 3)` có tổng 5; `[0, 5)` có tổng 11; `[2, 2)` có tổng 0. Tổng tiền tố: `[0, 3, 1, 6, 7, 11]`.
