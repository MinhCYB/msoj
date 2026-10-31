"""Trusted canonical documents and deterministic snapshots for built-in algorithms."""
from __future__ import annotations
import copy
import json
import re
from .visual_sources import algorithm_sources, semantic_line_ids

MAX_FRAMES = 500
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
_ID = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
_KINDS = {'for-loop', 'bfs', 'dfs', 'matrix-chain', 'dp-bitmask-matching'}


def _sequence(values, ids):
    return {'type': 'sequence', 'values': values, 'itemIds': ids}


def _vars(values):
    return {'type': 'variables', 'scopes': [{'id': 'main-scope', 'name': 'main', 'frames': [
        {'id': 'main-frame', 'procedure': 'main', 'parameters': {}, 'locals': values}]}]}


def _code(kind, inp):
    return {'id': 'source', 'type': 'code', 'caption': 'Mã nguồn chỉ để đọc',
            'sources': algorithm_sources(kind, inp)}


def algorithm_document(kind, inp, document_id=None):
    """Build the complete v2 document for an input already validated by its caller."""
    if kind not in _KINDS:
        raise ValueError('Unsupported visual algorithm')
    document_id = document_id or f'algorithm-{kind}'
    if not isinstance(document_id, str) or not _ID.fullmatch(document_id):
        raise ValueError('document_id must be a valid MSOJ identifier')
    modules, data = [], {}
    if kind == 'for-loop':
        data = {'variables': _vars({'start': inp['start'], 'end': inp['end'], 'step': inp['step'],
                                    'i': None, 'sum': 0}), 'iterations': _sequence([], [])}
        modules = [{'id': 'variables-view', 'type': 'variables', 'source': 'variables'},
                   {'id': 'iterations-view', 'type': 'vector', 'source': 'iterations'},
                   {'id': 'explanation', 'type': 'explanation', 'content': [{'type':'text','value':'Mỗi lượt cộng i vào tổng khi i <= end.'}]},
                   {'id': 'output', 'type': 'output', 'text': ''}, _code(kind, inp)]
    elif kind in {'bfs', 'dfs'}:
        n = inp['n']
        graph = {'type': 'graph', 'nodes': [{'id':f'v{i}','label':str(i)} for i in range(n)],
                 'edges':[{'id':f'edge-{j}','from':f'v{a}','to':f'v{b}','directed':False}
                          for j,(a,b) in enumerate(inp['edges'])]}
        data = {'graph':graph, 'dist':_sequence([None]*n,[f'vertex-{i}' for i in range(n)]),
                'parent':_sequence([None]*n,[f'vertex-{i}' for i in range(n)]),
                'status':_sequence(['undiscovered']*n,[f'vertex-{i}' for i in range(n)]),
                'queue':_sequence([],[])}
        modules = [{'id':'graph-view','type':'graph','source':'graph'},
                   {'id':'distance-view','type':'vector','source':'dist','caption':'Khoảng cách'},
                   {'id':'parent-view','type':'vector','source':'parent','caption':'Đỉnh cha'},
                   {'id':'status-view','type':'vector','source':'status','caption':'Trạng thái'}]
        if kind == 'bfs':
            modules.append({'id':'queue-view','type':'queue','source':'queue'})
        else:
            data['discover'] = _sequence([None]*n,[f'vertex-{i}' for i in range(n)])
            data['finish'] = _sequence([None]*n,[f'vertex-{i}' for i in range(n)])
            data['callstack'] = {'type':'variables','scopes':[{'id':'dfs-scope','name':'dfs','frames':[]}]}
            modules.extend([{'id':'discover-view','type':'vector','source':'discover','caption':'Thời điểm phát hiện'},
                            {'id':'finish-view','type':'vector','source':'finish','caption':'Thời điểm kết thúc'},
                            {'id':'callstack-view','type':'call-stack','source':'callstack'}])
        modules.extend([{'id':'explanation','type':'explanation','content':[{'type':'text','value':'Đồ thị vô hướng; duyệt láng giềng theo thứ tự tăng dần.'}]},_code(kind,inp)])
    elif kind == 'matrix-chain':
        n=len(inp['dimensions'])-1
        data={'dimensions':_sequence(list(inp['dimensions']),[f'dimension-{i}' for i in range(n+1)]),
              'cost':{'type':'matrix','values':[[0]*n for _ in range(n)]},
              'split':{'type':'matrix','values':[[None]*n for _ in range(n)]},
              'variables':_vars({'length':1,'left':None,'right':None,'middle':None,'candidate':None})}
        modules=[{'id':'dimensions-view','type':'vector','source':'dimensions'},
                 {'id':'cost-view','type':'matrix','source':'cost','caption':'Chi phí phép nhân vô hướng'},
                 {'id':'split-view','type':'matrix','source':'split','caption':'Điểm tách tối ưu'},
                 {'id':'variables-view','type':'variables','source':'variables'},
                 {'id':'explanation','type':'explanation','content':[{'type':'text','value':'Tính chi phí nhân vô hướng; không thực hiện phép nhân ma trận.'}]},_code(kind,inp)]
    else:
        matrix=[list(r) for r in inp['matrix']]; n=len(matrix); total=1<<n
        data={'compatibility':{'type':'matrix','values':matrix},
              'dp':_sequence([0]*total,[f'mask-{i}' for i in range(total)]),
              'variables':_vars({'mask':0,'person':0,'job':None,'next_mask':None}),
              'witness':{'type':'table','columns':[{'id':'person','type':'number'},{'id':'job','type':'number'}],'rows':[]}}
        modules=[{'id':'compatibility-view','type':'matrix','source':'compatibility'},
                 {'id':'dp-view','type':'vector','source':'dp','caption':'Số cách theo mask'},
                 {'id':'witness-view','type':'table','source':'witness','caption':'Một ghép cặp hợp lệ'},
                 {'id':'variables-view','type':'variables','source':'variables'},
                 {'id':'explanation','type':'explanation','content':[{'type':'text','value':'Mỗi bit bật gán một người; quy hoạch động đếm các phép gán tương thích.'}]},_code(kind,inp)]
    primary = {'for-loop': 'iterations-view', 'bfs': 'graph-view', 'dfs': 'graph-view',
               'matrix-chain': 'cost-view', 'dp-bitmask-matching': 'compatibility-view'}[kind]
    areas = [[primary, primary, 'source', 'source']]
    support = [module['id'] for module in modules
               if module['id'] not in {primary, 'source', 'explanation'}]
    for start in range(0, len(support), 2):
        pair = support[start:start + 2]
        areas.append([pair[0], pair[0], pair[1], pair[1]] if len(pair) == 2
                     else [pair[0], pair[0], pair[0], pair[0]])
    areas.append(['explanation'] * 4)
    # The visual grid is read left-to-right, top-to-bottom.
    reading_order = [primary, 'source', *support, 'explanation']
    return {'version':2,'id':document_id,'title':kind.replace('-',' ').title(),
            'summary':f'Mô phỏng {kind} xác định; mã nguồn chỉ dùng để đọc.','data':data,'modules':modules,
            'layout':{'areas':areas,'readingOrder':reading_order},
            'timeline':{'generator':kind,'input':copy.deepcopy(inp)}}


def _frame(data,title,text,highlights=None,lines=None,output=None):
    f={'data':copy.deepcopy(data),'title':title,'text':text,'highlights':highlights or {}}
    if lines: f['lines']=lines if isinstance(lines,list) else [lines]
    if output is not None: f['output']=output
    return f


def compile_algorithm(kind, inp):
    """Compile bounded, authoritative frames for prevalidated built-in input."""
    doc=algorithm_document(kind,inp); state=doc['data']; frames=[]; size=0
    def emit(title,text,line=None,output=None,**highlights):
        nonlocal size
        if len(frames)>=MAX_FRAMES: raise ValueError('Algorithm trace exceeds 500 frames')
        f=_frame(state,title,text,highlights,semantic_line_ids(kind,line) if line else None,output)
        size+=len(json.dumps(f,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        if size>MAX_SNAPSHOT_BYTES: raise ValueError('Algorithm snapshots exceed 2 MiB')
        frames.append(f)
    def node(i): return f'v{i}'
    if kind=='for-loop':
        loc=state['variables']['scopes'][0]['frames'][0]['locals']; values=state['iterations']['values']; ids=state['iterations']['itemIds']
        start,end,step=inp['start'],inp['end'],inp['step']; i=start
        loc['i'] = i
        emit('Trước vòng lặp','Các biến đã được khởi tạo.',line='init')
        while i<=end:
            loc['i']=i; emit('Kiểm tra điều kiện',f'{i} <= {end}: đúng.',line='loop')
            loc['sum']+=i; item=f'iteration-{len(ids)}'; values.append(i); ids.append(item)
            emit(f'Cộng {i}',f'Tổng hiện tại là {loc["sum"]}.',line='add',items={'iterations':[item]})
            i+=step; loc['i']=i; emit('Tăng i',f'i = {i}.',line='loop')
        emit('Kết thúc vòng lặp',f'{i} <= {end}: sai.',line='loop-end')
        emit('In tổng',f'Chương trình in {loc["sum"]}.',line='print',output=f'{loc["sum"]}\n')
        emit('Trả về','main trả về không lỗi.',line='return'); return frames
    if kind in {'bfs','dfs'}:
        n,source=inp['n'],inp['source']; graph=state['graph']; adj=[[] for _ in range(n)]; edges={}
        for e,(a,b) in zip(graph['edges'],inp['edges']): adj[a].append(b); adj[b].append(a); edges[frozenset((a,b))]=e['id']
        for ns in adj: ns.sort()
        dist=state['dist']['values']; parent=state['parent']['values']; status=state['status']['values']
        def vertex_frame(title,text,v,line,edge=None,**highlights):
            highlights['nodes']=[node(v)]
            if edge is not None: highlights['edges']=[edge]
            emit(title,text,line,**highlights)
        if kind=='bfs':
            q=state['queue']['values']; qids=state['queue']['itemIds']; dist[source]=0;status[source]='discovered'
            q.append(source);qid=f'queue-v{source}';qids.append(qid)
            vertex_frame('Enqueue nguồn',f'Đánh dấu {source} khi đưa vào hàng đợi.',source,'enqueue',items={'queue':[qid]})
            while q:
                v=q.pop(0);qid=qids.pop(0);status[v]='processed'
                vertex_frame('Dequeue',f'Lấy {v} khỏi đầu hàng đợi FIFO.',v,'dequeue',items={'queue':[qid]})
                for w in adj[v]:
                    edge=edges[frozenset((v,w))]
                    if status[w]!='undiscovered':
                        vertex_frame('Đã phát hiện',f'{w} đã được phát hiện; không enqueue lại.',w,'skip',edge);continue
                    dist[w]=dist[v]+1;parent[w]=v;status[w]='discovered';qid=f'queue-v{w}';q.append(w);qids.append(qid)
                    vertex_frame('Phát hiện láng giềng',f'dist[{w}]={dist[w]}, parent[{w}]={v}; đánh dấu ngay khi enqueue.',w,'discover',edge,items={'queue':[qid]})
            emit('Hoàn tất BFS','Đỉnh không tới được giữ dist và parent là null.');return frames
        stack=state['callstack']['scopes'][0]['frames']; discover=state['discover']['values']; finish=state['finish']['values']; seen=[None]*n;clock=0
        def visit(v,caller=None):
            nonlocal clock
            clock+=1;seen[v]=clock;discover[v]=clock;status[v]='active'
            stack.append({'id':f'call-v{v}','procedure':'dfs','parameters':{'vertex':v},'locals':{'nextNeighbor':0,'caller':caller}})
            vertex_frame('Gọi đệ quy',f'Đẩy dfs({v}) lên call stack; discovery={clock}.',v,'discover')
            for i,w in enumerate(adj[v]):
                stack[-1]['locals']['nextNeighbor']=i;edge=edges[frozenset((v,w))]
                if seen[w] is None:
                    parent[w]=v;vertex_frame('Cạnh cây',f'Gọi dfs({w}) từ {v}.',w,'recurse',edge);visit(w,v)
                else: vertex_frame('Đã thăm',f'{w} đã được phát hiện; bỏ qua.',w,'skip',edge)
            clock+=1;finish[v]=clock;status[v]='finished';stack.pop()
            vertex_frame('Trả về',f'Kết thúc dfs({v}) tại thời điểm {clock}; pop frame.',v,'finish')
        visit(source);emit('Hoàn tất DFS','DFS đệ quy chỉ duyệt thành phần chứa nguồn.');return frames
    if kind=='matrix-chain':
        p=inp['dimensions'];n=len(p)-1;cost=state['cost']['values'];split=state['split']['values'];loc=state['variables']['scopes'][0]['frames'][0]['locals']
        emit('Khởi tạo','Ma trận đơn lẻ có chi phí nhân vô hướng bằng 0.')
        for length in range(2,n+1):
            loc['length']=length
            for i in range(n-length+1):
                j=i+length-1;loc['left']=i;loc['right']=j
                for k in range(i,j):
                    candidate=cost[i][k]+cost[k+1][j]+p[i]*p[k+1]*p[j+1];loc['middle']=k;loc['candidate']=candidate
                    if split[i][j] is None or candidate<cost[i][j]:cost[i][j]=candidate;split[i][j]=k
                    emit(f'Xét điểm tách {k}',f'cost[{i},{j}]={cost[i][j]}, split={split[i][j]}.',line='candidate',cells={'cost':[[i,j]],'split':[[i,j]]})
        emit('Kết quả',f'Chi phí tối thiểu là {cost[0][n-1]}; không thực hiện phép nhân ma trận.',cells={'cost':[[0,n-1]]});return frames
    matrix=inp['matrix'];n=len(matrix);total=1<<n;dp=state['dp']['values'];dp[0]=1;loc=state['variables']['scopes'][0]['frames'][0]['locals'];paths={0:[]}
    emit('Khởi tạo','dp[0]=1 biểu diễn ghép cặp rỗng.',line='base',items={'dp':['mask-0']})
    for mask in range(total):
        person=mask.bit_count();loc['mask']=mask;loc['person']=person
        if person==n or not dp[mask]:continue
        for job in range(n):
            loc['job']=job
            if mask&(1<<job) or not matrix[person][job]:continue
            target=mask|(1<<job);before=dp[target];dp[target]+=dp[mask];loc['next_mask']=target
            if target not in paths:paths[target]=paths[mask]+[(person,job)]
            state['witness']['rows'][:]=[{'id':f'person-{p}','person':p,'job':j} for p,j in paths[target]]
            emit(f'Gán người {person} cho việc {job}',f'dp[{target}] tăng từ {before} lên {dp[target]}; bảng là một ghép cặp từng phần hợp lệ.',line='transition',items={'dp':[f'mask-{target}']})
    state['witness']['rows'][:]=[{'id':f'person-{p}','person':p,'job':j} for p,j in paths.get(total-1,[])]
    emit('Kết quả',f'{dp[-1]} ghép cặp hoàn chỉnh (giá trị trả về; không có stdout).',line='return',items={'dp':[f'mask-{total-1}']})
    return frames
