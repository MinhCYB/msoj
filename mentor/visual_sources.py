"""Trusted, display-only source listings for built-in visual algorithms."""


def _rows(kind, entries):
    counts = {}
    rows = []
    for semantic, text in entries:
        count = counts.get(semantic, 0) + 1
        counts[semantic] = count
        rows.append((semantic, count, f'{kind}-{semantic}-{count}', text))
    return rows


_SOURCE = {
    'for-loop': {
        'cpp': [('init', '#include <iostream>'), ('init', 'int main() {'),
                ('init', '    int start = START, end = END, step = STEP;'), ('init', '    int sum = 0;'),
                ('init', '    int i = start;'), ('loop', '    for (; i <= end; i += step) {'),
                ('add', '        sum += i;'), ('loop-end', '    }'),
                ('print', "    std::cout << sum << '\\n';"), ('return', '    return 0;'), ('end', '}')],
        'python': [('init', 'start, end, step = START, END, STEP'), ('init', 'total = 0'),
                   ('loop', 'for i in range(start, end + 1, step):'), ('add', '    total += i'),
                   ('print', 'print(total)')],
    },
    'bfs': {
        'cpp': [('include', '#include <algorithm>'), ('include', '#include <queue>'),
                ('include', '#include <utility>'), ('include', '#include <vector>'),
                ('function', 'std::pair<std::vector<int>, std::vector<int>> bfs(const std::vector<std::vector<int>>& graph, int source) {'),
                ('init', '    std::vector<int> distance(graph.size(), -1);'),
                ('init', '    std::vector<int> parent(graph.size(), -1);'), ('init', '    std::queue<int> queue;'),
                ('enqueue', '    distance[source] = 0;'), ('enqueue', '    queue.push(source);'),
                ('while', '    while (!queue.empty()) {'), ('dequeue', '        int vertex = queue.front();'),
                ('dequeue', '        queue.pop();'), ('sort', '        auto neighbors = graph[vertex];'),
                ('sort', '        std::sort(neighbors.begin(), neighbors.end());'),
                ('neighbor', '        for (int next : neighbors) {'),
                ('skip', '            if (distance[next] != -1) continue;'),
                ('discover', '            distance[next] = distance[vertex] + 1;'),
                ('parent', '            parent[next] = vertex;'), ('enqueue', '            queue.push(next);'),
                ('close', '        }'), ('close', '    }'), ('return', '    return {distance, parent};'), ('close', '}')],
        'python': [('import', 'from collections import deque'), ('function', 'def bfs(graph, source):'),
                   ('init', '    distance = [None] * len(graph)'), ('init', '    parent = [None] * len(graph)'),
                   ('init', '    queue = deque()'), ('enqueue', '    distance[source] = 0'),
                   ('enqueue', '    queue.append(source)'), ('while', '    while queue:'),
                   ('dequeue', '        vertex = queue.popleft()'),
                   ('neighbor', '        for next_vertex in sorted(graph[vertex]):'),
                   ('skip', '            if distance[next_vertex] is not None:'), ('skip', '                continue'),
                   ('discover', '            distance[next_vertex] = distance[vertex] + 1'),
                   ('parent', '            parent[next_vertex] = vertex'),
                   ('enqueue', '            queue.append(next_vertex)'), ('return', '    return distance, parent')],
    },
    'dfs': {
        'cpp': [('include', '#include <algorithm>'), ('include', '#include <vector>'),
                ('visit', 'void visit(const std::vector<std::vector<int>>& graph, int vertex, int parent, std::vector<int>& parents, std::vector<int>& discovered, std::vector<int>& finished, int& clock) {'),
                ('discover', '    discovered[vertex] = ++clock;'), ('sort', '    auto neighbors = graph[vertex];'),
                ('sort', '    std::sort(neighbors.begin(), neighbors.end());'),
                ('neighbor', '    for (int next : neighbors) {'), ('check', '        if (discovered[next] == 0) {'),
                ('parent', '            parents[next] = vertex;'),
                ('recurse', '            visit(graph, next, vertex, parents, discovered, finished, clock);'),
                ('close', '        }'), ('close', '    }'), ('finish', '    finished[vertex] = ++clock;'), ('close', '}'),
                ('function', 'void dfs(const std::vector<std::vector<int>>& graph, int source, std::vector<int>& parents, std::vector<int>& discovered, std::vector<int>& finished) {'),
                ('init', '    int clock = 0;'), ('recurse', '    visit(graph, source, -1, parents, discovered, finished, clock);'), ('close', '}')],
        'python': [('function', 'def dfs(graph, source):'), ('init', '    parent = [None] * len(graph)'),
                   ('init', '    discovered = [None] * len(graph)'), ('init', '    finished = [None] * len(graph)'),
                   ('init', '    clock = [0]'), ('visit', '    def visit(vertex):'),
                   ('discover', '        clock[0] += 1'), ('discover', '        discovered[vertex] = clock[0]'),
                   ('neighbor', '        for next_vertex in sorted(graph[vertex]):'),
                   ('check', '            if discovered[next_vertex] is None:'),
                   ('parent', '                parent[next_vertex] = vertex'),
                   ('recurse', '                visit(next_vertex)'), ('finish', '        clock[0] += 1'),
                   ('finish', '        finished[vertex] = clock[0]'), ('recurse', '    visit(source)'),
                   ('return', '    return parent, discovered, finished')],
    },
    'matrix-chain': {
        'cpp': [('include', '#include <vector>'),
                ('function', 'long long matrix_chain(const std::vector<int>& dimensions) {'),
                ('init', '    const int count = static_cast<int>(dimensions.size()) - 1;'),
                ('init', '    std::vector<std::vector<long long>> cost(count, std::vector<long long>(count, 0));'),
                ('init', '    std::vector<std::vector<int>> split(count, std::vector<int>(count, -1));'),
                ('length', '    for (int length = 2; length <= count; ++length) {'),
                ('left', '        for (int left = 0; left + length <= count; ++left) {'),
                ('right', '            const int right = left + length - 1;'),
                ('candidate', '            for (int middle = left; middle < right; ++middle) {'),
                ('candidate', '                const long long value = cost[left][middle] + cost[middle + 1][right] + static_cast<long long>(dimensions[left]) * dimensions[middle + 1] * dimensions[right + 1];'),
                ('update', '                if (split[left][right] == -1 || value < cost[left][right]) { cost[left][right] = value; split[left][right] = middle; }'),
                ('close', '            }'), ('close', '        }'), ('close', '    }'),
                ('return', '    return cost[0][count - 1];'), ('close', '}')],
        'python': [('function', 'def matrix_chain(dimensions):'), ('init', '    count = len(dimensions) - 1'),
                   ('init', '    cost = [[0] * count for _ in range(count)]'),
                   ('init', '    split = [[None] * count for _ in range(count)]'),
                   ('length', '    for length in range(2, count + 1):'),
                   ('left', '        for left in range(count - length + 1):'),
                   ('right', '            right = left + length - 1'),
                   ('candidate', '            for middle in range(left, right):'),
                   ('candidate', '                value = cost[left][middle] + cost[middle + 1][right] + dimensions[left] * dimensions[middle + 1] * dimensions[right + 1]'),
                   ('update', '                if split[left][right] is None or value < cost[left][right]:'),
                   ('update', '                    cost[left][right] = value'),
                   ('update', '                    split[left][right] = middle'),
                   ('return', '    return cost[0][count - 1]')],
    },
    'dp-bitmask-matching': {
        'cpp': [('include', '#include <bit>'), ('include', '#include <vector>'),
                ('function', 'long long count_matchings(const std::vector<std::vector<int>>& compatible) {'),
                ('init', '    const int n = static_cast<int>(compatible.size());'),
                ('mask', '    for (int mask = 0; mask < (1 << n); ++mask) {'),
                ('person', '        const int person = std::popcount(static_cast<unsigned>(mask));'),
                ('job', '        for (int job = 0; job < n; ++job) {'),
                ('check', '            if ((mask & (1 << job)) || !compatible[person][job]) continue;'),
                ('transition', '            dp[mask | (1 << job)] += dp[mask];'), ('close', '        }'),
                ('close', '    }'), ('return', '    return dp[(1 << n) - 1];'), ('close', '}')],
        'python': [('function', 'def count_matchings(compatible):'), ('init', '    n = len(compatible)'),
                   ('init', '    dp = [0] * (1 << n)'), ('base', '    dp[0] = 1'),
                   ('mask', '    for mask in range(1 << n):'), ('person', '        person = mask.bit_count()'),
                   ('job', '        for job in range(n):'),
                   ('check', '            if mask & (1 << job) or not compatible[person][job]:'),
                   ('check', '                continue'), ('transition', '            dp[mask | (1 << job)] += dp[mask]'),
                   ('return', '    return dp[(1 << n) - 1]')],
    },
}


def algorithm_sources(kind, inp):
    """Return complete C++/Python display tabs with corresponding semantic IDs."""
    if kind not in _SOURCE:
        raise ValueError('Unsupported visual algorithm')
    replacements = {'START': str(inp['start']), 'END': str(inp['end']), 'STEP': str(inp['step'])} if kind == 'for-loop' else {}
    tabs = []
    for language in ('cpp', 'python'):
        rows = _rows(kind, _SOURCE[kind][language])
        lines = []
        for _, _, line_id, text in rows:
            for key, value in replacements.items():
                text = text.replace(key, value)
            lines.append((line_id, text))
        tabs.append({'language': language, 'sourceCode': '\n'.join(text for _, text in lines),
                     'lineIds': [line_id for line_id, _ in lines]})
    return tabs


def semantic_line_ids(kind, semantic):
    if kind not in _SOURCE:
        raise ValueError('Unsupported visual algorithm')
    return list(dict.fromkeys(line_id for language in ('cpp', 'python')
                             for name, _, line_id, _ in _rows(kind, _SOURCE[kind][language]) if name == semantic))
