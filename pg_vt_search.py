import os
import csv
import psycopg2
import urllib.parse
import torch
import numpy as np
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

# 使用 BERT-base-chinese 和 BERT-base-multilingual-cased 作為 Embedding Model
MODEL_NAME_1 = "bert-base-chinese"
MODEL_NAME_2 = "bert-base-multilingual-cased"
tokenizer_1 = AutoTokenizer.from_pretrained(MODEL_NAME_1)
model_1 = AutoModel.from_pretrained(MODEL_NAME_1)
tokenizer_2 = AutoTokenizer.from_pretrained(MODEL_NAME_2)
model_2 = AutoModel.from_pretrained(MODEL_NAME_2)

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

# 連線 PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 新增除錯訊息

def search_similar_blocks(query):
    # 轉換搜尋詞為向量
    query_vector = text_to_embedding(query)
    print(f"{'='*20}")  # 除錯訊息
    print(f"Query Vector: {np.array(query_vector)}")  # 除錯訊息

    # 使用向量相似度搜尋最相關的影片片段
    cur.execute("""
        SELECT id, block_text, (embedding <-> %s::vector) AS distance
        FROM video_blocks
        ORDER BY distance ASC
        LIMIT 10;
    """, (query_vector,))
    # 顯示搜尋結果
    results = cur.fetchall()
    for id, block_text, distance in results:
        print(f"\n🎥 {id} \n📜 {block_text} \n📏 相似度: {distance:.4f}")
        # print(f"Embedding: {np.array(query_vector)}")  # 除錯訊息

try:
    while True:
        # 接受使用者輸入的關鍵詞
        query = input("請輸入關鍵詞（或輸入 'exit' 結束）：")
        if query.lower() == 'exit':
            break
        search_similar_blocks(query)
except KeyboardInterrupt:
    print("\n已退出搜尋。")
finally:
    cur.close()
    conn.close()
