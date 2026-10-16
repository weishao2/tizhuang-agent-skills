# 知识树、教材目录与中文化迁移

当前起步包使用 `teacher/v2` 布局：可见知识树在 `资料/知识目录`，教材章节在 `资料/教材目录`。插件 0.14.1 在下载后自动生成可点击目录；已有内部快照而左侧为空时，打开本地题库首页会离线补齐。此过程不重新取题、不消耗额度，也不覆盖已有目录笔记。判断下载是否完整时，同时检查 `.bank/taxonomy` 快照和可见目录，不能只凭“第一步已完成”。

## 网站知识树

学科/学段 ID 来自公开元数据（`https://tizhuang.qcscience.cc/api/v1/meta/subjects`、`/v1/meta/phases`）或老师给出的 ID。

```text
<python> <cli> --vault <vault> catalog --subject 2 --phase 2      # 首次下载前缓存真实学科/学段/教材名称
<python> <cli> --vault <vault> tree --subject 2 --phase 2
<python> <cli> --vault <vault> tree-search --subject 2 --phase 2 --query 一次函数
```

使用公开元数据，不依赖旧 skill，也不消耗题目额度。离线可用 `--file <tree.json>`。`知识库/标准知识点/<学段·学科>` 是生成内容，老师笔记写在 `知识库/我的教学笔记`，刷新不会改动。下载只提供层级与 ID，不含题目或完整讲解。`knowledge_tree_ids`（树节点）和 `knowledge_ids`（精确知识点）含义不同，不得互相推断。

## 教材版本与章节

知识树不是教材目录。教材相关任务先确认老师的真实版本（含 2024 修订、五四/六三学制）、年级和学期；不默认人教版，也不把名称相近的版本视为相同：

```text
<python> <cli> --vault <vault> editions --subject 2 --phase 2
<python> <cli> --vault <vault> chapters --subject 2 --phase 2 --edition <edition-id>
<python> <cli> --vault <vault> chapter-search --subject 2 --phase 2 --edition <edition-id> --query 一次函数
```

下载该版本的全部章节，保留每个节点来源的年级 ID（源数据里可能表示学期/册，请解析真实名称，不做算术换算），写入 `教材目录/<学段·学科·教材版本>`。离线可用 `--file <chapters.json>`。教材相关入库显式传 `--edition <id> --chapter <id…>`，且只在老师或原始查询确定归属时使用；网站返回没有版本信息时不要用知识点名称推断。未知版本保持未知，会被按版本的筛选排除。章节筛选需要 subject+phase+edition，并包含子孙章节。

## 英文旧目录 → 中文布局

先 `catalog` 缓存真实名称；旧目录库用 `migrate-cn --catalog-labels <names.json>`（JSON 含 subjects/phases/editions，各为 ID→真实名称）。迁移会在库旁生成完整 ZIP 备份，保留老师多出的笔记段落并更新链接，隐藏旧机器目录。不要自己重命名文件夹或删除旧副本。可见目录：`题目库`、`知识库/标准知识点`、`知识库/我的教学笔记`、`教材目录`、`附件`、`试卷`、`待整理`；知识/章节笔记显示名称，最多两级祖先目录，ID 放在中文属性里。题目文件可改名而 ID 不变；便携 JSON 的键和包内 `Assets/` 路径不变。
