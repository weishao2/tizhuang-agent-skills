# 题目与题目包协议 V1

JSON UTF-8。支持单题或数组，附件相对输入 JSON 目录。不扫描附近文件。

```json
{
  "schema": "tizhuang.question/v1",
  "id": "optional-stable-id",
  "title": "一次函数例题",
  "content_format": "markdown",
  "content": "已知 $y=2x+1$，求 $x=3$ 时的函数值。",
  "answer": "7",
  "analysis": "代入可得 $y=2\\times3+1=7$。",
  "subject_id": 2,
  "phase_id": 2,
  "grade_id": null,
  "edition_id": null,
  "type": "计算题",
  "difficulty": null,
  "score": 5,
  "status": "draft",
  "knowledge_tree_ids": [],
  "knowledge_ids": [],
  "chapter_ids": [],
  "tags": ["老师自编"],
  "source": {"kind": "local", "provider": "", "external_id": "", "label": "老师自编"},
  "assets": []
}
```

`content_format`: markdown/html，同时应用于答案解析。打印清除脚本、远程资源，只允许本地图。母子题一起保存，答案解析独立分区。空答案可以存 draft，不等于已核验。题干包含答案提示时不会语义自动删除，教师仍须查看打印稿。

`knowledge_tree_ids` 是树节点 ID；`knowledge_ids` 是精确知识 ID，不能互换。有树节点时要求下载相同 subject/phase 的树。结构校验不保证题目语义标注正确；跨知识体系不做自动推断。

`assets` 示例：`[{"path":"images/q1.png","sha256":"optional-on-local-import"}]`。支持 png/jpg/jpeg/gif/webp/pdf/txt/mp3/mp4。保存按哈希归档到附件目录，改写正文。teacher/v2 使用 `资料/附件`，Markdown 根据题目实际目录计算相对路径；包中内容统一用 `Assets/...`。在 Obsidian 手动增加图片后也要通过 JSON/ZIP 登记，才可完整导出。

`tags` 保存为 Obsidian 原生 `tags` 属性，兼容读取旧中文“标签”，两者并存以原生属性为准。`考点/一次函数` 可用于层级标签浏览。可选 `search_text`（本地属性“检索文字”）保存题图的可检索文字；它不是原题的替代内容，不参与打印，不应写入答案提示。

## ZIP

```text
questions.json
Assets/<sha256>.png
```

questions.json 为 `{"schema":"tizhuang.question-package/v1","includes_solutions":false,"questions":[上述单题对象]}`。附件带 SHA256。ZIP 最大100MB/1000条目，拒绝路径穿越、符号链接、重复名字和额外文件。不依赖数据库或网站凭证。

默认导出答案解析为空、无原始网站 JSON，只携带导出正文引用的附件。`--include-solutions` 明确包含答案解析。知识树不捆绑：接收方作为普通消费端可直接阅读；若导入另一个本地 bank 且有树节点关联，需先下载对应树。

`--website` 接收已有 skill 的 `{items:[QuestionOut...]}` 或 QuestionOut 数组，适配 title_html/options_html、answer_html/analysis_html、subquestions；原始单题响应存 `.bank/records/<id>.json`。不要传含凭证日志。导入不请求网站题目，不消耗取题额度。

## 维护

题目库/**/*.md 是内容和属性真源，必须递归读取；`.bank/records` 存来源与附件登记；`.bank/taxonomy` 存标准树快照，三者须共同备份。SQLite 可删重建。成功试卷 manifest 保存题序、分值、生成时内容，供使用记录推导。

同学科/学段/年级/教材版本同正文视为重复；同题可在不同教材上下文保存为不同本地记录，但不能自动断言它适用于所有教材。同来源 ID 但正文不同报冲突，不覆盖。V1 只支持单 writer。批量导入逐题提交，后题失败不回滚已成功题；可重试去重，不宣称批次事务。

`edition_id` 对应网站 edition 表；`chapter_ids` 对应 chapter_tree，保存时必须属于指定学科/学段/版本。章节和通用知识点分别建模。章节的 grade_id 按网站源值保留；不能通过章名或年级数字自行转成用户档案年级 ID。题目不指定版本时为未标注，不会自动被任何版本筛选命中。教材版本/章节关联必须来自已确认的取题条件或教师标注，不是依据知识点名称推断。

树更新覆盖 Standard，不碰 Personal，不自动迁移删除/改变的节点关联。离线树只能验证结构与显式 scope，不能独立证明网站完整性。
