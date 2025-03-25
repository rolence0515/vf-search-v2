import os
import csv
import psycopg2
import urllib.parse
import torch
from transformers import AutoModel, AutoTokenizer

# 你的 GCP PostgreSQL 資料庫連線資訊
# 原始連線資訊
username = "rolence"
password = "zaq1@#$%^&*"  # 這裡有特殊字元
host = "34.84.63.151"
port = "5432"
database = "postgres"

# 進行 URL 編碼
encoded_password = urllib.parse.quote_plus(password)

# 重新組合正確的 DATABASE_URL
DATABASE_URL = f"postgresql://{username}:{encoded_password}@{host}:{port}/{database}"

# 連線 PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 使用 BERT-base-chinese 和 BERT-base-multilingual-cased 作為 Embedding Model
MODEL_NAME_1 = "bert-base-chinese"
MODEL_NAME_2 = "bert-base-multilingual-cased"
tokenizer_1 = AutoTokenizer.from_pretrained(MODEL_NAME_1)
model_1 = AutoModel.from_pretrained(MODEL_NAME_1)
tokenizer_2 = AutoTokenizer.from_pretrained(MODEL_NAME_2)
model_2 = AutoModel.from_pretrained(MODEL_NAME_2)

# 清空所有資料的 embedding 欄位
cur.execute("UPDATE video_blocks SET embedding = NULL;")
conn.commit()

# 取得所有 block_text
cur.execute("SELECT id, block_text FROM video_blocks WHERE embedding IS NULL ORDER BY id;")
rows = cur.fetchall()

# 轉換文字為向量
def text_to_embedding(text):
    tokens_1 = tokenizer_1(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    tokens_2 = tokenizer_2(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        output_1 = model_1(**tokens_1)
        output_2 = model_2(**tokens_2)
    embedding_1 = output_1.last_hidden_state[:, 0, :].squeeze().tolist()  # 取得 [CLS] 向量
    embedding_2 = output_2.last_hidden_state[:, 0, :].squeeze().tolist()  # 取得 [CLS] 向量
    return embedding_1 + embedding_2  # 拼接兩個向量

# 批量更新向量
batch_size = 50
batch = []
for row_id, text in rows:
    embedding = text_to_embedding(text)
    # print(f"Row ID: {row_id}, Embedding: {embedding[:5]}...")  # 除錯訊息
    if len(embedding) != 1536:
        print(f"❌ 向量維度錯誤: {len(embedding)}")
        continue
    batch.append((embedding, row_id))
    if len(batch) >= batch_size:
        cur.executemany("UPDATE video_blocks SET embedding = %s WHERE id = %s;", batch)
        print(f"Batch update: {batch[:1]}...")  # 除錯訊息
        batch = []
if batch:
    cur.executemany("UPDATE video_blocks SET embedding = %s WHERE id = %s;", batch)  # 更新最後一批
    print(f"Final batch update: {batch[:1]}...")  # 除錯訊息
conn.commit()
print("✅ 所有 block_text 已轉換為向量並存入 PostgreSQL！")
cur.close()
conn.close()
