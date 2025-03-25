import json
import os
import re
import psycopg2
import chainlit as cl
import chinese_converter
from transformers import AutoModelForCausalLM, AutoTokenizer
from smolagents import tool, HfApiModel, CodeAgent, ToolCallingAgent, LiteLLMModel, DuckDuckGoSearchTool
from pathlib import Path
from datetime import datetime
from psycopg2.extras import RealDictCursor

# ============================== 配置區 ==============================
VF_DATABASE_URL = os.environ.get("VF_DATABASE_URL")
HF_TOKEN = os.environ.get("HF_TOKEN")
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
    "data":  "這裏是Markdown 語法來格式化文本內容"  // 這是Markdown 語法來格式化文本，內容用來回傳一般的文字回答}
    }

    或

    {
    "type": "elements",  // 當 type 為 'elements' 時
    "data": {            // data 應該包含一個元素列表，此類型的回應用於回傳影片標題及連結資訊
        "elements": [
        {
            "label": "影片的標題文字",
            "url": "https://example.com"  // 這是影片的連結
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

# model = HfApiModel()

# 使用者資訊
users = {
    "user1": {"session_id": "session1"},
    "user2": {"session_id": "session2"},
    "user3": {"session_id": "session3"}
}

# ============================== cl 配置區 ==============================
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="請說明一下莫子 AI的功能",
            message="請說明一下莫子 AI的功能",
            icon="/public/idea.svg",
            ),
        ]


# ============================== Agent 工具區 ==============================
@tool
def get_full_video_subtitles_by_title(keyword: str) -> str:
    """
    根據影片標題關鍵字查詢影片的完整 YouTube 字幕（前2000個字）
    資料庫中的影片標題都有數字，若使用者詢問影片使用數字編號時，keyword只要設定為純數字即可搜尋，例如 "86"。

    Args:
        keyword: 影片標題關鍵字

    Returns:
        str: 包含完整字幕的字串（前2000個字）

    Example:
        使用此工具可以搜尋影片標題中包含特定關鍵字的影片內容。例如：
        - 搜尋 "第８６集說些什麼？" 可以使用關鍵字 "86" 來找到該集的內容。
        - 搜尋標題中包含 "什麼" 的影片內容。
        此工具也可以搭配其他工具來應用，例如先使用 `search_youtube_subtitles` 工具找到相關影片，再使用此工具獲取完整字幕。
    """
    if not keyword:
        return ""

    conn = None
    full_text = ""
    try:
        conn = psycopg2.connect(VF_DATABASE_URL, sslmode='require')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT vt.text
                FROM video_text vt
                JOIN video v ON vt.video_id = v.video_id
                WHERE v.title LIKE %s
                ORDER BY vt.start
                LIMIT 2000
            """
            cur.execute(query, (f"%{keyword}%",))
            rows = cur.fetchall()

            for row in rows:
                full_text += row['text']
                if len(full_text) >= 2000:
                    full_text = full_text[:2000]
                    break
    except Exception as e:
        print("資料庫查詢失敗:", e)
    finally:
        if conn:
            conn.close()

    return full_text

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
                LIMIT 6
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

@tool
def describe_ai_functionality() -> str:
    """
    回應這是一個什麼功能的 AI

    Returns:
        str: 描述 AI 功能的字串
    """
    description = """
    這個 AI 是一個友善且多話的智能體，目標是幫助用戶查詢 YouTube 影片字幕和關鍵字出現次數，並提供相關影片的標題及連結資訊。

    功能概述：
    1. 查詢特定主題或關鍵字最常出現的影片。
    2. 根據影片標題關鍵字查詢影片的完整 YouTube 字幕（前2000個字）。
    3. 查詢指定影片的 YouTube 字幕段落列表。

    角色特點：
    1. 友善且多話：智能體以友善且熱情的態度與用戶交流，並會主動提供詳細的建議和資訊。
    2. 主動提供建議：根據查詢結果，智能體會主動提供進一步的建議，例如推薦相關影片。
    3. 解決需求和痛點：智能體會幫助用戶分析需求和痛點，並提供解決方案，確保查詢順利進行。

    使用此 AI，您可以輕鬆查詢和獲取 YouTube 影片的相關資訊，提升您的使用體驗。
    """
    return description

@tool
def summarize_video_content(video_content: str) -> str:
    """
    根據影片內文給出影片內容總結

    Args:
        video_content: 影片內文

    Returns:
        str: 影片內容總結
    """
    if not video_content:
        return "影片內文為空，無法總結。"

    try:
        # 使用模型生成影片內容總結
        messages = [
            {"role": "user", "content": [{"type": "text", "text": f"請總結以下影片內容：\n\n{video_content}"}]}
        ]
        summary = model(messages)
        return summary.content
    except Exception as e:
        print("生成影片內容總結失敗:", e)
        return "生成影片內容總結失敗，請稍後再試。"

search_agent = CodeAgent(
    tools=[search_youtube_subtitles, get_videos_with_most_mentions, get_full_video_subtitles_by_title, describe_ai_functionality, summarize_video_content],
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

def process_user_message(user_message, history):
    return search_agent.run(user_message + SEARCH_AGENT_RESP_DESC + history)

@cl.on_message
async def on_message(message: cl.Message):

    msg = cl.Message(content="請稍等，我們正在處理您的請求。")
    await msg.send()

    try:
        user_message = message.content

        # 獲取使用者的對話歷史
        history = cl.user_session.get("history", "")

        # 更新對話歷史
        history += f"\nUser: {user_message}"

        # 傳給 agent 處理
        response = await cl.make_async(process_user_message)(user_message, history)

        # 更新對話歷史
        history += f"\nAI: {response.get('data', '')}"
        cl.user_session.set("history", history)

        # 判斷格式並回傳
        if response.get("type") == "text":
            msg.content = ""

            # 如果是純文字格式
            response_content = response.get("data", "未提供的文字")

            # 使用正則表達式依據 `，` 或 `。` 來拆分 token
            tokens = re.split(r'[，。]', response_content)

            # 逐步發送每個 token
            for token in tokens:
                await msg.stream_token(token + " ")  # 加上空格以保持單詞之間的間隔

            # 最後更新訊息
            await msg.update()
        elif response.get("type") == "elements":
            # 如果是 elements 格式
            elements_data = response.get("data", {}).get("elements", [])
            elements = [cl.Text(content=f"[{item['label']}]({item['url']})") for item in elements_data]
            msg.content = "這是包含連結的元素"
            msg.elements = elements
            await msg.update()
        else:
            # 如果格式不正確
            msg.content = "格式不正確或未定義"
            await msg.update()
    except Exception as e:
        msg.content = "發生錯誤，請重新問問題或稍等一下再試。"
        await msg.update()
        print("處理訊息時發生錯誤:", e)
