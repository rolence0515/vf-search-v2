# 資料庫結構說明

本文件說明了程式中使用的資料表及其欄位和型別。

## 資料表結構

### 1. `video` 資料表

此資料表存儲了影片的基本資訊，包括影片 ID 和標題。

| 欄位名稱 | 型別    | 說明       |
| -------- | ------- | ---------- |
| video_id | SERIAL  | 影片 ID，主鍵 |
| title    | TEXT    | 影片標題   |

### 2. `video_text` 資料表

此資料表存儲了影片的字幕資訊，包括字幕文字和開始時間。

| 欄位名稱     | 型別    | 說明             |
| ------------ | ------- | ---------------- |
| video_text_id | SERIAL  | 字幕 ID，主鍵     |
| video_id     | INTEGER | 影片 ID，外鍵，參考 `video` 資料表 |
| text         | TEXT    | 字幕文字         |
| start        | INTEGER | 字幕開始時間（毫秒） |

### 3. `video_blocks` 資料表

此資料表存儲了影片的分段資訊，包括影片 ID、分段 ID、分段開始時間、分段結束時間、分段文字和嵌入向量。

| 欄位名稱     | 型別    | 說明             |
| ------------ | ------- | ---------------- |
| id           | SERIAL  | 分段 ID，主鍵     |
| video_id     | INTEGER | 影片 ID，外鍵，參考 `video` 資料表 |
| video_name   | TEXT    | 影片名稱         |
| block_id     | INTEGER | 分段 ID          |
| block_start  | INTEGER | 分段開始時間（毫秒） |
| block_end    | INTEGER | 分段結束時間（毫秒） |
| block_text   | TEXT    | 分段文字         |
| embedding    | VECTOR(1536)  | 分段文字的嵌入向量，1536 維度 |

## 資料表結構總結

根據程式中的查詢需求，我們可以推斷出程式用到的資料表結構如下：

1. **`video` 資料表**：
    - `video_id`：影片 ID，主鍵
    - `title`：影片標題

2. **`video_text` 資料表**：
    - `video_text_id`：字幕 ID，主鍵
    - `video_id`：影片 ID，外鍵，參考 `video` 資料表
    - `text`：字幕文字
    - `start`：字幕開始時間（毫秒）

3. **`video_blocks` 資料表**：
    - `id`：分段 ID，主鍵
    - `video_id`：影片 ID，外鍵，參考 `video` 資料表
    - `video_name`：影片名稱
    - `block_id`：分段 ID
    - `block_start`：分段開始時間（毫秒）
    - `block_end`：分段結束時間（毫秒）
    - `block_text`：分段文字
    - `embedding`：分段文字的嵌入向量，1536 維度

這些資料表結構應該能夠滿足程式中所有的查詢需求。
