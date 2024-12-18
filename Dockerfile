FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt
COPY requirements.txt /app/

# 安裝套件
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案所有檔案到容器中
COPY . /app

# 替換成你的 Flask 執行指令
# 假設 main.py 是你的 Flask 主程式，它會在 0.0.0.0:8080 上執行
ENV PORT 8080
EXPOSE 8080

# 如果 main.py 使用標準的 Flask 執行方式，請確定在main.py中
# 有這樣的啟動程式碼:
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080)
#
CMD ["python", "main.py"]
