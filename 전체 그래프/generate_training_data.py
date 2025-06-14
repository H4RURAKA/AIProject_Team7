# generate_training_data.py
import json
import math
import heapq
import os

# -- 1) merged_graph.json 로드 및 그래프 초기화 ----------------------------------------------------------------

with open('merged_buildings_graph.json', 'r', encoding='utf-8') as f:
    graph = json.load(f)

# nodes: {node_id: { "id": ..., "name": ..., "type": ..., "x": ..., "y": ... } }
nodes = {n['id']: n for n in graph['nodes']}

# adj: { source_id: [(target_id, weight), ...], ... }
adj = {}
for e in graph['edges']:
    src, tgt, w = e['source'], e['target'], e['weight']
    adj.setdefault(src, []).append((tgt, w))


# -- 2) Dijkstra 최단 경로 함수 ----------------------------------------------------------------------------------

def shortest_path(start_id, end_id):
    """
    start_id에서 end_id까지 Dijkstra로 최단 경로를 구해
    node_id 리스트로 반환. 경로가 없으면 빈 리스트 반환.
    """
    dist = {nid: math.inf for nid in nodes}
    prev = {}
    dist[start_id] = 0
    pq = [(0, start_id)]
    visited = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == end_id:
            break
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))

    # 경로 복원
    path = []
    u = end_id
    while u != start_id:
        path.append(u)
        u = prev.get(u, None)
        if u is None:
            return []  # 경로 없음
    path.append(start_id)
    return list(reversed(path))


# -- 3) 회전(turn) 계산 함수 ---------------------------------------------------------------------------------------

def compute_turn(prev_node, curr_node, next_node):
    """
    prev->curr->next 노드를 보고 각도와 방향(좌/우)을 계산.
    같은 복도(Corridor) 구간이어야 각도 계산. 아니면 '직진'으로 처리.
    양-수(positive)일 때 우회전, 음-수(negative)일 때 좌회전.
    """
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
    direction = '우회전' if cross > 0 else '좌회전'
    return f"{int(round(angle))}도 {direction}"


# -- 4) 중요 정류장(스톱)만 골라내는 함수 ----------------------------------------------------------------------------

def compress_stops(path_ids):
    """
    원본 path_ids(전체 노드 ID 리스트)에서
    중요 정류장만 뽑아낸 stops 리스트를 반환.
    Corridors 구간 중 회전(각도)이 생기는 노드 포함.
    엘리베이터/계단/Elevator/Stair/Room 등도 모두 포함.
    """
    stops = [path_ids[0]]
    L = len(path_ids)
    for i in range(1, L - 1):
        nid = path_ids[i]
        ntype = nodes[nid]['type']
        if ntype in ('Elevator', 'Stair'):
            stops.append(nid)
        elif ntype != 'Corridor':
            stops.append(nid)
        else:
            # Corridor인데, 직진이 아닐 경우(=회전)
            turn = compute_turn(nodes[path_ids[i-1]], nodes[nid], nodes[path_ids[i+1]])
            if turn != '직진':
                # 15도 이내 서로 평행 corridor 라면 무시
                try:
                    angle_val = int(turn.split('도')[0])
                except:
                    angle_val = None
                if (angle_val is not None
                    and angle_val <= 15
                    and nodes[path_ids[i-1]]['type'] == 'Corridor'
                    and nodes[path_ids[i+1]]['type'] == 'Corridor'):
                    continue
                stops.append(nid)
    stops.append(path_ids[-1])
    return stops


# -- 5) stops 기반으로 “D=거리 TYPE=노드타입 TURN_DIR” 형태로 핵심 정보만 뽑는 함수 ----------------------------------------

def path_to_feature_sequence(path_ids):
    """
    전체 path_ids 대신, compress_stops()를 거친 stops 리스트를 이용해서
    (거리, 타입, 회전 정보)만 남긴 토큰 시퀀스를 만들어 반환.
    - 거리(Distance)는 5m 단위로 반올림(round) → 정수로 출력
    - TYPE=Room/Elevator/Stair/Corridor 등
    - 회전 정보: TURN_LEFT 또는 TURN_RIGHT (회전 각도는 무시)
    최종적으로 "D=xx TYPE=yy [TURN_LEFT|TURN_RIGHT]" 토큰들이 공백으로 분리된 리스트 형태로 반환.
    """
    stops = compress_stops(path_ids)
    tokens = []

    # 첫 번째 노드는 타입 정보만 붙이고 거리 정보는 뒤에서 붙이므로 생략
    # 순회하며 (이전 스톱 → 현재 스톱) 사이 거리, 현재 스톱 타입, 회전 정보(있으면) 붙이기
    for idx in range(1, len(stops)):
        prev_stop = stops[idx - 1]
        curr_stop = stops[idx]

        # 1) 거리 계산 (전체 path_ids에서 prev_stop부터 curr_stop까지의 누적 weight)
        dist = 0.0
        i_prev = path_ids.index(prev_stop)
        i_curr = path_ids.index(curr_stop)
        for k in range(i_prev, i_curr):
            v_list = adj[path_ids[k]]
            # 다음 노드 weight 찾기
            for (v, w) in v_list:
                if v == path_ids[k + 1]:
                    dist += w
                    break
        # 5m 단위 반올림
        dist_rounded = int(round(dist / 5.0)) * 5
        tokens.append(f"D={dist_rounded}")

        # 2) 현재 스톱 타입
        ctype = nodes[curr_stop]['type']
        tokens.append(f"TYPE={ctype}")

        # 3) 회전 정보: curr_stop이 Corridor 구간일 때, 이전/다음 스톱이 모두 존재하면 회전 여부 계산
        if curr_stop not in (path_ids[0], path_ids[-1]) and ctype == 'Corridor':
            i_abs = path_ids.index(curr_stop)
            turn = compute_turn(nodes[path_ids[i_abs - 1]],
                                nodes[curr_stop],
                                nodes[path_ids[i_abs + 1]])
            if turn != '직진':
                # 방향만 LEFT/RIGHT로 바꿔 붙이기
                if '우회전' in turn:
                    tokens.append("TURN_RIGHT")
                elif '좌회전' in turn:
                    tokens.append("TURN_LEFT")
    # 마지막에 항상 END 토큰 붙이기
    tokens.append("END")
    return tokens


# -- 6) 학습 데이터 파일 생성 함수 ----------------------------------------------------------------------------------

def generate_training_file(output_txt_path):
    """
    merged_graph.json에 있는 모든 Room 노드의 가능한 쌍(combination)을 순회하며
    최단 경로를 뽑아 “시작_방_이름 끝_방_이름 | D=.. TYPE=.. … END” 형식으로
    output_txt_path에 한 줄씩 기록한다.
    """
    # 먼저, Room 타입 노드 ID 리스트와 name 리스트 추출
    room_nodes = [n for n in nodes.values() if n['type'] == 'Room']
    room_ids = [n['id'] for n in room_nodes]
    room_names = {n['id']: n['name'] for n in room_nodes}  # id → name

    # output 파일 열기
    with open(output_txt_path, 'w', encoding='utf-8') as fout:
        N = len(room_ids)
        for i in range(N):
            for j in range(N):
                if i == j:
                    continue
                start_id = room_ids[i]
                end_id = room_ids[j]
                start_name = room_names[start_id]
                end_name = room_names[end_id]

                # 최단 경로 구하기
                path_ids = shortest_path(start_id, end_id)
                if not path_ids:
                    continue  # 경로 없으면 스킵

                # 핵심 feature 시퀀스로 변환
                feat_tokens = path_to_feature_sequence(path_ids)
                feat_seq_str = " ".join(feat_tokens)

                # 한 줄에 “시작_방_이름 끝_방_이름 | feat_seq END” 기록
                fout.write(f"{start_name} {end_name} | {feat_seq_str}\n")

    print(f"[완료] 학습 데이터 파일을 생성했습니다: {output_txt_path}")


if __name__ == '__main__':
    # 실행 예시:
    # python generate_training_data.py
    output_path = "training_data.txt"
    if os.path.exists(output_path):
        print(f"'{output_path}' 파일이 이미 존재합니다. 덮어쓰기를 원하면 삭제 후 다시 실행하세요.")
    else:
        generate_training_file(output_path)
