import os
import csv
import psycopg2
import urllib.parse
import torch
from transformers import AutoModel, AutoTokenizer

# 你的 GCP PostgreSQL 資料庫連線資訊
# -----------------------------------
print("設定 GCP PostgreSQL 資料庫連線資訊...")
username = "rolence"
password = "zaq1@#$%^&*" # 這裡有特殊字元
host = "34.84.63.151"
port = "5432"
database = "postgres"

# 進行 URL 編碼
# -----------------------------------
print("進行 URL 編碼...")
encoded_password = urllib.parse.quote_plus(password)

# 重新組合正確的 DATABASE_URL
# -----------------------------------
print("重新組合正確的 DATABASE_URL...")
DATABASE_URL = f"postgresql://{username}:{encoded_password}@{host}:{port}/{database}"

# 連線 PostgreSQL
# -----------------------------------
def connect_db():
    print("連線 PostgreSQL...")
    return psycopg2.connect(DATABASE_URL)

conn = connect_db()
cur = conn.cursor()

# 使用 BERT-base-chinese 和 BERT-multilingual-cased 作為 Embedding Model
# -----------------------------------
print("載入 BERT-base-chinese 和 BERT-multilingual-cased 模型...")
MODEL_NAME_1 = "bert-base-chinese"
MODEL_NAME_2 = "bert-base-multilingual-cased"
tokenizer_1 = AutoTokenizer.from_pretrained(MODEL_NAME_1)
tokenizer_2 = AutoTokenizer.from_pretrained(MODEL_NAME_2)
model_1 = AutoModel.from_pretrained(MODEL_NAME_1)
model_2 = AutoModel.from_pretrained(MODEL_NAME_2)

# 計算 batch_count
# -----------------------------------
batch_count = len([file for file in os.listdir('.') if file.startswith('temp_embeddings_') and file.endswith('.csv')])
print(f"找到 {batch_count} 個批次文件")

# 詢問是否重新匯出 temp_embeddings_{batch_count}.csv
# -----------------------------------
choice = input(f"是否重新匯出 temp_embeddings_{batch_count}.csv？(y/n): ")
if choice.lower() == 'y':
    print(f"刪除舊的 temp_embeddings_{batch_count}.csv 文件...")
    for file in os.listdir('.'):  # 刪除所有舊的 temp_embeddings 文件
        if file.startswith('temp_embeddings_') and file.endswith('.csv'):
            os.remove(file)
    print("舊的 temp_embeddings 文件已刪除")
else:
    print("接續上次的斷點...")

# 轉換文字為向量
# -----------------------------------
def text_to_embedding(text):
    tokens_1 = tokenizer_1(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    tokens_2 = tokenizer_2(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        output_1 = model_1(**tokens_1)
        output_2 = model_2(**tokens_2)
    embedding_1 = output_1.last_hidden_state[:, 0, :].squeeze().tolist()  # 取得 [CLS] 向量
    embedding_2 = output_2.last_hidden_state[:, 0, :].squeeze().tolist()  # 取得 [CLS] 向量
    return embedding_1 + embedding_2  # 拼接兩個向量

# 重新匯出 temp_embeddings_{batch_count}.csv 匯出時，只匯出 id 和 embedding 欄位
# -----------------------------------
if choice.lower() == 'y':
    # 取得所有 block_text
    # -----------------------------------
    print("取得所有 block_text...")
    cur.execute("SELECT id, block_text FROM video_blocks ORDER BY id;")
    rows = cur.fetchall()
    print(f"取得 {len(rows)} 條記錄")

    print("開始批量處理並寫入臨時 CSV 文件...")
    with open('temp_embeddings_all.csv', 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(['id', 'embedding'])  # 只寫入 id 和 embedding 表頭
        for row_id, text in rows:
            embedding = text_to_embedding(text)
            csvwriter.writerow([row_id, embedding])
    print("所有記錄已寫入臨時 CSV 文件")
else:
    print("接續上次的斷點...")

# 詢問是否直接寫入數據庫
# -----------------------------------
write_choice = input("是否直接寫入數據庫？(y/n): ")
if write_choice.lower() == 'y':
    print("創建臨時表 temp_video_blocks...")
    cur.execute("CREATE TEMP TABLE temp_video_blocks (id SERIAL, embedding VECTOR(1536));")
    conn.commit()

    print("使用 COPY 命令將資料從 CSV 文件導入臨時表...")
    for batch_num in range(batch_count):
        with open(f'temp_embeddings_{batch_num}.csv', 'r') as csvfile:
            cur.copy_expert("COPY temp_video_blocks (id, embedding) FROM STDIN WITH CSV HEADER;", csvfile)
        conn.commit()
        print(f"批次 {batch_num} 資料已導入臨時表")

    print("將臨時表的數據寫回原始表...")
    cur.execute("UPDATE video_blocks SET embedding = temp_video_blocks.embedding FROM temp_video_blocks WHERE video_blocks.id = temp_video_blocks.id;")
    conn.commit()
    print("資料插入完成")
else:
    print("未寫入數據庫，請稍後手動處理")

# 關閉資料庫連線
# -----------------------------------
print("關閉資料庫連線...")
cur.close()
conn.close()

print("✅ 所有 block_text 已轉換為向量並存入 PostgreSQL！")
