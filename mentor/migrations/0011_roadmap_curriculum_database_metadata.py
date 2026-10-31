# Frozen snapshot from curriculum_v1.json at migration creation; no runtime manifest dependency.
from django.db import migrations, models

NODES = [
    [
        "foundations",
        "Xây dựng kỹ năng lập trình, phân tích và chuyển yêu cầu thành thuật toán.",
        ""
    ],
    [
        "io-basics",
        "Đọc và ghi dữ liệu, dùng biến, kiểu số và phép toán; kiểm tra chia nguyên, chia dư và giá trị trung gian.",
        "Nhập môn lập trình"
    ],
    [
        "conditions",
        "So sánh và kết hợp điều kiện, viết if/else; chia trường hợp đầy đủ, không chồng lấn và kiểm tra giá trị biên.",
        "Nhập môn lập trình"
    ],
    [
        "loops",
        "Dùng for/while để tích lũy, đếm và xử lý chữ số; xác định khởi tạo, điều kiện dừng và bước cập nhật.",
        "Nhập môn lập trình"
    ],
    [
        "functions",
        "Chia chương trình thành hàm nhỏ, rõ nhiệm vụ; hiểu tham số, giá trị trả về và phạm vi biến.",
        "Nhập môn lập trình"
    ],
    [
        "array-basics",
        "Lưu và duyệt dãy một chiều; tính tổng, tìm cực trị, tìm kiếm tuyến tính, dùng mảng đếm và đánh dấu.",
        "Nhập môn lập trình"
    ],
    [
        "string-basics",
        "Biểu diễn, đọc, duyệt và xử lý ký tự cùng xâu ngắn một cách an toàn.",
        "Nhập môn lập trình"
    ],
    [
        "matrix-basics",
        "Lưu và duyệt dữ liệu dạng bảng bằng hàng, cột và chỉ số hợp lệ.",
        "Nhập môn lập trình"
    ],
    [
        "algorithmic-thinking",
        "Hiểu đề, mô hình hóa, tìm hướng giải và lập luận đúng đắn; dùng bất biến, chia trường hợp và phản ví dụ.",
        "Kỹ năng giải bài nền tảng"
    ],
    [
        "complexity",
        "Ước lượng thời gian và bộ nhớ theo kích thước đầu vào.",
        "Kỹ năng giải bài nền tảng"
    ],
    [
        "implementation",
        "Chuyển mô hình lời giải thành chương trình đúng theo đặc tả.",
        "Kỹ năng giải bài nền tảng"
    ],
    [
        "basic-algorithms",
        "Học các mô hình tìm kiếm và xử lý dãy trước khi kết hợp cấu trúc dữ liệu.",
        ""
    ],
    [
        "brute-force",
        "Duyệt toàn bộ không gian lời giải trong giới hạn cho phép.",
        ""
    ],
    [
        "recursion",
        "Định nghĩa bài toán con, điều kiện dừng và trạng thái lời gọi.",
        ""
    ],
    [
        "backtracking",
        "Xây dựng lời giải từng bước và hoàn tác lựa chọn không phù hợp.",
        ""
    ],
    [
        "branch-and-bound",
        "Dùng cận có chứng minh để loại bỏ nhánh tìm kiếm không thể cải thiện đáp án.",
        ""
    ],
    [
        "binary-search",
        "Tìm biên hoặc đáp án dựa trên điều kiện đơn điệu.",
        ""
    ],
    [
        "two-pointers",
        "Duy trì hai vị trí với bất biến để xử lý dãy hiệu quả.",
        ""
    ],
    [
        "bitwise",
        "Biểu diễn tập nhỏ và thao tác nhị phân bằng phép toán bit.",
        ""
    ],
    [
        "coordinate-compression",
        "Đưa giá trị về chỉ số nhỏ đồng thời bảo toàn quan hệ thứ tự cần thiết.",
        ""
    ],
    [
        "meet-in-the-middle",
        "Chia không gian vét cạn thành hai nửa và kết hợp kết quả.",
        ""
    ],
    [
        "divide-and-conquer",
        "Tách bài toán, giải bài toán con và kết hợp với phân tích độ phức tạp.",
        ""
    ],
    [
        "greedy",
        "Chọn quyết định cục bộ và chứng minh nó dẫn đến lời giải tối ưu.",
        ""
    ],
    [
        "sorting",
        "So sánh thuật toán sắp xếp theo tính ổn định, độ phức tạp và miền dữ liệu.",
        ""
    ],
    [
        "sorting-overview",
        "Chọn thuật toán và tiêu chí so sánh phù hợp với dữ liệu.",
        ""
    ],
    [
        "quadratic-sorts",
        "So sánh ba phương pháp sắp xếp đơn giản với chi phí bậc hai.",
        ""
    ],
    [
        "merge-sort",
        "Trộn các dãy đã sắp xếp để đạt thời gian n log n.",
        ""
    ],
    [
        "quick-sort",
        "Phân hoạch theo chốt và nhận biết trường hợp xấu nhất.",
        ""
    ],
    [
        "heap-sort",
        "Dùng tính chất heap để sắp xếp tại chỗ với thời gian n log n.",
        ""
    ],
    [
        "counting-sort",
        "Sắp xếp bằng đếm tần suất khi miền giá trị đủ nhỏ.",
        ""
    ],
    [
        "radix-sort",
        "Kết hợp các lượt sắp xếp ổn định theo từng phần biểu diễn số.",
        ""
    ],
    [
        "data-structures",
        "Tổ chức dữ liệu theo phép toán và yêu cầu truy vấn.",
        ""
    ],
    [
        "containers",
        "Chọn cấu trúc tuyến tính, heap và tập hoặc ánh xạ phù hợp.",
        ""
    ],
    [
        "data-structures-overview",
        "So sánh chi phí thao tác và lựa chọn cấu trúc theo yêu cầu.",
        ""
    ],
    [
        "array-vector-list",
        "So sánh truy cập chỉ số, chèn xóa và thay đổi kích thước.",
        ""
    ],
    [
        "stack",
        "Quản lý dữ liệu theo thứ tự vào sau ra trước.",
        ""
    ],
    [
        "queue",
        "Quản lý dữ liệu theo thứ tự vào trước ra trước.",
        ""
    ],
    [
        "deque",
        "Thêm và lấy dữ liệu ở cả hai đầu của dãy.",
        ""
    ],
    [
        "monotonic-structures",
        "Duy trì thứ tự đơn điệu để xử lý phần tử lân cận hoặc cửa sổ.",
        ""
    ],
    [
        "heap-priority-queue",
        "Truy xuất phần tử ưu tiên nhất bằng cấu trúc heap.",
        ""
    ],
    [
        "ordered-containers",
        "Dùng cấu trúc có thứ tự với chính sách khóa duy nhất hoặc lặp.",
        ""
    ],
    [
        "hash-table",
        "Lưu tập hoặc ánh xạ có khóa băm và hiểu va chạm cùng chi phí kỳ vọng.",
        ""
    ],
    [
        "bitset",
        "Lưu và xử lý song song tập giá trị Boolean bằng bit.",
        ""
    ],
    [
        "range-queries",
        "Phân biệt dữ liệu tĩnh, cập nhật và truy vấn theo đoạn.",
        ""
    ],
    [
        "queries",
        "Phân biệt truy vấn và cập nhật cùng yêu cầu online hoặc offline.",
        ""
    ],
    [
        "prefix-difference",
        "Chuyển giữa giá trị, tổng tiền tố và thay đổi biên của đoạn.",
        ""
    ],
    [
        "sparse-table",
        "Tiền xử lý truy vấn tĩnh bằng các đoạn độ dài lũy thừa hai.",
        ""
    ],
    [
        "fenwick-tree",
        "Cập nhật và truy vấn tiền tố bằng phân rã chỉ số nhị phân.",
        ""
    ],
    [
        "segment-tree",
        "Tổng hợp thông tin trên các đoạn và hỗ trợ cập nhật hiệu quả.",
        ""
    ],
    [
        "lazy-propagation",
        "Kết hợp phép cập nhật đoạn và phép tổng hợp bằng luật hợp thành đúng.",
        ""
    ],
    [
        "segment-tree-walk",
        "Đi xuống cây theo thông tin tổng hợp để tìm vị trí thỏa điều kiện.",
        ""
    ],
    [
        "segment-tree-engineering",
        "So sánh biến thể cài đặt và chi phí thực tế của cây phân đoạn.",
        ""
    ],
    [
        "sqrt-techniques",
        "Cân bằng kích thước khối và chi phí xử lý truy vấn.",
        ""
    ],
    [
        "sqrt-decomposition",
        "Chia dữ liệu thành khối để cân bằng cập nhật và truy vấn.",
        ""
    ],
    [
        "mo-algorithm",
        "Sắp xếp truy vấn offline để giảm tổng dịch chuyển biên.",
        ""
    ],
    [
        "online-mo",
        "Giữ mục gốc để xác minh nghĩa của biến thể online trước khi biên soạn.",
        ""
    ],
    [
        "sqrt-advanced",
        "Mở rộng xử lý theo khối cho cập nhật và truy vấn trên cây.",
        ""
    ],
    [
        "heavy-light-sets",
        "Chia tập theo kích thước để cân bằng chi phí truy vấn và cập nhật.",
        ""
    ],
    [
        "advanced-data-structures",
        "Giữ các cấu trúc đa chiều, phiên bản và cây cân bằng trong nhánh chuyên sâu.",
        ""
    ],
    [
        "fenwick-2d",
        "Mở rộng cập nhật và tổng tiền tố sang dữ liệu hai chiều.",
        ""
    ],
    [
        "segment-tree-2d",
        "Tổ chức truy vấn hình chữ nhật bằng cây phân đoạn nhiều chiều.",
        ""
    ],
    [
        "persistent-segment-tree",
        "Giữ các phiên bản dữ liệu bằng chia sẻ phần không thay đổi.",
        ""
    ],
    [
        "rollback-segment-tree",
        "Khôi phục trạng thái trước để xử lý nhánh hoặc mốc thời gian offline.",
        ""
    ],
    [
        "order-statistics",
        "Hỗ trợ tìm thứ hạng và phần tử thứ k trên tập có thứ tự.",
        ""
    ],
    [
        "wavelet-tree",
        "Phân hoạch giá trị để trả lời thống kê thứ tự trên đoạn.",
        ""
    ],
    [
        "treap",
        "Kết hợp thứ tự khóa và ưu tiên ngẫu nhiên trong cây tìm kiếm.",
        ""
    ],
    [
        "splay-tree",
        "Tự điều chỉnh cây tìm kiếm và phân tích chi phí khấu hao.",
        ""
    ],
    [
        "skip-list",
        "Dùng các tầng liên kết ngẫu nhiên để tìm kiếm có thứ tự.",
        ""
    ],
    [
        "li-chao-tree",
        "Duy trì cực trị của tập hàm tuyến tính trên miền truy vấn.",
        ""
    ],
    [
        "segment-tree-beats",
        "Dùng thông tin cực trị và phân tích khấu hao cho cập nhật đoạn khó.",
        ""
    ],
    [
        "number-theory",
        "Xây nền số học, tổ hợp và các công cụ toán cho thuật toán.",
        ""
    ],
    [
        "basic-number-theory",
        "Học phép chia, đồng dư, số nguyên tố và cách đếm cơ bản.",
        ""
    ],
    [
        "modulo",
        "Tính toán trên lớp đồng dư và xử lý phần dư nhất quán; phần GCD được tách sang node riêng.",
        ""
    ],
    [
        "gcd-euclid",
        "Dùng thuật toán Euclid để tìm ước chung lớn nhất.",
        ""
    ],
    [
        "binary-exponentiation",
        "Tính lũy thừa qua bình phương liên tiếp.",
        ""
    ],
    [
        "prime-sieve",
        "Tiền xử lý số nguyên tố trong một miền hữu hạn.",
        ""
    ],
    [
        "arithmetic-functions",
        "Tính các hàm liên quan đến ước và phân tích số nguyên.",
        ""
    ],
    [
        "modular-inverse",
        "Xác định điều kiện tồn tại và cách tính nghịch đảo trong đồng dư.",
        ""
    ],
    [
        "binomial",
        "Tính số cách chọn với giới hạn và modulo cụ thể.",
        ""
    ],
    [
        "intermediate-math",
        "Kết nối số học với đếm, xác suất và đại số tuyến tính.",
        ""
    ],
    [
        "extended-euclid",
        "Tìm hệ số Bézout và giải các phương trình tuyến tính nguyên.",
        ""
    ],
    [
        "crt",
        "Kết hợp các điều kiện đồng dư với kiểm tra tính tương thích.",
        ""
    ],
    [
        "primality",
        "Phân biệt kiểm tra trực tiếp và phương pháp cho số nguyên lớn.",
        ""
    ],
    [
        "integer-factorization",
        "Phân tích số nguyên lớn bằng thuật toán phù hợp với miền dữ liệu.",
        ""
    ],
    [
        "euler-phi",
        "Liên hệ số phần tử khả nghịch với lũy thừa modulo.",
        ""
    ],
    [
        "advanced-binomial",
        "Tính hệ số nhị thức khi tiền xử lý cơ bản không còn phù hợp.",
        ""
    ],
    [
        "lucas",
        "Phân rã hệ số nhị thức theo chữ số cơ số nguyên tố.",
        ""
    ],
    [
        "probability",
        "Mô hình hóa biến ngẫu nhiên và áp dụng tính tuyến tính của kỳ vọng.",
        ""
    ],
    [
        "inclusion-exclusion",
        "Đếm hợp các tập bằng cộng trừ giao của chúng.",
        ""
    ],
    [
        "integer-partition",
        "Đếm và mô hình hóa cách phân tích số thành tổng các phần.",
        ""
    ],
    [
        "bignum",
        "Tính toán khi kết quả vượt kiểu số nguyên cố định.",
        ""
    ],
    [
        "matrix",
        "Biểu diễn phép chuyển tuyến tính và tăng tốc lặp bằng lũy thừa.",
        ""
    ],
    [
        "gaussian-elimination",
        "Giải hệ tuyến tính với xử lý hạng, vô nghiệm và miền số.",
        ""
    ],
    [
        "advanced-math",
        "Tách các công cụ số học và đại số có nhiều điều kiện áp dụng.",
        ""
    ],
    [
        "advanced-sieve",
        "Tiền xử lý các hàm số học và truy vấn số nguyên tố nâng cao.",
        ""
    ],
    [
        "mobius",
        "Chuyển quan hệ tổng trên ước bằng hàm Möbius.",
        ""
    ],
    [
        "multiplicative-functions",
        "Khai thác tích trên thừa số nguyên tố và tổng hàm số học.",
        ""
    ],
    [
        "discrete-log",
        "Tìm số mũ trong đồng dư bằng gặp nhau giữa hai dãy.",
        ""
    ],
    [
        "discrete-root",
        "Giải phương trình lũy thừa modulo với các điều kiện tồn tại rõ ràng.",
        ""
    ],
    [
        "modular-square-root",
        "Xử lý trường hợp căn bậc hai bằng thuật toán chuyên biệt.",
        ""
    ],
    [
        "polynomials-series",
        "Mô hình hóa phép toán đại số trên hệ số và chuỗi hình thức.",
        ""
    ],
    [
        "fft",
        "Tính tích chập nhanh với kiểm soát sai số số học.",
        ""
    ],
    [
        "lagrange",
        "Khôi phục hoặc đánh giá đa thức từ giá trị tại các điểm.",
        ""
    ],
    [
        "stern-brocot",
        "Biểu diễn và tìm kiếm phân số theo cấu trúc cây.",
        ""
    ],
    [
        "matroid",
        "Nghiên cứu hệ độc lập làm cơ sở cho tham lam và giao matroid.",
        ""
    ],
    [
        "dynamic-programming",
        "Tiến từ mô hình trạng thái cơ bản đến tối ưu phép chuyển.",
        ""
    ],
    [
        "dp-basics",
        "Xác định trạng thái, phép chuyển, điều kiện đầu và thứ tự tính.",
        ""
    ],
    [
        "lcs",
        "Mô hình hóa quan hệ giữa hai dãy bằng quy hoạch động.",
        ""
    ],
    [
        "lis",
        "Kết nối quy hoạch động trên dãy với tìm kiếm nhị phân.",
        ""
    ],
    [
        "knapsack",
        "Mô hình hóa lựa chọn với giới hạn tài nguyên và số lần lấy.",
        ""
    ],
    [
        "dp-patterns",
        "Nhận diện cách tổ chức trạng thái trên tập, chữ số, đồ thị và cây.",
        ""
    ],
    [
        "bitmask-dp",
        "Biểu diễn trạng thái tập con bằng bitmask.",
        ""
    ],
    [
        "digit-dp",
        "Đếm số qua trạng thái tiền tố chữ số và cận.",
        ""
    ],
    [
        "dag-dp",
        "Tính trạng thái theo thứ tự tô-pô của đồ thị không chu trình.",
        ""
    ],
    [
        "tree-dp",
        "Tổng hợp trạng thái từ các cây con.",
        ""
    ],
    [
        "tree-knapsack",
        "Gộp các giới hạn tài nguyên giữa trạng thái của cây con.",
        ""
    ],
    [
        "lexicographic-dp",
        "Đếm hoặc xây dựng dãy theo ràng buộc thứ tự từ điển.",
        ""
    ],
    [
        "dp-optimization",
        "Áp dụng tối ưu chỉ khi các tính chất toán học cần thiết được chứng minh.",
        ""
    ],
    [
        "knuth-optimization",
        "Giới hạn điểm chia tối ưu bằng các điều kiện đơn điệu phù hợp.",
        ""
    ],
    [
        "monotone-dp",
        "Duy trì tập ứng viên chuyển trạng thái bằng cấu trúc đơn điệu.",
        ""
    ],
    [
        "divide-conquer-dp",
        "Thu hẹp miền điểm chuyển nhờ tính đơn điệu của nghiệm tối ưu.",
        ""
    ],
    [
        "convex-hull-trick",
        "Chuyển phép tối ưu hàm tuyến tính thành truy vấn trên bao hàm.",
        ""
    ],
    [
        "advanced-knapsack",
        "Xử lý các biến thể lựa chọn có nhiều ràng buộc hoặc phụ thuộc.",
        ""
    ],
    [
        "interval-open-close",
        "Theo dõi trạng thái các đoạn đang mở khi xây dựng lời giải.",
        ""
    ],
    [
        "sos-dp",
        "Tổng hợp giá trị trên quan hệ tập con bằng biến đổi bitmask.",
        ""
    ],
    [
        "aliens-trick",
        "Dùng tham số phạt để xử lý ràng buộc số lượng hoặc tổng.",
        ""
    ],
    [
        "slope-trick",
        "Duy trì hàm lồi từng đoạn qua các phép biến đổi.",
        ""
    ],
    [
        "calculus-dp",
        "Nhận diện điều kiện giải tích để tối ưu một số phép chuyển.",
        ""
    ],
    [
        "graphs",
        "Học biểu diễn, duyệt và các bài toán kết nối trước khi đến mô hình chuyên sâu.",
        ""
    ],
    [
        "graph-basics",
        "Xây nền duyệt đồ thị, thứ tự phụ thuộc và phân tích liên thông.",
        ""
    ],
    [
        "graph-models",
        "Chọn biểu diễn và phân biệt các loại cạnh, đỉnh và đường đi.",
        ""
    ],
    [
        "bfs",
        "Duyệt theo lớp bằng hàng đợi.",
        ""
    ],
    [
        "dfs",
        "Khám phá đồ thị theo nhánh và trạng thái vào ra.",
        ""
    ],
    [
        "dfs-tree",
        "Phân loại cạnh và thời điểm trên cây duyệt DFS.",
        ""
    ],
    [
        "cycles",
        "Phát hiện và phân tích chu trình theo loại đồ thị.",
        ""
    ],
    [
        "topological-sort",
        "Sắp thứ tự đỉnh theo cạnh phụ thuộc của DAG.",
        ""
    ],
    [
        "bridges-articulations",
        "Dùng giá trị low-link để tìm điểm yếu của đồ thị vô hướng.",
        ""
    ],
    [
        "scc",
        "Phân hoạch đồ thị có hướng theo khả năng đi tới lẫn nhau.",
        ""
    ],
    [
        "bcc",
        "Phân tích các khối song liên thông của đồ thị vô hướng.",
        ""
    ],
    [
        "euler-circuit",
        "Duyệt mỗi cạnh một lần với kiểm tra điều kiện tồn tại.",
        ""
    ],
    [
        "shortest-paths",
        "Chọn thuật toán theo trọng số và cấu trúc đồ thị.",
        ""
    ],
    [
        "bfs-01",
        "Dùng deque cho đồ thị có trọng số cạnh bằng không hoặc một.",
        ""
    ],
    [
        "shortest-path-dag",
        "Lan truyền khoảng cách theo thứ tự tô-pô.",
        ""
    ],
    [
        "dijkstra",
        "Tìm đường đi ngắn nhất với cạnh không âm bằng hàng đợi ưu tiên.",
        ""
    ],
    [
        "bellman-ford",
        "Nới lỏng cạnh để xử lý trọng số âm.",
        ""
    ],
    [
        "negative-cycles",
        "Phân biệt phát hiện chu trình âm và ảnh hưởng tới đường đi.",
        ""
    ],
    [
        "floyd-warshall",
        "Tính khoảng cách mọi cặp bằng quy hoạch động theo đỉnh trung gian.",
        ""
    ],
    [
        "spfa",
        "Nghiên cứu biến thể hàng đợi của Bellman–Ford cùng trường hợp xấu.",
        ""
    ],
    [
        "dsu",
        "Quản lý phân hoạch liên thông bằng hợp và tìm đại diện.",
        ""
    ],
    [
        "mst",
        "Mô hình hóa kết nối toàn bộ đỉnh với tổng trọng số nhỏ nhất.",
        ""
    ],
    [
        "kruskal",
        "Chọn cạnh tăng dần theo trọng số với kiểm tra chu trình bằng DSU.",
        ""
    ],
    [
        "prim",
        "Mở rộng cây khung qua cạnh nhẹ nhất ở biên.",
        ""
    ],
    [
        "boruvka",
        "Hợp các thành phần qua cạnh nhẹ nhất của mỗi thành phần.",
        ""
    ],
    [
        "advanced-graphs",
        "Giữ các lớp đồ thị và mô hình logic riêng khỏi nền duyệt đồ thị.",
        ""
    ],
    [
        "two-sat",
        "Giải ràng buộc logic hai biến bằng đồ thị hàm ý và SCC.",
        ""
    ],
    [
        "functional-graph",
        "Phân tích đồ thị có đúng một cạnh đi ra mỗi đỉnh.",
        ""
    ],
    [
        "cactus-graph",
        "Khai thác cấu trúc chu trình ít giao nhau của đồ thị cactus.",
        ""
    ],
    [
        "planar-graph",
        "Nghiên cứu đồ thị có biểu diễn phẳng và các tính chất liên quan.",
        ""
    ],
    [
        "cliques",
        "Nghiên cứu tập đỉnh đôi một kề nhau và giới hạn thuật toán.",
        ""
    ],
    [
        "block-cut-tree",
        "Chuyển cấu trúc khối và đỉnh khớp thành cây.",
        ""
    ],
    [
        "rollback-dsu",
        "Hoàn tác phép hợp để xử lý truy vấn liên thông offline.",
        ""
    ],
    [
        "trees",
        "Xử lý quan hệ tổ tiên, truy vấn đường đi và phân rã cây.",
        ""
    ],
    [
        "euler-tour",
        "Ánh xạ cây con và quá trình duyệt cây sang dãy.",
        ""
    ],
    [
        "lca",
        "Tìm đỉnh tổ tiên sâu nhất chung của hai đỉnh.",
        ""
    ],
    [
        "lca-binary-lifting",
        "Tiền xử lý bước nhảy tổ tiên để trả lời LCA trong log n.",
        ""
    ],
    [
        "lca-rmq",
        "Chuyển LCA thành truy vấn cực tiểu trên dãy Euler.",
        ""
    ],
    [
        "linear-memory-lifting",
        "Giảm bộ nhớ của cấu trúc nhảy tổ tiên bằng kỹ thuật chuyên biệt.",
        ""
    ],
    [
        "hld",
        "Chuyển truy vấn đường đi trên cây thành các đoạn trên dãy.",
        ""
    ],
    [
        "centroid-decomposition",
        "Chia cây theo trọng tâm để xử lý đường đi và truy vấn.",
        ""
    ],
    [
        "small-to-large",
        "Khống chế tổng chi phí bằng chuyển phần tử từ tập nhỏ sang tập lớn.",
        ""
    ],
    [
        "dsu-on-tree",
        "Tái sử dụng dữ liệu cây con lớn để tổng hợp thống kê.",
        ""
    ],
    [
        "tree-isomorphism",
        "So sánh cấu trúc cây độc lập nhãn đỉnh.",
        ""
    ],
    [
        "link-cut-tree",
        "Duy trì rừng động bằng biểu diễn đường đi và cây tự điều chỉnh.",
        ""
    ],
    [
        "strings",
        "Học tìm mẫu và đối xứng trước khi đến chỉ mục xâu chuyên sâu.",
        ""
    ],
    [
        "string-hashing",
        "So sánh đoạn xâu bằng giá trị băm với nhận thức về va chạm.",
        ""
    ],
    [
        "kmp",
        "Dùng quan hệ tiền tố hậu tố để tìm mẫu tuyến tính.",
        ""
    ],
    [
        "z-function",
        "Tính độ dài khớp tiền tố tại mỗi vị trí của xâu.",
        ""
    ],
    [
        "trie",
        "Tổ chức tập xâu theo tiền tố chung.",
        ""
    ],
    [
        "manacher",
        "Tính bán kính palindrome quanh các tâm trong thời gian tuyến tính.",
        ""
    ],
    [
        "advanced-strings",
        "Tách chỉ mục hậu tố và tìm nhiều mẫu khỏi thuật toán xâu nền tảng.",
        ""
    ],
    [
        "aho-corasick",
        "Kết hợp trie và liên kết thất bại để tìm nhiều mẫu.",
        ""
    ],
    [
        "suffix-array",
        "Sắp thứ tự hậu tố và khai thác thông tin tiền tố chung.",
        ""
    ],
    [
        "suffix-automaton",
        "Biểu diễn các lớp xâu con bằng automaton.",
        ""
    ],
    [
        "suffix-tree",
        "Nén cấu trúc hậu tố để lập chỉ mục xâu.",
        ""
    ],
    [
        "palindrome-tree",
        "Lưu các palindrome phân biệt bằng cấu trúc liên kết.",
        ""
    ],
    [
        "geometry",
        "Xây phép toán hình học chính xác trước các thuật toán tổ hợp hình học.",
        ""
    ],
    [
        "geometry-basics",
        "Mô hình hóa điểm, vector, tích vô hướng và tích có hướng.",
        ""
    ],
    [
        "polygons",
        "Tính diện tích và xử lý quan hệ điểm với đa giác.",
        ""
    ],
    [
        "sweep-line",
        "Sắp sự kiện và duy trì trạng thái khi quét miền dữ liệu.",
        ""
    ],
    [
        "convex-hull",
        "Tìm biên lồi nhỏ nhất bao chứa tập điểm.",
        ""
    ],
    [
        "inversive-geometry",
        "Nghiên cứu phép nghịch đảo và điều kiện ứng dụng hình học.",
        ""
    ],
    [
        "flow-matching",
        "Mô hình hóa phân phối, phân công và các ràng buộc mạng.",
        ""
    ],
    [
        "maximum-flow",
        "Tìm lượng luồng lớn nhất và liên hệ với lát cắt nhỏ nhất.",
        ""
    ],
    [
        "maximum-matching",
        "Chọn tập cạnh không chung đầu mút với số lượng lớn nhất.",
        ""
    ],
    [
        "weighted-matching",
        "Tối ưu tổng trọng số của các cặp ghép.",
        ""
    ],
    [
        "min-cost-flow",
        "Tối ưu chi phí khi gửi luồng qua mạng.",
        ""
    ],
    [
        "flow-demands",
        "Chuyển các ràng buộc cận dưới và nhu cầu thành bài toán luồng.",
        ""
    ],
    [
        "hall-theorem",
        "Kiểm tra điều kiện tồn tại cặp ghép phủ trong đồ thị hai phía.",
        ""
    ],
    [
        "flow-applications",
        "Nhận diện phép chuyển các ràng buộc thực tế thành mạng luồng.",
        ""
    ],
    [
        "games",
        "Phân biệt trò chơi tổ hợp công bằng và tìm kiếm đối kháng.",
        ""
    ],
    [
        "nim",
        "Phân tích trạng thái thắng thua qua phép XOR.",
        ""
    ],
    [
        "grundy",
        "Ánh xạ trò chơi công bằng hữu hạn không chu trình sang nim-value.",
        ""
    ],
    [
        "minimax",
        "Tối ưu quyết định khi đối thủ cũng lựa chọn tối ưu.",
        ""
    ],
    [
        "alpha-beta",
        "Loại nhánh tìm kiếm đối kháng không ảnh hưởng kết quả minimax.",
        ""
    ],
    [
        "advanced-search",
        "Giữ các kỹ thuật tối ưu và truy vấn tìm kiếm chuyên sâu riêng.",
        ""
    ],
    [
        "ternary-search",
        "Tìm cực trị khi hàm có tính đơn đỉnh phù hợp.",
        ""
    ],
    [
        "parallel-binary-search",
        "Gom kiểm tra nhiều truy vấn nhị phân trên tiến trình offline.",
        ""
    ],
    [
        "local-search",
        "Cải thiện nghiệm bằng lân cận và phân biệt heuristic với bảo đảm tối ưu.",
        ""
    ],
    [
        "cdq-divide-conquer",
        "Tách thứ tự phụ thuộc để xử lý đóng góp và truy vấn offline.",
        ""
    ],
    [
        "contest-skills",
        "Rèn tính chính xác và chiến lược giải bài trong điều kiện thi.",
        ""
    ],
    [
        "test-generation",
        "Sinh dữ liệu và so sánh lời giải với bộ kiểm chứng đáng tin cậy.",
        ""
    ],
    [
        "randomized-algorithms",
        "Phân biệt dùng ngẫu nhiên để kiểm thử và để thiết kế thuật toán.",
        ""
    ],
    [
        "checker",
        "Kiểm chứng output theo đặc tả khi đáp án không duy nhất.",
        ""
    ],
    [
        "contest-strategy",
        "Phân bổ thời gian, đọc đề và quản lý quá trình giải bài.",
        ""
    ],
    [
        "adhoc",
        "Rút ra tính chất riêng của bài toán thay vì áp dụng khuôn mẫu máy móc.",
        ""
    ],
    [
        "constructive",
        "Tạo đối tượng thỏa ràng buộc với chứng minh tính tồn tại.",
        ""
    ],
    [
        "interactive",
        "Mô hình hóa giao thức hỏi đáp và giới hạn tương tác.",
        ""
    ]
]
EDGES = [
    [
        "complexity",
        "loops",
        "Phân tích các phép lặp và truy cập dữ liệu."
    ],
    [
        "complexity",
        "array-basics",
        "Phân tích các phép lặp và truy cập dữ liệu."
    ],
    [
        "recursion",
        "functions",
        "Hiểu hàm và trạng thái lời gọi."
    ],
    [
        "backtracking",
        "recursion",
        "Cây lựa chọn và hoàn tác."
    ],
    [
        "backtracking",
        "brute-force",
        "Cây lựa chọn và hoàn tác."
    ],
    [
        "branch-and-bound",
        "backtracking",
        "Cận phải hợp lệ để không bỏ nghiệm tốt."
    ],
    [
        "branch-and-bound",
        "algorithmic-thinking",
        "Cận phải hợp lệ để không bỏ nghiệm tốt."
    ],
    [
        "binary-search",
        "array-basics",
        "Bất biến biên và tính đơn điệu."
    ],
    [
        "binary-search",
        "algorithmic-thinking",
        "Bất biến biên và tính đơn điệu."
    ],
    [
        "coordinate-compression",
        "sorting-overview",
        "Bảo toàn thứ tự sau sắp xếp."
    ],
    [
        "greedy",
        "algorithmic-thinking",
        "Chứng minh lựa chọn và thứ tự xét."
    ],
    [
        "greedy",
        "sorting-overview",
        "Chứng minh lựa chọn và thứ tự xét."
    ],
    [
        "merge-sort",
        "recursion",
        "Chia bài toán và trộn kết quả."
    ],
    [
        "heap-sort",
        "heap-priority-queue",
        "Dùng tính chất heap."
    ],
    [
        "monotonic-structures",
        "stack",
        "Bất biến thứ tự và cửa sổ."
    ],
    [
        "monotonic-structures",
        "deque",
        "Bất biến thứ tự và cửa sổ."
    ],
    [
        "monotonic-structures",
        "two-pointers",
        "Bất biến thứ tự và cửa sổ."
    ],
    [
        "queries",
        "array-basics",
        "Cần hiểu cấu trúc mảng và chi phí xử lý trước khi học mô hình truy vấn."
    ],
    [
        "queries",
        "complexity",
        "Cần hiểu cấu trúc mảng và chi phí xử lý trước khi học mô hình truy vấn."
    ],
    [
        "sparse-table",
        "array-basics",
        "Đoạn lũy thừa hai và phép gộp."
    ],
    [
        "sparse-table",
        "bitwise",
        "Đoạn lũy thừa hai và phép gộp."
    ],
    [
        "fenwick-tree",
        "prefix-difference",
        "Tổng tiền tố và chỉ số nhị phân."
    ],
    [
        "fenwick-tree",
        "bitwise",
        "Tổng tiền tố và chỉ số nhị phân."
    ],
    [
        "segment-tree",
        "recursion",
        "Phân rã đoạn và phép tổng hợp."
    ],
    [
        "segment-tree",
        "queries",
        "Phân rã đoạn và phép tổng hợp."
    ],
    [
        "lazy-propagation",
        "segment-tree",
        "Luật hợp thành cập nhật."
    ],
    [
        "lazy-propagation",
        "algorithmic-thinking",
        "Luật hợp thành cập nhật."
    ],
    [
        "mo-algorithm",
        "queries",
        "Offline và dịch chuyển biên."
    ],
    [
        "mo-algorithm",
        "two-pointers",
        "Offline và dịch chuyển biên."
    ],
    [
        "mo-algorithm",
        "sqrt-decomposition",
        "Offline và dịch chuyển biên."
    ],
    [
        "persistent-segment-tree",
        "segment-tree",
        "Phiên bản và chia sẻ cấu trúc."
    ],
    [
        "li-chao-tree",
        "segment-tree",
        "Truy vấn tập đường thẳng."
    ],
    [
        "li-chao-tree",
        "convex-hull-trick",
        "Truy vấn tập đường thẳng."
    ],
    [
        "segment-tree-beats",
        "lazy-propagation",
        "Chi phí khấu hao và điều kiện dừng."
    ],
    [
        "segment-tree-beats",
        "complexity",
        "Chi phí khấu hao và điều kiện dừng."
    ],
    [
        "modular-inverse",
        "modulo",
        "Điều kiện khả nghịch; không giả định modulo luôn nguyên tố."
    ],
    [
        "modular-inverse",
        "gcd-euclid",
        "Điều kiện khả nghịch; không giả định modulo luôn nguyên tố."
    ],
    [
        "modular-inverse",
        "binary-exponentiation",
        "Điều kiện khả nghịch; không giả định modulo luôn nguyên tố."
    ],
    [
        "crt",
        "modulo",
        "Hệ đồng dư tương thích."
    ],
    [
        "crt",
        "extended-euclid",
        "Hệ đồng dư tương thích."
    ],
    [
        "advanced-binomial",
        "binomial",
        "Giới hạn factorial và modulo."
    ],
    [
        "advanced-binomial",
        "modular-inverse",
        "Giới hạn factorial và modulo."
    ],
    [
        "lucas",
        "advanced-binomial",
        "Trường hợp modulo nguyên tố."
    ],
    [
        "mobius",
        "arithmetic-functions",
        "Tổng trên ước."
    ],
    [
        "mobius",
        "advanced-sieve",
        "Tổng trên ước."
    ],
    [
        "discrete-log",
        "modulo",
        "Hai dãy gặp nhau."
    ],
    [
        "discrete-log",
        "binary-exponentiation",
        "Hai dãy gặp nhau."
    ],
    [
        "discrete-log",
        "hash-table",
        "Hai dãy gặp nhau."
    ],
    [
        "discrete-root",
        "discrete-log",
        "Điều kiện nhóm nhân; trường hợp bình phương có hướng riêng."
    ],
    [
        "discrete-root",
        "modular-inverse",
        "Điều kiện nhóm nhân; trường hợp bình phương có hướng riêng."
    ],
    [
        "fft",
        "polynomials-series",
        "Tích chập và sai số."
    ],
    [
        "fft",
        "divide-and-conquer",
        "Tích chập và sai số."
    ],
    [
        "fft",
        "implementation",
        "Tích chập và sai số."
    ],
    [
        "dp-basics",
        "array-basics",
        "Trạng thái và thứ tự phụ thuộc."
    ],
    [
        "dp-basics",
        "recursion",
        "Trạng thái và thứ tự phụ thuộc."
    ],
    [
        "dp-basics",
        "complexity",
        "Trạng thái và thứ tự phụ thuộc."
    ],
    [
        "lis",
        "dp-basics",
        "Tách bản DP và tối ưu nhị phân."
    ],
    [
        "lis",
        "binary-search",
        "Tách bản DP và tối ưu nhị phân."
    ],
    [
        "bitmask-dp",
        "dp-basics",
        "Trạng thái tập con."
    ],
    [
        "bitmask-dp",
        "bitwise",
        "Trạng thái tập con."
    ],
    [
        "dag-dp",
        "dp-basics",
        "Thứ tự tính không chu trình."
    ],
    [
        "dag-dp",
        "topological-sort",
        "Thứ tự tính không chu trình."
    ],
    [
        "tree-dp",
        "dp-basics",
        "Tổng hợp cây con."
    ],
    [
        "tree-dp",
        "dfs",
        "Tổng hợp cây con."
    ],
    [
        "tree-knapsack",
        "tree-dp",
        "Gộp trạng thái theo tài nguyên."
    ],
    [
        "tree-knapsack",
        "knapsack",
        "Gộp trạng thái theo tài nguyên."
    ],
    [
        "knuth-optimization",
        "dp-basics",
        "Điều kiện bất đẳng thức và điểm chia đơn điệu."
    ],
    [
        "knuth-optimization",
        "algorithmic-thinking",
        "Điều kiện bất đẳng thức và điểm chia đơn điệu."
    ],
    [
        "divide-conquer-dp",
        "dp-basics",
        "Chứng minh điểm tối ưu đơn điệu."
    ],
    [
        "divide-conquer-dp",
        "divide-and-conquer",
        "Chứng minh điểm tối ưu đơn điệu."
    ],
    [
        "divide-conquer-dp",
        "algorithmic-thinking",
        "Chứng minh điểm tối ưu đơn điệu."
    ],
    [
        "convex-hull-trick",
        "dp-basics",
        "Hàm tuyến tính và so sánh giao điểm; không bắt buộc học thuật toán bao lồi điểm trước."
    ],
    [
        "convex-hull-trick",
        "geometry-basics",
        "Hàm tuyến tính và so sánh giao điểm; không bắt buộc học thuật toán bao lồi điểm trước."
    ],
    [
        "sos-dp",
        "bitmask-dp",
        "Biến đổi tập con."
    ],
    [
        "aliens-trick",
        "dp-basics",
        "Tham số phạt và tính lồi hoặc đơn điệu phù hợp."
    ],
    [
        "aliens-trick",
        "binary-search",
        "Tham số phạt và tính lồi hoặc đơn điệu phù hợp."
    ],
    [
        "aliens-trick",
        "algorithmic-thinking",
        "Tham số phạt và tính lồi hoặc đơn điệu phù hợp."
    ],
    [
        "bfs",
        "graph-models",
        "Biểu diễn và duyệt theo lớp."
    ],
    [
        "bfs",
        "queue",
        "Biểu diễn và duyệt theo lớp."
    ],
    [
        "dfs",
        "graph-models",
        "Duyệt lặp hoặc đệ quy."
    ],
    [
        "dfs",
        "stack",
        "Duyệt lặp hoặc đệ quy."
    ],
    [
        "dfs",
        "recursion",
        "Duyệt lặp hoặc đệ quy."
    ],
    [
        "scc",
        "dfs",
        "Thời điểm và thành phần liên thông."
    ],
    [
        "scc",
        "dfs-tree",
        "Thời điểm và thành phần liên thông."
    ],
    [
        "bcc",
        "bridges-articulations",
        "Low-link trên đồ thị vô hướng."
    ],
    [
        "bcc",
        "dfs-tree",
        "Low-link trên đồ thị vô hướng."
    ],
    [
        "bfs-01",
        "bfs",
        "Thứ tự khoảng cách 0–1."
    ],
    [
        "bfs-01",
        "deque",
        "Thứ tự khoảng cách 0–1."
    ],
    [
        "shortest-path-dag",
        "topological-sort",
        "Phụ thuộc trên DAG; dù nguồn chấm 1 sao vẫn học sau nền đồ thị."
    ],
    [
        "dijkstra",
        "bfs",
        "Cạnh không âm và lấy khoảng cách nhỏ nhất."
    ],
    [
        "dijkstra",
        "heap-priority-queue",
        "Cạnh không âm và lấy khoảng cách nhỏ nhất."
    ],
    [
        "kruskal",
        "dsu",
        "Không tạo chu trình."
    ],
    [
        "kruskal",
        "sorting-overview",
        "Không tạo chu trình."
    ],
    [
        "prim",
        "dijkstra",
        "Kỹ thuật lấy đỉnh hoặc cạnh ưu tiên; mục tiêu khác Dijkstra."
    ],
    [
        "two-sat",
        "scc",
        "Đồ thị hàm ý."
    ],
    [
        "block-cut-tree",
        "bcc",
        "Khối và khớp thành cây."
    ],
    [
        "rollback-dsu",
        "dsu",
        "Hoàn tác không dùng path compression tùy tiện."
    ],
    [
        "rollback-dsu",
        "divide-and-conquer",
        "Hoàn tác không dùng path compression tùy tiện."
    ],
    [
        "lca-binary-lifting",
        "dfs",
        "Độ sâu và bước nhảy tổ tiên."
    ],
    [
        "lca-binary-lifting",
        "bitwise",
        "Độ sâu và bước nhảy tổ tiên."
    ],
    [
        "lca-rmq",
        "euler-tour",
        "Dãy Euler đầy đủ cho LCA, không nhầm với chỉ flatten cây con."
    ],
    [
        "lca-rmq",
        "sparse-table",
        "Dãy Euler đầy đủ cho LCA, không nhầm với chỉ flatten cây con."
    ],
    [
        "hld",
        "euler-tour",
        "Đường đi thành các đoạn."
    ],
    [
        "hld",
        "lca",
        "Đường đi thành các đoạn."
    ],
    [
        "hld",
        "segment-tree",
        "Đường đi thành các đoạn."
    ],
    [
        "centroid-decomposition",
        "dfs",
        "Cân bằng kích thước cây con."
    ],
    [
        "centroid-decomposition",
        "divide-and-conquer",
        "Cân bằng kích thước cây con."
    ],
    [
        "dsu-on-tree",
        "dfs",
        "Kỹ thuật sack hoặc gộp; không đồng nhất với DSU union-find."
    ],
    [
        "dsu-on-tree",
        "small-to-large",
        "Kỹ thuật sack hoặc gộp; không đồng nhất với DSU union-find."
    ],
    [
        "link-cut-tree",
        "splay-tree",
        "Cây động và đường ưu tiên."
    ],
    [
        "link-cut-tree",
        "hld",
        "Cây động và đường ưu tiên."
    ],
    [
        "aho-corasick",
        "trie",
        "Trie, failure links và duyệt lớp."
    ],
    [
        "aho-corasick",
        "kmp",
        "Trie, failure links và duyệt lớp."
    ],
    [
        "aho-corasick",
        "bfs",
        "Trie, failure links và duyệt lớp."
    ],
    [
        "suffix-array",
        "sorting-overview",
        "Thứ tự từ điển và biểu diễn xâu; không đòi hoàn thành mọi topic xâu cơ bản."
    ],
    [
        "suffix-array",
        "string-basics",
        "Thứ tự từ điển và biểu diễn xâu; không đòi hoàn thành mọi topic xâu cơ bản."
    ],
    [
        "sweep-line",
        "geometry-basics",
        "Thứ tự sự kiện và cấu trúc trạng thái."
    ],
    [
        "sweep-line",
        "ordered-containers",
        "Thứ tự sự kiện và cấu trúc trạng thái."
    ],
    [
        "convex-hull",
        "geometry-basics",
        "Định hướng và thứ tự điểm."
    ],
    [
        "convex-hull",
        "sorting-overview",
        "Định hướng và thứ tự điểm."
    ],
    [
        "maximum-flow",
        "bfs",
        "Mạng dư và tìm đường tăng."
    ],
    [
        "maximum-flow",
        "dfs",
        "Mạng dư và tìm đường tăng."
    ],
    [
        "weighted-matching",
        "maximum-matching",
        "Chọn phạm vi hai phía hoặc tổng quát khi biên soạn."
    ],
    [
        "weighted-matching",
        "matrix",
        "Chọn phạm vi hai phía hoặc tổng quát khi biên soạn."
    ],
    [
        "min-cost-flow",
        "maximum-flow",
        "Chi phí âm và thế năng phù hợp."
    ],
    [
        "min-cost-flow",
        "bellman-ford",
        "Chi phí âm và thế năng phù hợp."
    ],
    [
        "min-cost-flow",
        "dijkstra",
        "Chi phí âm và thế năng phù hợp."
    ],
    [
        "flow-demands",
        "maximum-flow",
        "Biến đổi cận dưới."
    ],
    [
        "grundy",
        "nim",
        "Mex và trạng thái không chu trình."
    ],
    [
        "grundy",
        "dag-dp",
        "Mex và trạng thái không chu trình."
    ],
    [
        "alpha-beta",
        "minimax",
        "Cận đối kháng."
    ],
    [
        "parallel-binary-search",
        "binary-search",
        "Gom kiểm tra offline."
    ],
    [
        "parallel-binary-search",
        "queries",
        "Gom kiểm tra offline."
    ],
    [
        "cdq-divide-conquer",
        "divide-and-conquer",
        "Thứ tự phụ thuộc và đóng góp chéo."
    ],
    [
        "cdq-divide-conquer",
        "fenwick-tree",
        "Thứ tự phụ thuộc và đóng góp chéo."
    ],
    [
        "test-generation",
        "brute-force",
        "Oracle và so sánh output."
    ],
    [
        "test-generation",
        "implementation",
        "Oracle và so sánh output."
    ],
    [
        "interactive",
        "io-basics",
        "Giao thức và flush."
    ],
    [
        "interactive",
        "queries",
        "Giao thức và flush."
    ]
]

def backfill(apps, schema_editor):
    db = schema_editor.connection.alias
    Roadmap = apps.get_model('mentor', 'Roadmap')
    Node = apps.get_model('mentor', 'RoadmapNode')
    Prerequisite = apps.get_model('mentor', 'RoadmapPrerequisite')
    roadmap = Roadmap.objects.using(db).filter(slug='competitive-programming').first()
    if roadmap is None:
        return
    nodes = {n.slug: n for n in Node.objects.using(db).filter(roadmap_id=roadmap.pk)}
    for slug, summary, section in NODES:
        node = nodes.get(slug)
        if node is not None:
            Node.objects.using(db).filter(pk=node.pk).update(summary=summary, display_section=section)
    for target, prior, reason in EDGES:
        node, prerequisite = nodes.get(target), nodes.get(prior)
        if node is not None and prerequisite is not None:
            Prerequisite.objects.using(db).get_or_create(node_id=node.pk, prerequisite_id=prerequisite.pk, defaults={'reason': reason})

class Migration(migrations.Migration):
    dependencies = [('mentor', '0010_roadmap_node_icon')]
    operations = [
        migrations.AddField(model_name='roadmapnode', name='summary', field=models.TextField(blank=True, default='', verbose_name='Mô tả ngắn')),
        migrations.AddField(model_name='roadmapnode', name='display_section', field=models.CharField(blank=True, default='', max_length=100, verbose_name='Nhóm hiển thị')),
        migrations.AddField(model_name='roadmapprerequisite', name='reason', field=models.TextField(blank=True, default='', verbose_name='Lý do')),
        migrations.AlterModelOptions(name='roadmapprerequisite', options={'verbose_name': 'Điều kiện tiên quyết lộ trình', 'verbose_name_plural': 'Các điều kiện tiên quyết lộ trình'}),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
