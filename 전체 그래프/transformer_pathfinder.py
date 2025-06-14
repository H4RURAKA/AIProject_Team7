# transformer_pathfinder.py

import json
import math
import sys
import torch
import torch.nn as nn

# 1) Device 설정
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 2) token2idx.json 불러오기
with open('token2idx.json', 'r', encoding='utf-8') as f:
    token2idx = json.load(f)
idx2token = {idx: tok for tok, idx in token2idx.items()}
vocab_size = len(token2idx)

# 3) Positional Encoding & Transformer 정의
class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2).float()
                        * -(math.log(10000.0)/d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.pe = pe.unsqueeze(0)
    def forward(self, x):
        return x + self.pe[:, :x.size(1), :].to(x.device)

def generate_square_subsequent_mask(sz):
    return torch.triu(torch.ones(sz, sz), diagonal=1).bool()

class TransformerSeq2Seq(nn.Module):
    def __init__(self,
                 vocab_size,
                 d_model=256,
                 nhead=8,
                 num_encoder_layers=3,
                 num_decoder_layers=3,
                 dim_feedforward=512,
                 dropout=0.1,
                 max_len=100):
        super().__init__()
        # 저장된 state_dict 키와 일치하도록 이름 맞춤
        self.embedding   = nn.Embedding(vocab_size, d_model, padding_idx=0)
        self.pos_encoder = PositionalEncoding(d_model, max_len)
        self.transformer = nn.Transformer(
            d_model=d_model,
            nhead=nhead,
            num_encoder_layers=num_encoder_layers,
            num_decoder_layers=num_decoder_layers,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True
        )
        self.fc_out      = nn.Linear(d_model, vocab_size)

    def forward(self,
                src,                        # (B, S)
                tgt,                        # (B, T)
                src_key_padding_mask,       # (B, S)
                tgt_key_padding_mask,       # (B, T)
                memory_key_padding_mask):   # (B, S)
        src_emb = self.pos_encoder(
            self.embedding(src) * math.sqrt(self.embedding.embedding_dim)
        )
        tgt_emb = self.pos_encoder(
            self.embedding(tgt) * math.sqrt(self.embedding.embedding_dim)
        )
        tgt_mask = generate_square_subsequent_mask(tgt_emb.size(1)).to(src.device)
        out = self.transformer(
            src_emb, tgt_emb,
            tgt_mask=tgt_mask,
            src_key_padding_mask=src_key_padding_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=memory_key_padding_mask
        )
        return self.fc_out(out)

def create_padding_mask(seq):
    return (seq == 0)

# 4) 모델 생성 후 가중치 로드
model = TransformerSeq2Seq(vocab_size).to(device)
model.load_state_dict(torch.load('transformer_maze_model.pt', map_location=device))
model.eval()

# 5) 추론 함수: start_id, end_id 는 토큰으로 쓰이는 문자열이어야 합니다
@torch.no_grad()
def infer_sequence(start_id, end_id, max_len=100):
    if start_id not in token2idx or end_id not in token2idx:
        raise ValueError(f"'{start_id}' or '{end_id}' not in token2idx.")
    sos, eos = token2idx['<SOS>'], token2idx['<EOS>']
    src_idxs = [sos, token2idx[start_id], token2idx[end_id], eos]
    src = torch.tensor([src_idxs], device=device)
    src_pad = create_padding_mask(src)

    ys = torch.tensor([[sos]], device=device)
    for _ in range(max_len):
        ys_pad = create_padding_mask(ys)
        out = model(src, ys, src_pad, ys_pad, src_pad)
        next_tok = out[:, -1, :].argmax(dim=-1).item()
        ys = torch.cat([ys, torch.tensor([[next_tok]], device=device)], dim=1)
        if next_tok == eos:
            break

    tokens = [idx2token[idx] for idx in ys.squeeze().tolist()[1:-1]]
    return tokens

# 6) main: 노드 ID 토큰을 직접 입력
if __name__ == '__main__':
    start_token = input("start token: ").strip()
    end_token   = input("end token: ").strip()
    try:
        seq = infer_sequence(start_token, end_token)
    except ValueError as e:
        print("Error:", e)
        sys.exit(1)

    print("\nTransformer path tokens:")
    print(seq)
