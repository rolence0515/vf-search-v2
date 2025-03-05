import json
import os
import re
import psycopg2
import chainlit as cl
import chinese_converter
from smolagents import tool, CodeAgent, ToolCallingAgent, LiteLLMModel, DuckDuckGoSearchTool
from pathlib import Path
from datetime import datetime
from psycopg2.extras import RealDictCursor

# ============================== 配置區 ==============================
VF_DATABASE_URL = os.environ.get("VF_DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_api_key")  # 請設置環境變數或直接填入
SEARCH_AGENT_DESC = """
    # 莫子 AI 指導文檔

    ## 簡介
    這個 AI Agent 是一個友善且多話的智能體，目標是幫助用戶查詢 YouTube 影片字幕和關鍵字出現次數，並提供相關影片的標題及連結資訊。

    ## 角色特點
    1. **友善且多話**：智能體以友善且熱情的態度與用戶交流，並會主動提供詳細的建議和資訊。
    2. **主動提供建議**：根據查詢結果，智能體會主動提供進一步的建議，例如推薦相關影片。
    3. **解決需求和痛點**：智能體會幫助用戶分析需求和痛點，並提供解決方案，確保查詢順利進行。

    ## 功能概述
    1. **查詢特定主題或關鍵字最常出現的影片**：
    - 用戶輸入關鍵字後，Agent 會使用 get_videos_with_most_mentions 工具來查詢關鍵字在哪些影片中出現最多次，並返回相關影片的標題及連結資訊。

    ## 注意事項
    - 使用繁體中文回答
    """

SEARCH_AGENT_RESP_DESC = """
    ## 回傳格式
    請注意，只能回傳以下字典格式：
    {
    "type": "text",  // 或 "elements"
    "data": {       // 當 type 為 'text' 時，data 應該是純文字
        "content": "這裏是純文字內容"  // 這是純文字內容
    }
    }

    或

    {
    "type": "elements",  // 當 type 為 'elements' 時
    "data": {            // data 應該包含一個元素列表
        "elements": [
        {
            "label": "顯示的文字",
            "url": "https://example.com"  // 這是可點擊的連結
        }
        ]
    }
    }

    請確保所有回應都符合上面這兩種格式。
    """

# ============================== Agent 配置區 ==============================
# 設定 OpenAI 代理模型
model = LiteLLMModel(
    model_id="gpt-4",
    api_base="https://api.openai.com/v1",
    api_key=OPENAI_API_KEY,
)

# 使用者資訊
users = {
    "user1": {"session_id": "session1"},
    "user2": {"session_id": "session2"},
    "user3": {"session_id": "session3"}
}

# ============================== Agent 工具區 ==============================
@tool
def search_youtube_subtitles(video_id: str, keyword: str) -> list:
    """
    查詢指定影片的 YouTube 字幕段落列表

    Args:
        video_id: 影片ID
        keyword: 關鍵字

    Returns:
        list: 包含字幕段落資訊的列表，每個元素為一個字典，結構如下:
        {
            'text': str,  # 字幕文字（前50個字）
            'url': str    # 影片URL
        }
    """
    if not video_id or not keyword:
        return []

    conn = None
    results = []
    try:
        conn = psycopg2.connect(VF_DATABASE_URL, sslmode='require')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT vt.text, vt.start
                FROM video_text vt
                WHERE vt.video_id = %s AND vt.text LIKE %s
                LIMIT 6
            """
            cur.execute(query, (video_id, f"%{keyword}%",))
            rows = cur.fetchall()

            for row in rows:
                start_time = row['start'] or 0
                url = f"https://www.youtube.com/watch?v={video_id}&t={int(start_time/1000)}s"
                text = row['text'][:50]  # 只取前50個字

                results.append({
                    'text': text,
                    'url': url
                })
    except Exception as e:
        print("資料庫查詢失敗:", e)
    finally:
        if conn:
            conn.close()

    return results

@tool
def get_videos_with_most_mentions(keyword: str) -> list:
    """
    查詢某一個關鍵字在哪些影片中出現最多次（前四名）

    Args:
        keyword: 關鍵字

    Returns:
        list: 包含影片資訊的列表，每個元素為一個字典，結構如下:
        {
            'rank': int,           # 排名
            'video_id': str,       # 影片ID
            'title': str,          # 影片標題
            'mention_count': int,  # 關鍵字出現次數
            'url': str             # 影片URL
        }
    """
    if not keyword:
        return []

    conn = None
    results = []
    try:
        conn = psycopg2.connect(VF_DATABASE_URL, sslmode='require')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT v.video_id, v.title, COUNT(*) as mention_count
                FROM video_text vt
                JOIN video v ON vt.video_id = v.video_id
                WHERE vt.text LIKE %s
                GROUP BY v.video_id, v.title
                ORDER BY mention_count DESC
                LIMIT 4
            """
            cur.execute(query, (f"%{keyword}%",))
            rows = cur.fetchall()

            for rank, row in enumerate(rows, start=1):
                results.append({
                    'rank': rank,
                    'video_id': row['video_id'],
                    'title': row['title'],
                    'mention_count': row['mention_count'],
                    'url': f"https://www.youtube.com/watch?v={row['video_id']}"
                })
    except Exception as e:
        print("資料庫查詢失敗:", e)
    finally:
        if conn:
            conn.close()

    return results

search_agent = CodeAgent(
    tools=[search_youtube_subtitles, get_videos_with_most_mentions],
    model=model,
    name="search_agent",
    description=SEARCH_AGENT_DESC
)

# ============================== cl 配置區 ==============================
@cl.set_chat_profiles
async def chat_profile():
    return [
        cl.ChatProfile(
            name="搜尋影片",
            markdown_description="搜尋莫子 YT 影片。",
            icon="https://picsum.photos/200",
        ),
        cl.ChatProfile(
            name="莫子 AI",
            markdown_description="使用莫子 AI 來回答問題。",
            icon="https://picsum.photos/250",
        )
    ]

# ============================== 啟動區 ==============================
@cl.on_chat_start
async def on_chat_start():
    """聊天開始時初始化"""
    user = cl.user_session.get("user")
    chat_profile = cl.user_session.get("chat_profile")
    await cl.Message(
        content=f"歡迎使用莫子 AI！您目前在 {chat_profile}區域 歡迎你的提問。",
        author="System"
    ).send()

@cl.on_message
async def on_message(message: cl.Message):
    user_message = message.content

    # 假設 response 是從 manager_agent.run() 獲得的字串
    response = search_agent.run("我要找松果體的影片" + SEARCH_AGENT_RESP_DESC)

    # 判斷格式並回傳
    if response.get("type") == "text":
        # 如果是純文字格式
        await cl.Message(content=response.get("data", "未提供的文字")).send()
    elif response.get("type") == "elements":
        # 如果是 elements 格式
        elements_data = response.get("data", {}).get("elements", [])
        elements = [cl.Text(content=f"[{item['label']}]({item['url']})") for item in elements_data]
        await cl.Message(
            content="這是包含連結的元素",
            elements=elements
        ).send()
    else:
        # 如果格式不正確
        await cl.Message(content="格式不正確或未定義").send()
