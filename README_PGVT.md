# PostgreSQL Video Text Processing

本文件說明了四個 PostgreSQL 相關程式的使用方式及順序：`pg_vt_export.py`、`pg_vt_import.py`、`pg_vt_embedding.py` 和 `pg_vt_search.py`。

## 使用順序

1. **Export**：`pg_vt_export.py`
2. **Import**：`pg_vt_import.py`
3. **Embedding**：`pg_vt_embedding.py`
4. **Search**：`pg_vt_search.py`

## 程式說明

### 1. `pg_vt_export.py`

此程式用於從資料庫中匯出資料到 CSV 檔案。

#### 使用方式

```bash
python pg_vt_export.py
```

### 2. `pg_vt_import.py`

此程式用於將 CSV 檔案中的資料匯入到資料庫中。

#### 使用方式

```bash
python pg_vt_import.py
```

### 3. `pg_vt_embedding.py`

此程式用於生成分段文字的嵌入向量，並將其存入資料庫中。

#### 使用方式

```bash
python pg_vt_embedding.py
```

### 4. `pg_vt_search.py`

此程式用於根據嵌入向量進行相似度搜尋，找出最相關的影片片段。

#### 使用方式

```bash
python pg_vt_search.py
```

## 注意事項

- 確保在執行這些程式之前，已經正確配置了資料庫連線資訊。
- 在執行 `pg_vt_embedding.py` 時，請確保已經安裝了所需的模型和相關依賴。
- 在執行 `pg_vt_search.py` 時，請確保資料庫中已經存在嵌入向量。