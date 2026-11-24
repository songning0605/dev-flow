# dev-workflow 架构说明

本文档说明 `dev-workflow` 独立单插件的整体分层架构、5 个原子节点与 `D/R` 双轴自定档机制、历史项目护栏、状态追溯主线，以及上游 `obra/superpowers` 自动同步流水线。

## 1. 整体分层架构

```
flowchart TB
    subgraph L1["1. Bootstrap 跨宿主接入层（无项目绑定）"]
        H1["Claude Code / Cursor / SDK<br/>hooks/hooks*.json -> run-hook.cmd -> session-start"]
        H2["Pi Harness<br/>.pi/extensions/dev-workflow.ts"]
        H3["Codex / Gemini CLI<br/>.codex-plugin/plugin.json | GEMINI.md"]
    end

    subgraph L2["2. 总控路由与自定档层 (skills/dev-workflow)"]
        R1["零配置探测 + 4 类意图分类<br/>Legacy/Greenfield + bug/feature/refactor/analysis"]
        R2["双轴独立定档<br/>Design D0-D3 | Review R0-R3"]
        R3["运行中自动升档<br/>Archeology / Scope / Deviation / STALE 触发器"]
    end

    subgraph L3["3. 5 个原子节点 + 确定性工具接缝 (custom/skills + scripts/)"]
        N1["Brainstorm<br/>repo-recon 快扫 + 代码考古 + 多方案"]
        N2["Save Design<br/>check-design 门禁 + Basis Hash + Decision Log"]
        N3["Improve Design (D0-D3)<br/>并发 N-Agent 查老代码评审"]
        N4["Impl (legacy-impl)<br/>表征测试 + TDD + verify-basis stamp"]
        N5["Review (deep-review R0-R3)<br/>verify-basis check + 多视角审查 + gen-report"]
        N1 --> N2 --> N3 --> N4 --> N5
        N2 -. "D0 跳过" .-> N4
    end

    subgraph L4["4. 12 个内置底座 (vendored dev-workflow:*)"]
        B1["brainstorming / writing-plans / executing-plans"]
        B2["subagent-driven-development / dispatching-parallel-agents"]
        B3["test-driven-development / systematic-debugging / verification"]
        B4["requesting-code-review / receiving-code-review / worktrees / finishing"]
    end

    subgraph L5["5. 确定性脚本层、状态沉淀与上游同步"]
        S1["Design Doc (Basis Hash) -> .git/dev-workflow-verify.json -> Commit Footer -> gen-report PR Body"]
        S2["scripts/{repo-recon,check-design,verify-basis,gen-report,log-metric,sync-upstream}.py"]
    end

    L1 --> L2 --> L3 --> L4 --> S1
    S2 -. "构建/周同步" .-> L4

```

## 2. 双轴独立定档与自动升档机制

`Improve Design` 与 `Review` 被设计为**同等重要、彼此独立的一等深度旋钮**，不采用二选一的刚性模式：

| 维度 | 判定信号（满足项越多，档位越高） | 档位行为 | 
| ----- | ----- | ----- | 
| **轴 A：设计不确定性 → `Improve Design` (`D0–D3`)** | 需求含糊 / 跨模块或数据契约变更 / 存量高耦合需找接缝 / 设计失误返工成本高 | `D0` 跳过；`D1` 2 并发（自由 + 回归）；`D2` 3 并发（+ 最小侵入）；`D3` 5 并发（+ 可测试性 + YAGNI，支持第 2 轮收敛） | 
| **轴 B：实现与回归爆炸半径 → `Review` (`R0–R3`)** | 触碰核心链路、并发、权限或持久化 / 老代码缺单测 / 多文件原地修改 / 前置设计偏简略 | `R0` 测试自检；`R1` 1 次全分支只读终审；`R2` 关键点 + 全分支终审；`R3` 逐任务双审 + 3 视角并发全分支终审 | 

### 动态流转与自动升档（Escalation）

```
stateDiagram-v2
    [*] --> Detect: 零配置探测 + repo-recon.py 意图/IDF快扫
    Detect --> Calibrate: 计算 D0-D3 与 R0-R3 并一句话亮牌
    Calibrate --> Brainstorm: 用户确认或手调 (analysis 模式只读止步于分析)
    Brainstorm --> SaveDesign: 达成 Approaches 共识 + check-design.py 质量门禁
    Brainstorm --> Calibrate: 考古发现隐藏调用方/状态机 (D 自动升档)
    SaveDesign --> ImproveDesign: D >= 1
    SaveDesign --> Impl: D == 0
    ImproveDesign --> Impl: 聚合 Must-Fix/Trade-Off 并更新 Decision Log
    Impl --> Review: verify-basis.py stamp + 传递 Escalation Flags
    Review --> EscalateR: SCOPE_EXPANDED / DESIGN_DEVIATION / NO_CHAR_TEST / STALE
    EscalateR --> Review: 自动升档 R 或重跑验证
    Review --> [*]: gen-report.py 去噪/越界报告 + Commit/PR 挂载 Design

```

## 3. 历史项目（Legacy Mode）五项护栏

当总控探测到目标仓库已有提交历史与业务代码时，自动启用 Legacy Mode：

1. **前置代码考古**：Brainstorm 阶段先查调用链（callers/callees）、隐式入口（MQ/Cron/配置）与近期 `git log`，再提出方案。

2. **变更边界契约**：`save-design` 强制记录现状与隔离接缝（Seam）、影响面、兼容与脏数据处理、回滚方案以及明确不动的历史债（Non-Goals）。

3. **基于真实代码的并发评审**：`improving-design` 派发的 `N` 个独立子代理拥有只读代码库权限，必须用 `grep`/读文件证伪设计假设，防止脱离现状的空谈建议。

4. **表征测试 + 增量 TDD + Strict Scope Lock**：修改存量逻辑前先补表征测试锁住现网行为；新逻辑走严格 RED→GREEN TDD；严禁顺手重构或格式化无关老代码。

5. **全链路设计可追溯**：`Design Doc` 独立提交 → 实现 Commit Footer 附 `Design: <path>` → PR 自动注入 `## Design & Key Decisions`。

## 4. 目录职责边界（源码层 vs. 构建产物层）

| 路径 | 角色 | 说明 | 
| ----- | ----- | ----- | 
| `custom/skills/` | **定制源码（Source of Truth）** | 6 个自有原子技能（`dev-workflow`、`save-design`、`improving-design`、`legacy-impl`、`deep-review`、`retro-evolve`），永不被上游同步覆盖 | 
| `custom/patches/patches.json` | **声明式上游补丁** | 对上游 3 个文件的最小锚点补丁（`brainstorming`、`implementer-prompt.md`、`finishing-a-development-branch`），锚点失效时显式报错 | 
| `vendor-manifest.json` & `upstream.lock` | **上游清单与版本锁** | 声明抽取的 12 个 `obra/superpowers` 技能、命名空间重写规则（`superpowers:` → `dev-workflow:`）及已同步 commit SHA | 
| `skills/` | **最终运行时技能目录** | 由 `scripts/sync-upstream.py` 合并上游 12 个技能 + 定制 5 个技能 + 补丁后的完整产物，零外部依赖 | 
| `hooks/` & `.pi/` & `.*-plugin/` | **多平台接入层** | 适配 Pi、Codex (App/CLI)、Cursor、Claude Code、Gemini CLI 与 Copilot SDK | 
| `tests/` | **自动化防回归防线** | `test_plugin.py`（跨平台全量自检）+ `tests/pi/test-pi-extension.mjs`（Pi 扩展生命周期单测） | 

## 5. 上游自动同步流水线

1. **定时巡检**：`.github/workflows/sync-upstream.yml` 每周一对比 `obra/superpowers` 的 `main` HEAD 与 `upstream.lock`。

2. **自动构建**：检测到新提交后执行 `python3 scripts/sync-upstream.py`：拉取上游 → 抽取 12 个技能与 MIT `LICENSE` → 批量重写 `superpowers:` 为 `dev-workflow:` → 叠加 `custom/skills/` → 施加 `custom/patches/patches.json` → 运行 `tests/test_plugin.py`。

3. **自动交付或告警**：测试全绿自动开 PR；若上游改动导致补丁锚点失效，自动开带错误日志的 Issue 提醒人工微调对应补丁。

## 6. 受控自进化架构（方案 B）

`dev-workflow` 采用**双轮进化模型**：

* **外部进化**：由 `scripts/sync-upstream.py` + GitHub Actions 每周自动吸收 `obra/superpowers` 上游脚本与底层提示词更新。

* **内部进化（方案 B）**：由 `scripts/log-metric.py` + 第 6 个原子技能 `dev-workflow:retro-evolve` 组成，基于真实历史项目的执行信号持续校准 `D/R` 阈值、并发评审视角与 `Red Flags`，同时从机制上杜绝日志爆炸与 Prompt 腐烂（Prompt Rot）。

### 6.1 自进化闭环流程图

```
flowchart LR
    A["deep-review 收尾"] -->|"1 行白名单摘要 (<=500B)"| B["scripts/log-metric.py log"]
    B --> C[("~/.agent-plugins/<br/>dev-workflow-metrics.jsonl")]
    C -->|"按需触发: tail -n 30<br/>只读滑动窗口"| D["dev-workflow:retro-evolve"]
    D --> E["3 条进化铁律过滤<br/>复现>=2-3次 + 减法优先 + 只改源码"]
    E -->|"<=3 条 Diff 提案"| F{"人工审批"}
    F -->|"拒绝 / 仅采纳部分"| G["放弃或局部修改"]
    F -->|"批准"| H["写入 custom/skills/"]
    H --> I["sync-upstream.py --local-only<br/>构建 skills/ + 跑 8 项自检"]
    I --> J["log-metric.py rotate --keep 10<br/>旧记录按月归档"]
    J --> K["git commit chore(evolve): ...<br/>随时可 git revert"]

```

### 6.2 `dev-workflow-metrics.jsonl` 白名单 Schema

日志固定存放在用户本机目录 `~/.agent-plugins/dev-workflow-metrics.jsonl`（**绝不写入业务代码仓库**）。每完成一次任务只追加 1 行紧凑 JSON，严格限制字段白名单：

| 字段 | 类型 / 允许值 | 约束 | 进化分析用途 | 
| ----- | ----- | ----- | ----- | 
| `ts` | ISO-8601 UTC 字符串 | 自动生成 | 按时间窗口排序与归档 | 
| `mode` | `legacy` | `greenfield` | 枚举强校验 | 区分存量历史项目与新项目的定档表现 | 
| `init_d` / `final_d` | `D0` | `D1` | `D2` | `D3` | 枚举强校验 | 检测 `Improve Design` 初始定档是否频繁偏低/偏高 | 
| `init_r` / `final_r` | `R0` | `R1` | `R2` | `R3` | 枚举强校验 | 检测 `Review` 初始定档是否频繁被升档 | 
| `escalations` | 字符串数组 | 仅限 `D_ESCALATED`, `SCOPE_EXPANDED`, `DESIGN_DEVIATION`, `NO_CHAR_TEST` | 统计最常触发的运行时风险信号 | 
| `hit_perspectives` | 字符串数组 | 仅限 `free-form`, `legacy-compat`, `minimal-diff`, `testability`, `yagni` | 衡量 5 个并发设计评审视角的真实 ROI，淘汰低效视角 | 
| `missed_by_design` | 布尔值 | `true` | `false` | 标记 Review 阶段是否抓出了设计阶段漏掉的重大问题 | 
| `ruling_count` | 非负整数 | `>= 0` | 衡量实现期偏离设计的频次 | 
| `friction_tags` | 短标签数组 | 最多 3 个标签，每个 ≤ 32 字符；**禁止代码/diff/路径** | 归类跨项目重复出现的人工纠偏与流程摩擦 | 

### 6.3 防日志爆炸与防上下文爆炸护栏

1. **硬字节上限**：`scripts/log-metric.py` 在写入前强制校验单行 UTF-8 字节数 **≤ 500 字节**，超限直接拒绝写入（按每天 3 个任务计，一年约 400 KB）。

2. **滑动窗口读取**：`retro-evolve` 禁止直接读取整个 JSONL 文件，强制通过 `log-metric.py tail -n 30` 只取最近 30 条记录，确保复盘上下文开销恒定在几 KB 以内。

3. **复盘即归档**：每次进化落地后执行 `log-metric.py rotate --keep 10`，将已消化的旧记录按月追加归档至 `dev-workflow-metrics-archive-YYYYMM.jsonl`，活跃文件始终保持极简。

4. **隐私与业务隔离**：严禁把业务代码片段、原始 `git diff`、文件路径或堆栈信息写入日志。

### 6.4 `retro-evolve` 的 3 条进化铁律

1. **复现门槛（防过拟合）**：同一类摩擦、升档或盲区必须在窗口内**跨 ≥ 2～3 个任务复现**才允许提议改全局规则；单项目特例一律忽略。

2. **减法优先（防提示词膨胀）**：每次复盘最多提议 **3 条变更**，且每新增 1 条规则/视角指令，必须同时检查能否合并或删除 1 条长期零命中/冗余的旧规则。

3. **源码层审批 + 测试门禁**：所有修改只针对 `custom/skills/`，必须经人工明确确认 Diff 后才落盘，并强制跑通 `python scripts/sync-upstream.py --local-only`（全部 8 项自检）后以独立 `chore(evolve):` commit 留档，随时可 `git revert`。

### 6.5 常用命令与触发示例

```
# 查看最近 30 条结构化复盘指标
python C:\Users\mrn\.agent-plugins\dev-workflow\scripts\log-metric.py tail -n 30

# 手动归档旧记录（只保留最近 10 条在活跃文件）
python C:\Users\mrn\.agent-plugins\dev-workflow\scripts\log-metric.py rotate --keep 10

# 审批并修改 custom/skills/ 后离线秒级重建 + 全量 8 项校验
python C:\Users\mrn\.agent-plugins\dev-workflow\scripts\sync-upstream.py --local-only

```

在 Pi / Cursor / Codex / Claude Code 中触发周期进化：

> `用 dev-workflow:retro-evolve 分析最近 30 条运行记录，给出针对 custom/skills 的优化提案`

## 7. 确定性工程辅助脚本层（融合 dsh-dev-hub 优势）

为弥补纯 Prompt 工作流在大型老项目定位、需求质量门禁、测试防过期与交付去噪上的不确定性，`scripts/` 新增 4 个零外部依赖 Python 3 CLI（与既有 `log-metric.py`、`sync-upstream.py` 同构）：

| 脚本 | 接入节点 | 核心能力 | 产物 / 退出码 | 
| ----- | ----- | ----- | ----- | 
| `scripts/repo-recon.py` | Step 1 / `Brainstorm` | 纯本地中英文分词 + IDF 权重快扫 + 4 类意图分类（`bug/feature/refactor/analysis`） | 候选文件、命中行、窄粒度 `suggested_scope` | 
| `scripts/check-design.py` | `Save Design` | 校验必填章节、Legacy 契约、占位符残留与 `isRawEcho` 原话照抄，生成 16 位 `design_basis_hash` | 校验通过退出 `0`，失败退出 `1` | 
| `scripts/verify-basis.py` | `Impl` / `Review` | 计算 `design_basis_hash + HEAD + diff + untracked` 联合指纹，写入 `.git/dev-workflow-verify.json`（零仓库污染） | `FRESH` 退出 `0`，`STALE` 退出 `2` | 
| `scripts/gen-report.py` | `Review` / PR 交付 | 自动剔除 `.DS_Store`/`dist/` 等噪声，比对 `Scope Lock` 标记越界文件并输出显式 `Evidence Boundaries` | 可直接嵌入 PR Body 的只读 Markdown 报告 | 
