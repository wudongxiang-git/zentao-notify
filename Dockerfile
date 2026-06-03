# zentao-notify：禅道 Bug 推送到飞书（轮询 daemon）
# 默认使用阿里云 Docker Hub 镜像缓存，避免 registry-1.docker.io 匿名拉取 429
# 海外 CI 可覆盖：docker build --build-arg BASE_IMAGE=python:3.11-alpine .
ARG BASE_IMAGE=registry.cn-hangzhou.aliyuncs.com/library/python:3.11-alpine
FROM ${BASE_IMAGE}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

COPY config.py zentao_client.py feishu_notifier.py notifier.py main.py ./

ENV TZ=Asia/Shanghai
ENV PATH="/app:${PATH}"

# 状态文件可挂载到 /data
ENV STATE_FILE=/data/state.json
RUN mkdir -p /data

CMD ["python", "main.py"]
