# 本地题库工作流

适用版本：1.0.1。所有操作只进入 **tizhuang-studio 当前工作目录**，不读取或改写 Obsidian 库，两个现有技能保持独立。

## 先读再改

1. 读取 `state`，确认 workspace、revision、catalogs、library_stats 和当前 items。沿用工作目录，不能为了完成任务另建老师找不到的题库。
2. `search` 找到候选题，`show --ids ...` 读题干、答案、解析、配图与 `content_sha256`。图片用本机查看工具检查。
3. 用 `library --json @操作.json` 修改。文件必须包含 action、最新 revision、一次性 request_id。CLI 自动标记 actor=Agent。
4. 读回结果再汇报；页面会同步。不要直接编辑 SQLite 或 session.json，不把 Key/OAuth 令牌放入操作 JSON。

```text
python scripts/studio.py --workspace <工作目录> state
python scripts/studio.py --workspace <工作目录> search --catalog knowledge-2-2 --node 1480 --status draft --limit 30
python scripts/studio.py --workspace <工作目录> search --tag 期末 --unused
python scripts/studio.py --workspace <工作目录> show --ids <题号>
python scripts/studio.py --workspace <工作目录> library --json @操作.json
```

`search` 支持 keyword、catalog、node（包含后代节点）、tag、type、status（draft / reviewed / unclassified）、unused、archived、limit。只读，不取新题，不扣额度。`state` 返回完整目录快照，适合 Agent 查真实节点。

## 目录与分类

| action | 字段 | 说明 |
|---|---|---|
| catalog-fetch | kind=knowledge/chapter, subject_id, phase_id, label；章节加 edition_id | 用页面服务内存中的 API Key 调受保护目录接口并落盘 |
| catalog-save | 上述范围 + nodes 数组 | 保存已授权 MCP 或可信缓存取得的真实目录；不接受虚构节点 |
| auto-classify | 可选 ids | 对尚无知识点的题按 knowledge / tags 与目录名称 **唯一完全相同** 匹配；不会模糊猜测 |
| classify | ids, hashes, knowledge_tree_ids, chapter_ids, tags, edition_id（可部分提交） | 批量设置分类；字段数组是替换，不是追加 |
| edit | id, hashes, text, format, type, title, notes | 可编辑正文；保存后回到待核对，保留历史 |
| create | subject_id, phase_id, text, format, type, title, notes | 新建自编题，必须明确标为自编，不能伪装网站原题 |
| review | ids, hashes, confirm=true | 由老师核对；Agent 仅在老师明确核对这些具体题后可带 teacher_confirmed=true 提交 |
| archive | ids, hashes, confirm=true, archived=true/false | 归档或取消归档；仍在组卷篮的题需先移出 |

`hashes` 是 `{题号: show返回的content_sha256}`。正文变化后拒绝旧哈希；revision 防止页面和 Agent 相互覆盖。分类不改正文、不自动视为已核对。

目录 nodes 格式：`[{"id":1300,"name":"数与式","parent_id":0}, ...]`。节点必须属于正确学科学段，章节还须对应教材。保存后查询、分类、浏览可以离线使用。更新已有目录须显式 `replace:true`；如果删除的节点仍被题目引用，更新会拒绝。

一个题可关联多个知识点和章节。**找新题时**章节和知识点仍互斥；**整理已存题时**两个维度可同时记录。老师没选教材就只分知识点，不能猜教材章节。自动完全匹配不了的题：Agent 阅读后查真实树、选择合适节点，不能只根据标题盲目分类；无法判断就留待分类并说明。

```json
{
  "action":"classify","revision":12,"request_id":"<新UUID>",
  "ids":["123"],"hashes":{"123":"<show返回的哈希>"},
  "knowledge_tree_ids":["1513"],"tags":["课堂练习"]
}
```

编辑 text 为 `{content,answer,analysis}`，format 为 markdown 或 html，支持 LaTeX/MathML。编辑网页来源题时默认可保留 HTML/MathML；不要把已有 MathML 当纯文本重写。`notes` 为教学笔记，不进入试卷。配图只允许已保存的 `Assets/<SHA256>.png` 等图片路径，不能在编辑器插入远程追踪图片。原题没答案就留空并说明，AI 推导答案不能冒充原答案。

## 核对与组卷

未核对题可以暂放组卷篮，但不能直接生成正式稿。Agent 不得替老师勾选“我已核对”。请老师在页面查看题干、答案、解析、配图和 PDF 原页后确认；核对只作用于明确选择的题，不扩大到屏幕外题目。编辑内容会取消原核对状态。

核对完成后沿用 `command` 的 add / move / score / settings / export。导出同一快照的：

- `student.docx`：无答案 Word，可编辑文字、OMML 公式，图片嵌入。
- `teacher.docx`：原答案与解析 Word。
- `student.html` / `teacher.html`：独立打印稿，图片内嵌，浏览器打印或保存 PDF。

教学笔记不进入两版。答案未由 MCP 返回或题目包明确不含答案时，先补齐原答案再生成教师版，不自动调用收费取题。

### 整理和继续编辑已生成试卷

从 state 的 `exports` 读取试卷 id。以下操作仍通过 `command` 提交，包含最新 revision 和唯一 request_id：

- `paper-update`：传入 `id`、`title`、`tags`（最多 10 个，每个 1–24 字）。只修改列表名称与标签，不改已生成的 Word、打印稿或当前组卷篮。
- `paper-open`：先说明将替换当前组卷篮，得到用户明确同意后传入 `id`、`confirm:true`。恢复原稿题序、分值、时长与留白，使用题库当前内容，保留当前核对状态。缺失、归档或附件不完整的题目会阻止恢复。
- 继续修改后 `export` 会生成新稿并继承标签，原稿保留。修改卷头应在组卷设置中调整标题后重新生成。

## 备份与题目包

| action | 字段 | 行为 |
|---|---|---|
| backup | 无 | 完整 ZIP：题目、目录、篮子、PDF 原件、图片、历史稿、编辑历史；不含会话、Key、数据库运行文件 |
| package-export | ids, include_solutions=true/false | 导出选中题目与使用到的配图、目录快照；不含答案时连笔记和仅答案用图片一起剔除 |
| package-import | 通过 `--file <zip>` 提供 | 合并新题，同号跳过；不覆盖已有篮子和题目；新题待核对 |
| restore | `--file <完整备份.zip>`, confirm=true | 恢复前先自动备份，替换当前题目、目录、篮子与试卷记录 |

```text
python scripts/studio.py --workspace <目录> library --json @导入操作.json --file <题目包.zip>
```

恢复是替换操作，必须得到老师对目标工作目录和备份的明确指示，不能把“查看备份”当作恢复授权。恢复时当前会话仍保持有效，但历史操作记录不从备份导入，revision 持续递增。

支持 Studio v1 包及本地题库 `tizhuang.question-package/v1` 的文字/图片题目包。旧包没有目录快照时，旧节点编号保存在 unmapped 字段，先下载树再按真实节点重新分类。非图片附件目前会明确拒绝；不宣称任意 Obsidian 笔记或库可直接完整迁移。

界面“备份迁移”列出生成的 ZIP。个人题库只在指定电脑目录保存，不会自动云同步；保留目录与备份，隔几个月仍可继续使用。
# 取题进度与目录复用

工作台 `command fetch` 未指定 `offset` 时，使用当前工作区保存的范围进度；成功后按实际返回数量推进。页面与 Agent 共用，重启和完整备份恢复后保留。范围包括学段、学科、教材、年级、章节或知识点和关键词；取题数量改变不重置进度。除非老师明确要求重新取某一页，否则不要传 `offset: 0`。网络结果不明时先核对原始结果与额度，不自动重试。MCP 客户端自己的搜索分页不属于此进度。

取题校验优先读取本机对应目录，但会通过当前 Key 查询目录名额：范围已开通才复用缓存，未开通则按正常受限接口下载开通；鉴权失败立即停止。更新目录仍走 catalog-fetch 并明确 replace，不通过缓存绕过额度。

标签检索 `--tag 期中` 同时匹配 `期中/易错题` 等子标签；题目包和原始标签仍保留完整路径。

