# zentao-notify

将禅道 Bug 推送到飞书群，支持指定 Webhook。轮询禅道 API 获取新增/更新的 Bug，以飞书交互卡片形式推送到指定群聊。

---

## 功能

- 定时轮询禅道 API，获取新增或更新的 Bug（支持 **REST v1 / v2** 与 **传统 Session API**）
- 通过飞书群机器人 Webhook 发送交互卡片（标题、严重程度、状态、创建人、链接等）
- 使用 `state.json` 记录上次检查时间，只推送该时间之后的 Bug，避免重复
- 常驻模式下复用登录状态，不重复登录；token 失效时自动重新登录并重试

---

## 环境要求

- Python 3.7+
- 禅道需开启 API 并配置可登录账号
- 飞书群中已添加「自定义机器人」并获取 Webhook URL

**禅道版本说明：**

- **21.7.6（开源版）**：使用 REST v1（`api.php/v1/tokens`），`ZENTAO_BASE_URL` 需带子路径，如 `http://192.168.11.141/zentao`
- **21.7.8+**：支持 REST v2，程序会优先尝试 v2 再回退 v1 / 传统 Session

---

## 配置

### 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| `ZENTAO_BASE_URL` | 禅道根地址（带子路径时包含，如 `http://192.168.11.141/zentao`） | 是 |
| `ZENTAO_ACCOUNT` | 禅道账号 | 是 |
| `ZENTAO_PASSWORD` 或 `ZENTAO_API_KEY` | 密码或 API Key | 是 |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook URL | 是 |
| `POLL_INTERVAL` | 轮询间隔（秒），默认 300 | 否 |
| `STATE_FILE` | 状态文件路径，默认 `./state.json` | 否 |
| `ZENTAO_PRODUCT_IDS` | 只拉取指定产品 ID，逗号分隔；空则全部产品 | 否 |
| `ZENTAO_USE_LEGACY_API` | 设为 `1`/`true` 强制使用传统 Session API | 否 |
| `ZENTAO_BUG_BROWSE_STATUS` | REST Bug 列表范围（禅道 browseType），默认 `all` | 否 |
| `ZENTAO_API_PAGE_LIMIT` | REST 分页每页条数，默认 `100` | 否 |
| `ZENTAO_URL_STYLE` | Bug 链接：`path_info`（默认）或 `get` | 否 |

可在项目目录下创建 `.env` 文件填写上述变量（一行一个 `KEY=VALUE`），程序启动时会优先读取。

---

## 安装与运行

### 安装依赖

```bash
pip install -r requirements.txt
```

### 常驻服务（按间隔轮询）

```bash
python main.py
```

登录状态会缓存，每轮只拉 Bug 与推送，不重复登录。

### 单次执行（适合计划任务 / cron）

```bash
python main.py --once
```

### 指定 Webhook（覆盖环境变量）

```bash
python main.py --once --webhook "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

---

## Docker

镜像内默认 `STATE_FILE=/data/state.json`，建议挂载持久化目录并传入环境变量。

**阿里云 ACR 自动构建**：`Dockerfile` 默认从 `registry.cn-hangzhou.aliyuncs.com/library/python:3.11-alpine` 拉取基础镜像，并走阿里云 PyPI 源，避免 Docker Hub `429 Too Many Requests`。本地或海外构建可指定官方镜像：

```bash
docker build --build-arg BASE_IMAGE=python:3.11-alpine -t zentao-notify .
```

**常驻运行：**

```bash
docker run -d --name zentao-notify \
  -e ZENTAO_BASE_URL=http://192.168.11.141/zentao \
  -e ZENTAO_ACCOUNT=admin \
  -e ZENTAO_PASSWORD=你的密码 \
  -e FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx \
  -v /path/to/data:/data \
  ghcr.io/你的用户名/zentao-notify:latest
```

**单次执行：**

```bash
docker run --rm \
  -e ZENTAO_BASE_URL=... -e ZENTAO_ACCOUNT=... -e ZENTAO_PASSWORD=... \
  -e FEISHU_WEBHOOK_URL=... \
  -v /path/to/data:/data \
  ghcr.io/你的用户名/zentao-notify:latest python main.py --once
```

---

## GitHub Actions

推送 `main` / `master` 或打 tag `v*` 时会自动构建并推送镜像到 GitHub Container Registry（ghcr.io）。  
PR 仅构建不推送。镜像标签：分支名、`latest`（main/master）、`v1.0.0`、`v1.0`、短 SHA。

---

## 项目结构

```
zentao-notify/
├── .github/workflows/build.yml   # CI：构建并推送 Docker 镜像
├── config.py                     # 配置（环境变量 / .env）
├── zentao_client.py              # 禅道 API 客户端（v1 / v2 / 传统 Session，登录缓存与失效重试）
├── feishu_notifier.py            # 飞书通知（文本 + Bug 卡片）
├── notifier.py                   # 轮询、去重、推送逻辑
├── main.py                       # 入口（--once / 常驻）
├── Dockerfile
├── requirements.txt
├── README.md
└── state.json                    # 运行后生成，记录上次检查时间
```

---

## 禅道 API 说明

- **REST v2**（21.7.8+）：`POST /api.php/v2/users/login` 获取 Token，再请求产品列表与 Bug 列表
- **REST v1**（开源版 21.7.6）：`POST /api.php/v1/tokens` 获取 Token；响应体为 `{products|bugs, page, total, limit}`（无 `status` 字段）；Bug 列表需分页并建议 `status=all`、`timeFormat=local`
- **传统 Session API**：`GET index.php?m=api&f=getSessionID&t=json` → `POST index.php?m=user&f=login` → `GET index.php?m=bug&f=getList&...`；若 v1/v2 均不可用会自动切换到此模式

按 `openedDate`、`lastEditedDate` 与上次检查时间过滤，只推送新产生或新更新的 Bug。

---

## 飞书配置

1. 在飞书群中添加「自定义机器人」
2. 获取 Webhook URL
3. 将 URL 配置到环境变量 `FEISHU_WEBHOOK_URL` 或运行参数 `--webhook`

---

## 故障排查

| 现象 | 处理 |
|------|------|
| 禅道登录失败 / 404 | 检查 `ZENTAO_BASE_URL` 是否包含子路径（如 `/zentao`）、账号密码、禅道是否开启 API |
| 飞书未收到消息 | 检查 `FEISHU_WEBHOOK_URL` 是否正确、机器人是否被禁用 |
| 没有推送 | 首次运行只记录当前时间为 `last_check_time`，之后只推送该时间之后的新 Bug；可删除 `state.json` 后再次运行（仍按时间过滤） |
| token 过期 | 程序会检测 401/认证失败并自动重新登录后重试一次，无需重启 |
| 链接 404 | 若禅道为 GET 路由，设置 `ZENTAO_URL_STYLE=get` |
| 推送失败反复重试 | 有失败时不更新 `state.json`，修复 Webhook 后会重推本轮 Bug |

---

## 依赖

- `requests`（见 `requirements.txt`）
