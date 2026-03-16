# tg-digest

一个用于实验的 Telegram 内容提取项目。

目标：从群组或频道消息中，每天筛选 1-3 条适合写成文章的候选内容，主题聚焦在 APP 使用教学、故障排查和实用修复方案。

## 当前阶段

- 第一版优先支持 `Bot API polling`
- `MTProto` 已预留抽象接口，但暂未接入具体实现
- 聊天内容按天存储为 JSON 文件

## 推荐命令

如果安装了 `uv`：

```bash
uv venv
uv sync --extra dev
uv run python -m tg_digest
uv run python -m tg_digest worker
uv run ruff check .
uv run ruff format .
uv run mypy src tests
uv run pytest
uv run pytest tests/test_select.py::test_select_candidates_limits_count
```

如果没有 `uv`：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m tg_digest
python -m tg_digest worker
pytest
```

## 环境变量

程序启动时会优先读取根目录 `.env`，再读取当前 shell 环境变量。
建议先执行：

```bash
cp .env.example .env
```

然后把真实的 bot token 和群组 id 写入 `.env`。

- `TG_DIGEST_BOT_TOKEN`: Telegram Bot Token
- `TG_DIGEST_BOT_ALLOWED_CHAT_IDS`: 允许采集的 chat id，逗号分隔
- `TG_DIGEST_DATA_DIR`: 数据目录
- `TG_DIGEST_TIMEZONE`: 业务时区，当前默认 `UTC`
- `TG_DIGEST_POLLING_BATCH_SIZE`: 每轮 `getUpdates` 的批大小
- `TG_DIGEST_POLLING_INTERVAL_SECONDS`: worker 每轮轮询之间的等待秒数

## 数据目录

每日运行会在 `data/daily/YYYY-MM-DD/` 下生成：

- `messages.json`
- `candidates.json`
- `summary.json`
- `cursors.json`

`messages.json` 中会同时保存：

- 标准化后的 `text`
- 原始输入的 `raw_text`

这样即使群里出现“中文提问 + 英文回答”或其他混合语言对话，原始信息也会先被完整归档，方便后续再做更细分析。

## 说明

当前轮询实现会基于 `cursors.json` 中记录的 `offset` 持续增量抓取 `getUpdates`。
Bot API 在历史消息拉取方面能力有限，因此当前实现更偏向增量采集与本地归档。
后续接入 `MTProto` 后，可用于补拉历史消息。

## 运行方式

- 单次执行：`python -m tg_digest`
- 长期轮询 worker：`python -m tg_digest worker`

如果你已经配好了 `.env`，直接运行 worker 即可，它会：

- 读取 `cursors.json` 中已保存的 offset
- 循环调用 `getUpdates` 增量抓取
- 追加归档到当天 `messages.json`
- 重新生成当天候选结果与 summary
