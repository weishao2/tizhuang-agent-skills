# MCP 取题 → 当前工作台

支持 Agent 客户端通过 OAuth 或 API Key 连接题庄 MCP。认证、令牌保存与续期由客户端负责；工作台不接收令牌。页面“连接题庄”仍使用 API Key，与客户端 MCP 状态独立。

## 连接（二选一）

地址 `https://tizhuang.qcscience.cc/mcp`，Streamable HTTP。

- OAuth：支持 MCP OAuth 的客户端添加此地址，不填认证头，由客户端打开题庄授权页。用户完成登录授权，客户端管理刷新；401 时续期或重新连接，不向用户索取令牌。
- API Key：在客户端凭据设置里配置 `X-API-Key`。不要把真实 Key 写进技能、题目文件、命令参数或聊天。持续保存能力取决于客户端。

以下是现有 WorkBuddy 包使用的格式；其他客户端按其实际配置方式添加，不覆盖整份用户设置。

OAuth：
```json
{"mcpServers":{"tizhuang-question-bank-oauth":{"type":"streamableHttp","url":"https://tizhuang.qcscience.cc/mcp","timeout":30000}}}
```

API Key（仅客户端支持环境变量替换时使用）：
```json
{"mcpServers":{"tizhuang-question-bank":{"type":"streamableHttp","url":"https://tizhuang.qcscience.cc/mcp","headers":{"X-API-Key":"${QUESTION_SERVICE_LICENSE}"},"timeout":30000}}}
```

同一连接不要同时传 Bearer 与 X-API-Key。工具未挂载时，说明需要在 Agent 客户端连接题庄 MCP；不得将缓存、测试结果称为本次正式取题。不修改两个旧 Skill。

## Agent 操作

1. 读取页面提供的工作区路径，运行 `state`，复用现有服务和组卷篮。
2. 通过 MCP `get_quota` 检查额度，用目录工具和 `resolve_question_filters` 核实筛选。没有 phase 参数时，用真实年级或知识树限定学段；不能仅按学科宽泛取题，再填写 phase_id 冒充学段校验。缺少映射时先确认。
3. 调用 `search_questions` 或 `get_question`。用户要求教师答案版或完整带答案入库时，明确传 `include_solutions:true`；只看题且要求隐藏答案时保持默认。失败、超时或额度不足不自动重试，不切换认证方式重取同批题。
4. 将完整 `structuredContent`、CallToolResult 或其 JSON 文本输出存成 UTF-8 JSON 文件。只保存题目工具结果，不保存认证头、客户端配置或令牌；不手写、摘要或改造题干答案。每批最多 2 MB、100 题，过大时拆分已有结果，不重新取题。
5. 重新读取 `state.revision`，生成 request_id，再执行（占位符换为实际值）：

```text
python scripts/studio.py --workspace <当前工作区绝对路径> import-mcp --file <完整工具结果.json> --auth oauth --tool search_questions --subject-id <真实学科ID> --phase-id <核实的学段ID> --revision <当前revision> --request-id <新UUID> --add-to-basket
```

Key 连接使用 `--auth api_key`；单题使用 `--tool get_question`。只保存供老师选择时省略 `--add-to-basket`。auth 仅为来源标记，不是凭据，也不是授权成功的证明。

6. 检查返回的 `imported_ids` / `existing_ids` / `updated_ids` / `added_ids` / `failed_ids` / `solutions_missing_ids`。页面自动同步。导入不查询额度或重新取题，只可能下载题庄配图。
7. 用 `show` 读回原题，再使用 move / score / settings / export 调整和导出。不再调用页面 fetch 获取同批题。

## 重复、失败与答案

- 同 request_id 重复提交返回第一次结果。revision 冲突时读新状态，继续提交同一结果文件，不重新调用 MCP。
- 网站题号去重。已完整保存的题目不被覆盖；保留原题序、分值和答案。
- 先前隐藏答案的题目可用带答案结果补充，但仅允许题干与配图一致。再次调用 get_question 可能扣额度，按用户授权的完整入库/教师版需求执行并说明；工作台不自动补取。
- “MCP 未返回答案”会阻止双版导出；“上游返回了空答案”保留原样，不编造答案。
- 附件失败的题目保存为待重载，不自动入篮；`retry-prepare` 只重载图片，不重新取题。
- 入库仅保留题目白名单字段、来源标签，不保存整个 MCP 信封；认证字段和明显凭据会被拒绝。临时文件也应只含题目。

## 本机接口

CLI 调用 `POST /api/import-mcp`，自动使用工作区 session.json 中的会话；不要展示该会话。请求字段为 revision、request_id、auth_mode、tool、subject_id、phase_id、add_to_basket、result。result 是真实 MCP 输出（例如 structuredContent 中的 `{data:{items:[...]}}`），不是摘要。

接口仅限已认证本机同源访问，不接受工作区路径或 MCP 凭据。题目和篮子在一个 SQLite 事务中提交；失败时可能留下未引用的图片文件，但不会出现半批题目或半更新篮子。
