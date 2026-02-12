# zentao-notify：禅道 Bug 推送到飞书（轮询 daemon）
FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py zentao_client.py feishu_notifier.py notifier.py main.py ./

ENV TZ=Asia/Shanghai
ENV PATH="/app:${PATH}"

# 状态文件可挂载到 /data
ENV STATE_FILE=/data/state.json
RUN mkdir -p /data

CMD ["python", "main.py"]
