# build_vocab.py

import json
from tqdm import tqdm

class MazeSeqDataset:
    def __init__(self, data_path, token2idx=None, build_vocab=False):
        self.pairs = []
        self.token2idx = token2idx or {}
        self.build_vocab = build_vocab
        self._all_tokens = set()

        # 1) 데이터 읽기
        with open(data_path, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]

        # 2) 토큰 수집
        for line in tqdm(lines, desc="Scanning tokens"):
            lhs, rhs = line.split('|')
            start_id, end_id = lhs.strip().split()
            inp = [start_id, end_id]
            out = rhs.strip().split()
            self._all_tokens.update(inp)
            self._all_tokens.update(out)
            self.pairs.append((inp, out))

        # 3) vocab 생성
        specials = ['<PAD>','<SOS>','<EOS>']
        idx = 0
        for sp in specials:
            self.token2idx[sp] = idx; idx += 1
        for tok in sorted(self._all_tokens):
            if tok not in self.token2idx:
                self.token2idx[tok] = idx; idx += 1

        print(f"Built vocab size = {len(self.token2idx)}")

if __name__ == '__main__':
    DATA_PATH = 'training_data.txt'
    ds = MazeSeqDataset(DATA_PATH, build_vocab=True)
    with open('token2idx.json', 'w', encoding='utf-8') as f:
        json.dump(ds.token2idx, f, ensure_ascii=False, indent=2)
    print("Saved token2idx.json")
