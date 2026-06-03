# zentao-notify：禅道 Bug 推送到飞书（轮询 daemon）
# 默认 DaoCloud 同步 Docker Hub library，避免 docker.io 429 且无需 ACR library 命名空间权限
# 海外 CI：docker build --build-arg BASE_IMAGE=python:3.11-alpine .
# 若已在 ACR 控制台配置专属加速器，可传：--build-arg BASE_IMAGE=<加速器>/library/python:3.11-alpine
ARG BASE_IMAGE=docker.m.daocloud.io/library/python:3.11-alpine
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
