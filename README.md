# dev-workflow（完全独立单插件版 + 多平台生态适配 + 上游自动同步）

一套**零外部依赖、不与业务项目绑定、开箱即用**的原子化研发流程单插件包（完整分层架构、双轴定档状态图与同步机制见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)）：

- **无需单独安装 `obra/superpowers`**：按 MIT 协议精选整合 12 个核心底层 Skill 与辅助脚本，并全部重写为 `dev-workflow:` 命名空间（共 18 个内置 Skill）。
- **5 个原子节点自由编排**：`Brainstorm` → `Save Design` → `Improve Design` → `Impl` → `Review`，任意节点均可单独触发。
- **`Improve Design (D0–D3)` 与 `Review (R0–R3)` 双轴独立自判断**：自动探测历史项目（Legacy Mode）与新项目，开局一句话亮出档位，支持随时回复如 `D3 R2` 手调，且执行中遇风险自动升档。
- **源码级历史项目改造**：内置 `brainstorming`（前置代码考古 + 解除强跳 `writing-plans`）、`implementer-prompt.md`（Strict Scope Lock 禁止顺手重构 + Commit 附 `Design:`）与 `finishing-a-development-branch`（PR 自动挂载 `## Design & Key Decisions`）。
- **自动化上游同步**：自带 `scripts/sync-upstream.py` 与 `.github/workflows/sync-upstream.yml`，推送到你的 GitHub 仓库后可每周自动同步 `obra/superpowers` 更新、自动打补丁、自动跑测试并提 PR。

## 平台生态适配总览

| 平台 / 工具 | 适配文件 | 自动注入 / 触发机制 | 并发多 Agent 支持 | Windows 注意事项 |
| :--- | :--- | :--- | :--- | :--- |
| **Pi Harness** | `package.json` + `.pi/extensions/dev-workflow.ts` + `references/pi-tools.md` | Pi 原生 Extension（`session_start` / `session_compact` / `context`） | 配合 `pi-subagents` 并发，否则自动降级顺序多视角 | 原生 Node 运行，**无需 Git Bash** |
| **Codex (App / CLI)** | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` + `references/codex-tools.md` + `assets/` | Codex 插件系统加载 `skills/` + App 展示元数据 | 在 `~/.codex/config.toml` 开启 `multi_agent = true` 后使用 `spawn_agent` 并发 | Codex App 沙盒 detached HEAD 时自动输出可复制的 PR 模板与 Design 摘要 |
| **Cursor** | `.cursor-plugin/{plugin,marketplace}.json` + `hooks/hooks-cursor.json` | `sessionStart` Hook 自动注入总控路由 | 原生 Subagent 并发 | 需安装 Git for Windows 以运行 `sessionStart` Hook |
| **Claude Code** | `.claude-plugin/{plugin,marketplace}.json` + `hooks/hooks.json` | `SessionStart` Hook 自动注入总控路由 | 原生 Subagent 并发 | 需安装 Git for Windows 以运行 `SessionStart` Hook |
| **Gemini CLI** | `gemini-extension.json` + `GEMINI.md` | 扩展上下文文件自动加载 `dev-workflow/SKILL.md` | 按当前版本子代理能力或自动降级 | 原生支持 |
| **Copilot CLI / 通用 SDK** | `hooks/hooks.json` + `hooks/session-start` | 标准 `additionalContext` 输出 | 按宿主能力 | 需 Git for Windows |

> 建议解压到不含空格和括号的固定目录，例如：
> - Windows：`C:\Users\<你的用户名>\.agent-plugins\dev-workflow`
> - macOS / Linux：`~/.agent-plugins/dev-workflow`

## 各平台安装与配置指南

### 1. Pi Harness
```bash
# 正式安装（本地目录或推送后的 GitHub 仓库）
pi install C:\Users\<你的用户名>\.agent-plugins\dev-workflow
# 或：pi install git:github.com/<you>/dev-workflow

# 临时加载调试
pi -e C:\Users\<你的用户名>\.agent-plugins\dev-workflow
```
- 如需在 Pi 中开启 `improving-design`（D1–D3）与 `deep-review`（R3）的真正并发多 Agent，建议同时安装 `pi-subagents`。

### 2. Codex (App / CLI)
- **安装插件**：将目录推送到 GitHub 后在 Codex 插件市场添加，或按本地插件/marketplace 方式指向该目录（已完整包含 `.codex-plugin/plugin.json`、`interface` 展示元数据、图标资源和 `.agents/plugins/marketplace.json`）。
- **开启并发多 Agent（强烈推荐）**：在 `~/.codex/config.toml` 中添加以下配置，让 `improving-design` 和 `deep-review`（R3）真正通过 `spawn_agent {fork_turns: "none"}` 并发执行并控制子代理成本：

```toml
[features]
multi_agent = true

[agents]
default_subagent_model = "<填你允许列表中的中档模型>"
default_subagent_reasoning_effort = "medium"
```

- **Codex App 沙盒收尾**：如果在 Codex App 外部托管的 detached HEAD 工作树中无法直接 push，Skill 会自动提交代码并输出可直接粘贴进 App UI（Create branch / Hand off to local）的分支名、Commit 说明和 `## Design & Key Decisions` PR 描述。

### 3. Cursor
1. 打开 Cursor 的 Plugins 面板，点击 **+ Add → From Local Repository**。
2. 选择 `dev-workflow` 根目录（内置 `.cursor-plugin/marketplace.json`、`.cursor-plugin/plugin.json` 与 `hooks/hooks-cursor.json`）。
3. 启用后即可在任意项目自动触发 `SessionStart` 注入与全部 18 个技能。

### 4. Claude Code
```bash
# 方式 A：本地目录直接加载插件（自动注册 SessionStart Hook）
claude --plugin-dir ~/.agent-plugins/dev-workflow

# 方式 B：作为本地 Marketplace 注册安装
# 在 Claude Code 内执行：/plugin marketplace add ~/.agent-plugins/dev-workflow
```

### 5. Gemini CLI
```bash
gemini extensions install ~/.agent-plugins/dev-workflow
```

## 本地自检与上游自动同步

```bash
# 跨平台全量自检（Windows / macOS / Linux 通用）
python tests/test_plugin.py

# 单独运行 Pi 扩展单测（需 Node >= 22.6）
node --test tests/pi/test-pi-extension.mjs

# 方案 A 日常微调：改完 custom/skills/ 后 1 秒离线生效并跑自检
python scripts/sync-upstream.py --local-only

# 随时一键拉取最新 obra/superpowers 并重新构建
python scripts/sync-upstream.py
```

**开启 GitHub 每周自动同步**：将本目录推到你的 GitHub 仓库，在 `Settings -> Actions -> General -> Workflow permissions` 开启 `Read and write permissions` 并勾选 `Allow GitHub Actions to create and approve pull requests`，即可每周一自动巡检 `obra/superpowers`、自动打补丁、跑测并提 PR（如上游改了补丁锚点会自动提 Issue 提醒）。

## 受控自进化（方案 B）

- **自动记录（零业务污染、防膨胀）**：每次 `deep-review` 收尾会通过 `scripts/log-metric.py` 向 `~/.agent-plugins/dev-workflow-metrics.jsonl` 追加 1 行白名单指标（硬上限 ≤500 字节，不存代码/diff）。
- **按需复盘进化**：每攒够 10～15 个任务，发一句 `用 dev-workflow:retro-evolve 复盘最近 30 条记录并提出优化建议`，技能会自动遵守「≥2～3 次复现门槛 + 减法优先」，给出 `custom/skills/` 的 Diff 提案；经你确认后自动跑 `python scripts/sync-upstream.py --local-only` 全量校验并执行 `log-metric.py rotate` 滚动归档。

## 日常使用示例

- **自动全流程**：进入任意历史项目直接提需求，Agent 会先做代码考古，再用一句话亮出自动判定的档位（如 `Design D3 + Review R2`）。
- **随时覆盖深度**：直接回复 `D2 R3`、`D3 R1` 或 `D0 R2`。
- **单点调用原子节点**：
  - 「用 `improving-design` 对 `docs/designs/2026-11-19-refund-design.md` 跑一轮 D3（5 并发）评审」
  - 「用 `deep-review` 对当前分支按 R3 深度做多视角审查并生成附带 Design 的 PR 描述」
