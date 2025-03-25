import json
import os
import re
import chinese_converter
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__, template_folder='template')
app.secret_key = 'your_secret_key'  # Flask 需要設定secret_key才能使用flash訊息


def parse_srt_content(srt_content):
    """
    將SRT內容解析成字幕區塊的列表，每個區塊含有開始、結束時間及文字。
    """
    # 將所有換行符統一處理為 '\n'
    srt_content = srt_content.replace('\r\n', '\n').strip()

    # 按兩個空行分割區塊
    srt_blocks = srt_content.split('\n\n')
    parsed_results = []

    for block in srt_blocks:
        # 分割行
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # SRT格式：
        # 1) index (可忽略)
        # 2) time range: "HH:MM:SS,mmm --> HH:MM:SS,mmm"
        # 3) subtitles text...
        time_line = lines[1]
        text_lines = lines[2:]
        text = ' '.join(text_lines)

        start_str, end_str = time_line.split(' --> ')
        start_ms = srt_time_to_ms(start_str)
        end_ms = srt_time_to_ms(end_str)
        dur = end_ms - start_ms

        parsed_results.append((start_ms, dur, text))

    return parsed_results



def srt_time_to_ms(timestamp):
    """將 SRT 時間字串轉為毫秒。格式: HH:MM:SS,mmm"""
    time_parts = timestamp.split(',')
    ms = int(time_parts[1])
    h, m, s = time_parts[0].split(':')
    ms += (int(h) * 3600 + int(m) * 60 + int(s)) * 1000
    return ms


def search_videos(word):
    if not word:
        return []
    conn = None
    results = []
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT vt.video_id, vt.start, vt.dur, vt.text, v.title, v.number
                FROM video_text vt
                JOIN video v ON vt.video_id = v.video_id
                WHERE vt.text LIKE %s
                ORDER BY v.number DESC
            """
            cur.execute(query, (f"%{word}%",))
            rows = cur.fetchall()

            highlight_pattern = re.compile(re.escape(word), re.IGNORECASE)

            for row in rows:
                video_id = row['video_id']
                start_time = row['start'] or 0
                url = f"https://www.youtube.com/watch?v={video_id}&t={int(start_time/1000)}s"

                highlighted_text = highlight_pattern.sub(
                    lambda m: f'<span class="highlight">{m.group(0)}</span>',
                    row['text']
                )
                title_short = row['title'][:40]

                results.append({
                    'text': highlighted_text,
                    'url': url,
                    'title_short': title_short
                })
    except Exception as e:
        print("資料庫查詢失敗:", e)
    finally:
        if conn:
            conn.close()

    return results


@app.route('/', methods=['GET', 'POST'])
@app.route('/search', methods=['GET'])
@app.route('/search/<word>', methods=['GET'])
def index(word=""):
    if request.method == 'POST':
        word = request.form['word'].strip()
        word = chinese_converter.to_traditional(word) # 簡體轉中文
    elif request.method == 'GET':
        word = request.args.get('q', word).strip()
        word = chinese_converter.to_traditional(word) if word else ''
    results = search_videos(word)
    return render_template('index.html', word=word, data=results)


@app.route('/srt_upload', methods=['GET', 'POST'])
def srt_upload():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        number = request.form.get('number', '').strip()
        video_id = request.form.get('video_id', '').strip()
        srt_file = request.files.get('srt_file', None)

        # 基本檢查
        if not title or not number or not video_id or not srt_file:
            flash("所有欄位都必須填寫並提供檔案。", "error")
            return redirect(url_for('srt_upload'))

        # 檢查 number, video_id 是否已存在
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            with conn.cursor() as cur:
                # 檢查 video_id
                cur.execute("SELECT 1 FROM video WHERE video_id = %s", (video_id,))
                if cur.fetchone():
                    flash("該 video_id 已存在，無法上傳。", "error")
                    return redirect(url_for('srt_upload'))

                # 檢查 number
                cur.execute("SELECT 1 FROM video WHERE number = %s", (number,))
                if cur.fetchone():
                    flash("該 number 已存在，無法上傳。", "error")
                    return redirect(url_for('srt_upload'))

            # 解析上傳的 SRT 檔
            srt_content = srt_file.read().decode('utf-8', errors='replace')
            subtitles = parse_srt_content(srt_content)

            # 寫入 video 及 video_text
            with conn.cursor() as cur:
                # 寫入 video
                insert_video_query = """
                    INSERT INTO video (video_id, title, number)
                    VALUES (%s, %s, %s)
                """
                cur.execute(insert_video_query, (video_id, title, number))

                # 寫入 video_text
                for (start, dur, text) in subtitles:
                    # 將文字中單引號跳脫
                    escaped_text = text.replace("'", "''")
                    print(escaped_text)
                    insert_text_query = f"""
                        INSERT INTO video_text (video_id, start, dur, text)
                        VALUES ('{video_id}', {start}, {dur}, '{escaped_text}')
                    """
                    cur.execute(insert_text_query)

                conn.commit()

            flash("上傳成功！", "success")
            return redirect(url_for('srt_upload'))
        except Exception as e:
            print("上傳失敗:", e)
            flash("上傳失敗，請查看伺服器日誌。", "error")
            return redirect(url_for('srt_upload'))
        finally:
            if conn:
                conn.close()
    else:
        # 這裡是 GET，查詢目前資料庫中最後一筆影片
        conn = None
        last_video = None
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 根據你自己的排序方式 (假設 number 越大代表越晚上傳)
                cur.execute("SELECT * FROM video ORDER BY m_dt DESC LIMIT 1")
                last_video = cur.fetchone()
        except Exception as e:
            print("查詢最後上傳影片失敗:", e)
        finally:
            if conn:
                conn.close()

        # 將 last_video 丟給模板
        return render_template('srt_upload.html', last_video=last_video)


if __name__ == '__main__':
    # 執行Flask服務
    app.run(host='0.0.0.0', port=8080)
