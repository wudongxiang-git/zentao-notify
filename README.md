# zentao-notify

将禅道 Bug 推送到飞书群，支持指定 Webhook URL。

## 功能

- 定时轮询禅道 REST API v2，获取新增或更新的 Bug
- 通过飞书群机器人 Webhook 发送交互卡片（标题、严重程度、状态、创建人、链接等）
- 使用 `state.json` 记录上次检查时间，只推送该时间之后的 Bug，避免重复

## 环境要求

- Python 3.7+
- 禅道需开启 REST API（v2），并配置可登录的账号
- 飞书群中已添加自定义机器人并获取 Webhook URL

## 配置（环境变量）

| 变量 | 说明 | 必填 |
|------|------|------|
| `ZENTAO_BASE_URL` | 禅道根地址，如 `http://192.168.11.141:8001` | 是 |
| `ZENTAO_ACCOUNT` | 禅道账号 | 是 |
| `ZENTAO_PASSWORD` 或 `ZENTAO_API_KEY` | 密码或 API Key | 是 |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook URL | 是 |
| `POLL_INTERVAL` | 轮询间隔（秒），默认 300 | 否 |
| `STATE_FILE` | 状态文件路径，默认 `./state.json` | 否 |
| `ZENTAO_PRODUCT_IDS` | 只拉取指定产品 ID，逗号分隔；空则全部产品 | 否 |

可在项目目录下创建 `.env` 文件填写上述变量（一行一个 `KEY=VALUE`），程序会优先读取。

## 安装

```powershell
cd zentao-notify
pip install -r requirements.txt
```

## 运行

**常驻服务（按间隔轮询）：**

```powershell
python main.py
```

**单次执行（适合计划任务 / cron）：**

```powershell
python main.py --once
```

**指定 Webhook（覆盖环境变量）：**

```powershell
python main.py --once --webhook "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

## 飞书配置

1. 在飞书群中添加「自定义机器人」
2. 获取 Webhook URL
3. 将 URL 配置到环境变量 `FEISHU_WEBHOOK_URL` 或运行参数 `--webhook`

## 禅道 API 说明

- 使用禅道 RESTful API v2：`POST /api.php/v2/users/login` 获取 Token，再请求 `GET /api.php/v2/products` 与 `GET /api.php/v2/products/:productID/bugs` 获取 Bug 列表
- 按 `openedDate`、`lastEditedDate` 与上次检查时间过滤，只推送新产生或新更新的 Bug

## Docker

镜像内默认 `STATE_FILE=/data/state.json`，建议挂载持久化目录并传入环境变量：

```bash
docker run -d --name zentao-notify \
  -e ZENTAO_BASE_URL=http://禅道地址 \
  -e ZENTAO_ACCOUNT=账号 \
  -e ZENTAO_PASSWORD=密码 \
  -e FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx \
  -v /path/to/data:/data \
  ghcr.io/你的用户名/zentao-notify:latest
```

单次执行（例如配合 cron）：

```bash
docker run --rm \
  -e ZENTAO_BASE_URL=... -e ZENTAO_ACCOUNT=... -e ZENTAO_PASSWORD=... \
  -e FEISHU_WEBHOOK_URL=... \
  -v /path/to/data:/data \
  ghcr.io/你的用户名/zentao-notify:latest python main.py --once
```

## GitHub Actions

推送 `main`/`master` 或打 tag `v*` 时会自动构建并推送镜像到 GitHub Container Registry（ghcr.io）。  
PR 仅构建不推送。镜像标签：分支名、`latest`（main/master）、`v1.0.0`、`v1.0`、短 SHA。

## 项目结构

```
zentao-notify/
├── .github/workflows/build.yml  # CI：构建并推送 Docker 镜像
├── config.py                    # 配置（环境变量 / .env）
├── zentao_client.py             # 禅道 API 客户端
├── feishu_notifier.py           # 飞书通知（文本 + Bug 卡片）
├── notifier.py                  # 轮询、去重、推送逻辑
├── main.py                      # 入口（--once / 常驻）
├── Dockerfile
├── requirements.txt
├── README.md
└── state.json                   # 运行后生成，记录上次检查时间
```

## 故障排查

- **禅道登录失败**：检查 `ZENTAO_BASE_URL`、`ZENTAO_ACCOUNT`、`ZENTAO_PASSWORD`（或 `ZENTAO_API_KEY`），以及禅道是否开启 API
- **飞书未收到消息**：检查 `FEISHU_WEBHOOK_URL` 是否正确、机器人是否被禁用
- **没有推送**：首次运行会写入当前时间为 `last_check_time`，之后只会推送该时间之后的新 Bug；可删除 `state.json` 后再次运行以重新全量判断（会按时间过滤，仍只推送“新”的）
