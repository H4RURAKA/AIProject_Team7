import json
import math
import sys
import heapq

# Load merged graph
with open('merged_graph.json', 'r', encoding='utf-8') as f:
    graph = json.load(f)

# Build node and adjacency maps
nodes = {n['id']: n for n in graph['nodes']}
adj = {}
for e in graph['edges']:
    src, tgt, w = e['source'], e['target'], e['weight']
    adj.setdefault(src, []).append((tgt, w))

# Dijkstra's algorithm to find shortest path
def shortest_path(start_id, end_id):
    dist = {nid: math.inf for nid in nodes}
    prev = {}
    dist[start_id] = 0
    pq = [(0, start_id)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == end_id:
            break
        if d > dist[u]:
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    # reconstruct path
    path = []
    u = end_id
    while u != start_id:
        path.append(u)
        u = prev.get(u)
        if u is None:
            return []
    path.append(start_id)
    return list(reversed(path))

# Compute turn angle; swap left/right mapping
def compute_turn(prev_node, curr_node, next_node):
    f1 = prev_node['id'].split('_')[0]
    f2 = curr_node['id'].split('_')[0]
    f3 = next_node['id'].split('_')[0]
    if f1 != f2 or f2 != f3:
        return '직진'
    v1 = (curr_node['x'] - prev_node['x'], curr_node['y'] - prev_node['y'])
    v2 = (next_node['x'] - curr_node['x'], next_node['y'] - curr_node['y'])
    norm1 = math.hypot(*v1)
    norm2 = math.hypot(*v2)
    if norm1 == 0 or norm2 == 0:
        return '직진'
    cos_a = max(-1, min(1, (v1[0]*v2[0] + v1[1]*v2[1]) / (norm1*norm2)))
    angle = math.degrees(math.acos(cos_a))
    if abs(angle - 180) < 10:
        return '직진'
    cross = v1[0]*v2[1] - v1[1]*v2[0]
    # swapped: positive cross => 우회전, negative => 좌회전
    direction = '우회전' if cross > 0 else '좌회전'
    return f"{int(angle)}도 {direction}"

# Format path: collapse small-angle corridor nodes and hide weights for elevator/stair segments
def format_path(path_ids):
    def node_str(nid):
        n = nodes[nid]
        return f"(id: {n['id']}, name: {n['name']}, type: {n['type']})"

    # determine important stops
    stops = [path_ids[0]]
    L = len(path_ids)
    for i in range(1, L-1):
        nid = path_ids[i]
        ntype = nodes[nid]['type']
        if ntype in ('Elevator', 'Stair'):
            stops.append(nid)
        elif ntype != 'Corridor':
            stops.append(nid)
        else:
            turn = compute_turn(nodes[path_ids[i-1]], nodes[nid], nodes[path_ids[i+1]])
            if turn != '직진':
                try:
                    angle = int(turn.split('도')[0])
                except:
                    angle = None
                if angle is not None and angle <= 15 \
                   and nodes[path_ids[i-1]]['type']=='Corridor' \
                   and nodes[path_ids[i+1]]['type']=='Corridor':
                    continue
                stops.append(nid)
    stops.append(path_ids[-1])

    out = []
    out.append(node_str(stops[0]))
    for j in range(1, len(stops)):
        prev = stops[j-1]
        curr = stops[j]
        prev_type = nodes[prev]['type']
        curr_type = nodes[curr]['type']
        # elevator->elevator or stair->stair: hide weight
        if prev_type == curr_type and prev_type in ('Elevator', 'Stair'):
            out.append("-> ")
            out.append(node_str(curr))
            continue
        # sum distance
        dist = 0
        i_prev = path_ids.index(prev)
        i_curr = path_ids.index(curr)
        for k in range(i_prev, i_curr):
            for v, w in adj[path_ids[k]]:
                if v == path_ids[k+1]:
                    dist += w
                    break
        out.append(f"-> {dist:.2f}m -> ")
        out.append(node_str(curr))
        # add turn if needed
        if curr not in (path_ids[0], path_ids[-1]) and curr_type not in ('Elevator', 'Stair'):
            i = path_ids.index(curr)
            turn = compute_turn(nodes[path_ids[i-1]], nodes[curr], nodes[path_ids[i+1]])
            if turn != '직진':
                out.append(f" <{turn}>")
    return ' '.join(out)

if __name__ == '__main__':
    start_name = input("start name: ")
    end_name = input("end name: ")
    start_ids = [nid for nid, n in nodes.items() if n['name'] == start_name]
    end_ids = [nid for nid, n in nodes.items() if n['name'] == end_name]
    if not start_ids or not end_ids:
        print('Node name not found')
        sys.exit(1)
    path = shortest_path(start_ids[0], end_ids[0])
    if not path:
        print('No path found')
        sys.exit(1)
    print(format_path(path))
