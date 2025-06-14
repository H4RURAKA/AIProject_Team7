# generate_token_to_graphid.py

import json

def main():
    # 1) merged_buildings_graph.json 로드
    with open('merged_buildings_graph.json', 'r', encoding='utf-8') as f:
        graph = json.load(f)

    # 2) token(name) → graph_id(id) 매핑 생성
    mapping = {}
    for node in graph['nodes']:
        token = node['name']   # training_data.txt 의 start/end 에 쓰인 바로 그 토큰
        graph_id = node['id']  # pathfinder.py 가 내부적으로 쓰는 그래프의 노드 ID
        mapping[token] = graph_id

    # 3) JSON 으로 저장
    with open('token_to_graphid.json', 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"token_to_graphid.json 생성 완료: 총 {len(mapping)}개 매핑")

if __name__ == '__main__':
    main()
