import os
import psycopg2
import urllib.parse

# 來源資料庫連線資訊從環境變數取得
SOURCE_DATABASE_URL = os.getenv('VF_DATABASE_URL')

# 目的資料庫連線資訊
username = "rolence"
password = "zaq1@#$%^&*"  # 這裡有特殊字元
host = "34.84.63.151"
port = "5432"
database = "postgres"

# 進行 URL 編碼
encoded_password = urllib.parse.quote_plus(password)

# 重新組合正確的 DATABASE_URL
DATABASE_URL = f"postgresql://{username}:{encoded_password}@{host}:{port}/{database}"

# 連線來源資料庫
source_conn = psycopg2.connect(SOURCE_DATABASE_URL)
source_cur = source_conn.cursor()

# 連線目的資料庫
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# 定義時間段
TIME_INTERVAL = 10000  # 10 秒

# SQL 查詢
query = f"""
SELECT
    v.video_id,
    v.title AS video_name,
    FLOOR(vt.start / {TIME_INTERVAL}) AS block_id,
    MIN(vt.start) AS block_start,
    MAX(vt.start) AS block_end,
    STRING_AGG(vt.text, ' ' ORDER BY vt.start) AS block_text
FROM video_text vt
JOIN video v ON vt.video_id = v.video_id
GROUP BY v.video_id, v.title, FLOOR(vt.start / {TIME_INTERVAL})
ORDER BY v.video_id, block_start;
"""

# 執行 SQL 查詢
source_cur.execute(query)
rows = source_cur.fetchall()

# 清空目的資料表
cur.execute("TRUNCATE TABLE video_blocks;")
conn.commit()

# 建立 pgvector 資料表
create_table_query = """
CREATE TABLE IF NOT EXISTS video_blocks (
    id SERIAL PRIMARY KEY,
    video_id TEXT,
    video_name TEXT,
    block_id INT,
    block_start INT,
    block_end INT,
    block_text TEXT,
    embedding VECTOR(1536)
);
"""
cur.execute(create_table_query)
conn.commit()

# 插入資料到 pgvector 資料表
insert_query = """
INSERT INTO video_blocks (video_id, video_name, block_id, block_start, block_end, block_text)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (video_id, block_id) DO NOTHING;
"""
cur.executemany(insert_query, rows)
conn.commit()

# 關閉資料庫連線
source_cur.close()
source_conn.close()
cur.close()
conn.close()

print("資料已成功匯出到 video_blocks 資料表")
