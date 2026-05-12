# Winter Bot

基于 AstrBot + DeepSeek 的 aespa Winter（金冬天）角色扮演 QQ 机器人。

## 功能

- **Winter 人格对话** — 2000+ 字系统提示词 + 13 组对话示例，模仿 Winter 的语气和表达习惯
- **Instagram 监控** — 自动检测 imwinter 新帖，LLM 翻译非中文文案，图文推送到 QQ 私聊
- **知识库** — 60+ 条 Winter 真实语录、采访摘录、aespa 团体背景资料

## 目录

| 目录 | 内容 |
|------|------|
| `persona/` | Winter 人格提示词（JSON，可导入 AstrBot WebUI） |
| `knowledge_base/` | 语录 (`winter_quotes.md`)、采访 (`winter_interviews.md`)、事实 (`winter_facts.md`)、团体 (`aespa_context.md`) |
| `plugins/instagram_monitor/` | Instagram 监控插件（AstrBot Star Plugin） |
| `scripts/` | B站字幕爬虫、人格离线测试、API 费用估算 |

## 部署

1. 安装 [AstrBot](https://github.com/Soulter/AstrBot) v4.24+
2. 将 `plugins/instagram_monitor/` 目录联接到 `AstrBot/data/plugins/`：
   ```
   mklink /J AstrBot\data\plugins\instagram_monitor winter-bot\plugins\instagram_monitor
   ```
3. 在 AstrBot WebUI 中导入 `persona/winter_persona_import.json`
4. 配置 DeepSeek API Key，默认人格选 `winter`
5. 修改 `plugins/instagram_monitor/data/cfg.json` 中的代理端口（如需要）

## 命令

| 命令 | 功能 |
|------|------|
| `/ins 订阅` | 订阅 Instagram 自动推送 |
| `/ins 取消` | 取消订阅 |
| `/ins 状态` | 查看监控账号、订阅数、检查间隔 |
| `/ins 最新 [N]` | 手动获取 imwinter 最新 N 条帖子（默认 3，最多 20） |

## 技术栈

Python · AstrBot · DeepSeek V4 · QQ Bot API · Instagram API 逆向

## 许可

MIT
