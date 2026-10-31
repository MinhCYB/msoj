# Di chuyển đầu mút của đoạn thẳng

Dùng các ô tọa độ, phím mũi tên trên điểm A hoặc kéo điểm để thay đổi đồng thời hình vẽ và đoạn AB. Tọa độ màn hình tăng sang phải và xuống dưới.

```msoj-visual
{"version":2,"id":"segment-geometry","title":"Điểm và đoạn thẳng","summary":"Di chuyển điểm A trong vùng 600×300; đầu mút đoạn AB đi theo A.","data":{"drawing":{"type":"scene","width":600,"height":300,"primitives":[{"id":"segment-ab","type":"segment","x1":100,"y1":220,"x2":500,"y2":60,"label":"AB"},{"id":"point-a","type":"point","x":100,"y":220,"label":"Điểm A","xControl":"point-x","yControl":"point-y"},{"id":"point-b","type":"point","x":500,"y":60,"label":"Điểm B"}]}},"modules":[{"id":"geometry","type":"scene","source":"drawing","caption":"Điểm A di chuyển, điểm B cố định"}],"layout":{"areas":[["geometry"]],"readingOrder":["geometry"]},"controls":[{"id":"point-x","type":"number","label":"Tọa độ x của A","min":0,"max":600,"step":1,"value":100},{"id":"point-y","type":"number","label":"Tọa độ y của A","min":0,"max":300,"step":1,"value":220}],"bindings":[{"id":"move-a","operation":"scene-point","args":["drawing","point-a","point-x","point-y"],"target":"geometry"}]}
```

Đầu mút đoạn được liên kết với điểm có tọa độ ban đầu trùng khớp; các đầu mút khác giữ nguyên. Có thể nhập tọa độ thay cho kéo thả.
