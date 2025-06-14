# compare_runtime.py

import time, sys, json
from transformer_pathfinder import infer_sequence
from pathfinder import shortest_path, format_path

# 1) 토큰→그래프ID 매핑 불러오기
with open('token_to_graphid.json', 'r', encoding='utf-8') as f:
    token2graph = json.load(f)

def main():
    start_tok = input("start token: ").strip()
    end_tok   = input("end token: ").strip()

    # 2) Transformer 실행 및 시간 측정
    t0 = time.time()
    try:
        toks = infer_sequence(start_tok, end_tok)
    except ValueError as e:
        print(f"Transformer Error: {e}")
        sys.exit(1)
    t1 = time.time()
    print("\n=== Transformer Result ===")
    print("Tokens:", toks)
    print(f"Transformer elapsed: {(t1-t0)*1000:.2f} ms")

    # 3) 토큰을 그래프 ID 로 변환
    if start_tok not in token2graph or end_tok not in token2graph:
        print("Error: token_to_graphid.json 에 매핑 정보가 없습니다.")
        sys.exit(1)
    start_graph = token2graph[start_tok]
    end_graph   = token2graph[end_tok]

    # 4) Dijkstra 실행 및 시간 측정
    t2 = time.time()
    path = shortest_path(start_graph, end_graph)
    t3 = time.time()

    if not path:
        print("\n=== Dijkstra Result ===")
        print(f"No path found between {start_graph} and {end_graph}")
    else:
        formatted = format_path(path)
        print("\n=== Dijkstra Result ===")
        print(formatted)

    print(f"Dijkstra elapsed: {(t3-t2)*1000:.2f} ms")

if __name__ == '__main__':
    main()
