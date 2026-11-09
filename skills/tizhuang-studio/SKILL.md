---
name: tizhuang-studio
description: 题庄题库工作台。在 Agent 中找真实题目、保存本地题库、按知识点和章节分类、导入 PDF、核对编辑、组卷导出 Word、备份迁移；Agent 与网页共用题库和组卷篮，不依赖 Obsidian。用户指定题庄 2.0、工作台或在 Agent 中保存组卷时使用；两个既有技能仍独立使用。
metadata:
  version: 1.0.1
---

# 题庄 · 题库工作台

这是题庄主推的本地题库技能，替代旧 Obsidian 版的新安装入口。旧版保留历史下载，不再更新；不自动覆盖或转换旧题库。在线找题，本机保存备课工作区。UI 沿用题庄插件的交互，不需要 Obsidian。支持知识点/教材目录、标签、分类、编辑、核对、PDF Agent 分题、共享组卷、Word 双版、打印稿和备份迁移；不含云端私有题库或跨设备自动同步。

## 自动安装与更新

从官方完整包解压后运行：

```text
python scripts/install.py --target <当前Agent的skills目录>/tizhuang-studio --workspace <独立题库目录>
```

安装器自动创建独立 `.venv`、安装依赖并运行 doctor；同内容跳过，旧版先备份再更新，新版不降级。程序目录与题库目录必须分开，更新不删除未知文件，不改两个旧 Skill。Python 缺失时先安装官方 Python 3.10+。体检未成功不能说安装完成。然后运行下方启动命令；更新运行中的服务前先保存工作，不能杀掉不属于这个工作区的服务。详细安装见 [references/install.md](references/install.md)。

## 启动

1. 确定一个专用于此技能的工作目录，沿用用户已打开的工作台目录，不另建第二个篮子。不要使用或改写用户现有 Obsidian 题库。
2. 找到 Python 3.10+，执行 `python scripts/studio.py --workspace <绝对工作目录> doctor`。缺依赖时，在本技能独立 `.venv` 安装 `scripts/requirements.txt`；再次体检通过再汇报可用。不改两个既有技能、全局 Python 或它们的环境。
3. 如工作目录已有 `session.json`，先用 `state` 验证服务可用。成功则复用其地址；否则运行 `serve --port 4186`（端口占用则选空闲端口）。只监听 127.0.0.1。Windows 后台启动使用 `Start-Process -WindowStyle Hidden`，日志存新工作目录外；不要停止不属于本技能的进程。
4. 把服务返回的本机链接打开给用户。用户可在“连接题庄”输入 Key；也可在启动环境中提供 `QUESTION_SERVICE_LICENSE`。不要让用户把 Key 贴到聊天里，不打印、打包或写入脚本。界面输入的 Key 只在服务内存保存，重启后重填。

Windows 可直接执行 `scripts/start.ps1 -Workspace <绝对工作目录> -Python <已体检解释器> -Port 4186`，会优先复用已有工作台，或在后台启动新服务。独立环境首次配置可用 `python -m venv .venv`，再用 `.venv/Scripts/python.exe -m pip install -r scripts/requirements.txt`。

工作目录内的 `session.json` 含本机会话凭据，不上传；`studio.sqlite3`、`raw/`、`Assets/` 和 `exports/` 是老师的数据。更新技能仅替换程序文件，保留整个工作目录。

## Agent 通过 MCP 取题

客户端已经连接题庄 MCP 时，优先读 [MCP 取题入库流程](references/mcp-workflow.md)，通过其 OAuth 或 API Key 连接取题，再用 `import-mcp` 保存到当前工作区，可同时加入共享组卷篮。认证由客户端管理，不复制凭据到页面，不调用 fetch 重取同一批题。页面直接取题仍使用自己的 API Key。

## Agent 与界面共用状态

本地题库、知识树/教材树、标签分类、题目编辑、核对、备份与迁移：先读 [题库工作流](references/library-workflow.md)。PDF 原页识别、独立配图、可编辑分题入库：先读 [PDF 工作流](references/pdf-workflow.md)。页面和 Agent 共用这些能力，不要另建第二套存储。核对必须由老师完成，Agent 不得自行确认。

所有命令从这个技能目录运行，下方 `python` 替换成体检通过的解释器绝对路径。命令输出 JSON；向老师用正常中文汇报。

```text
python scripts/studio.py --workspace <目录> state
python scripts/studio.py --workspace <目录> search --keyword 反比例函数 --limit 10
python scripts/studio.py --workspace <目录> show --ids <题号> <题号>
python scripts/studio.py --workspace <目录> meta subjects
python scripts/studio.py --workspace <目录> meta phases
python scripts/studio.py --workspace <目录> meta knowledge-points --params '{"subject_id":2,"phase_id":2,"limit":5000}'
python scripts/studio.py --workspace <目录> quota
python scripts/studio.py --workspace <目录> command --json @<操作文件.json>
```

`search` 只搜索当前已获取题目，不会扣费。新题可通过客户端 MCP 取回后 `import-mcp` 保存，或通过页面 Key 调用 `fetch`。`show` 返回题干、答案、解析和配图路径；读原题再选择，不编造答案或改写题意。页面 `meta knowledge-points/chapters` 使用受保护目录接口，按账户既有“学段 × 学科”名额开通，不绕过目录额度。

每次修改先读 `state.revision`，再生成一次性的 `request_id`（UUID）。操作 JSON 示例：

```json
{"action":"add","ids":["123","456"],"revision":4,"request_id":"<新UUID>"}
```

| action | 其余字段 | 用途 |
| --- | --- | --- |
| fetch | subject_id, phase_id, count(1–20), 可选 knowledge_tree_id 或 edition_id+chapter_id, grade_id, keyword, offset | 获取真实题目；先查目录确认 ID |
| add | ids 字符串数组 | 加入篮子，自动去重 |
| remove | id | 从本卷移除，保留题目 |
| move | id, position | 移到第几题，从 1 起 |
| score | id, score | 分值 0–1000，最多两位小数 |
| settings | title, duration_minutes, answer_space_mm（可传部分） | 改标题、时长、留白 |
| export | 无 | 已核对题目从同一快照生成 Word 双版及 HTML 打印稿 |
| retry-prepare | id | 重新加载已取回题目的图片与公式，不重新取题 |
| demo | 无 | 用户需要演示时加载缓存真实题，明确标记为示例 |

`command` 自动标记操作者为 Agent。网页每 1.8 秒同步。不要直接改 SQLite、session 或前端存储来绕过接口。遇到版本冲突，重新读取并理解最新篮子，再应用仍符合用户意图的修改；不能盲目覆盖。网络超时后先查 state/额度，同一个 request_id 不会重复执行，但新的取题请求可能再次扣额。

章节和知识点互斥，也可都不选。学科、学段必填；未选具体节点时按该学段知识树根节点限定范围。不擅自放宽范围找题。用户已明确要求取题即可直接取，不增加“确认扣额度”弹窗。失败不自动重复请求。

导出前 `show` 检查所选题目及分值。原题没答案应说明，不代造答案。Word 中 LaTeX / MathML 转为可编辑公式；上游本身是图片的公式仍是图片，不声称全部可编辑。带合并单元格的复杂表格目前会停止导出并说明原因。导出成功后从 state.exports 返回下载链接；旧稿保持生成时快照。

## 开发与验证

运行 `python -m unittest discover -s tests -v`。发布前还需用真实 Key 在网页执行一次受保护目录和取题验收，分别验证 Word 双版、Agent 同步、窄屏、重启恢复和空白安装。测试用假 API 的结果不能表述为线上付费取题已验证。

复用来源及当前边界见 [references/implementation.md](references/implementation.md)。
