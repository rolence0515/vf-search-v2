import json
import os
import re
from pathlib import Path

from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
DATABASE_URL = os.environ.get("DATABASE_URL")

def search_videos(word):
    if not word:
        return []
    conn = None
    results = []
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 加入 v.number，並根據 v.number DESC 排序
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

                # 將標題前40個字截取
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


app = Flask(__name__, template_folder='template')

@app.route('/', methods=['GET', 'POST'])
@app.route('/search/<word>', methods=['GET'])
def index(word=""):
    if request.method == 'POST':
        word = request.form['word'].strip()
    results = search_videos(word)
    return render_template('index.html', word=word, data=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
