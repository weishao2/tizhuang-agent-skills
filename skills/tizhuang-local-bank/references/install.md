# Agent 安装、更新与跳过

用户要求安装或更新本地题库时，使用这个流程。常规存题、检索和组卷不触发软件更新。用户已授权安装时，检查后直接完成，不重复确认同一个安装动作。

首次获取完整包，读取公开的 [Agent 安装入口](https://github.com/weishao2/tizhuang-agent-skills/blob/main/docs/local-bank/INSTALL.md)。发行信息在 `https://raw.githubusercontent.com/weishao2/tizhuang-agent-skills/main/downloads/local-bank/latest.json`；下载对应 ZIP，校验 SHA256 后解压到临时目录。安装包不包含凭证、用户题目或已下载目录。

安装器只使用 Python 标准库。先检查 Python 3.10+，可以用当前 Agent 可用的 Python；缺少时由 Agent 通过操作系统正规安装方式配置独立 Python，不修改系统默认解释器或旧 skill 环境。Obsidian 缺少时按其官方渠道安装。用户已明确使用纯 Agent 模式时无需安装 Obsidian。

## 定位已有安装

运行包内 `skills/tizhuang-local-bank/scripts/install_local_bank.py --discover`，只读 Obsidian 的仓库登记与常见 Agent skill 位置，不扫整盘。优先使用当前任务中用户指定的路径；没有指定且只发现一个题庄题库，可自动选用。多个题庄题库时请用户选择，不批量更新。没有现有题库时，可在用户文档目录下创建“题庄本地题库”，先检查目标是否已有内容。

确定当前 Agent 的 skill 根目录。Codex 可用 `--agent codex`（尊重 CODEX_HOME），其他 Agent 用自身安装机制确定路径后传 `--skill-dir <根目录>/tizhuang-local-bank`。不得把当前运行环境默认为所有客户端的标准路径，不批量给其他 Agent 安装。已安装旧 `question-bank` 不改变此选择。

```text
<python> <解压目录>/skills/tizhuang-local-bank/scripts/install_local_bank.py --package <解压目录> --vault <持久题库路径> --skill-dir <新skill路径> --plan
<python> <解压目录>/skills/tizhuang-local-bank/scripts/install_local_bank.py --package <解压目录> --vault <持久题库路径> --skill-dir <新skill路径> --apply
```

只需要插件可加 `--skip-skill`；只需要新 skill 可加 `--skip-plugin`。`--skip-runtime` 仅在用户只要程序文件、或本次明确不配置 PDF/Word 环境时使用，不把它报告成完整安装成功。正式安装路径应位于下载包之外，临时解压目录不能用作用户的持久题库。

## 判断规则

- `install`：缺少组件，安装。
- `update`：版本较旧，备份后只替换清单内的程序文件。早期无 version.json 的本地 skill 按已识别的旧版更新。
- `skip_current`：版本和程序完整一致，跳过。
- `skip_newer`：用户版本更新，跳过，绝不降级。
- `repair`：同版本缺少程序文件时补齐；其他文件保持一致才自动修复。
- `preserve_modified`：同版本程序有用户修改，保留并说明；只有用户明确要求修复才加 `--repair`。

安装器重新检查状态后才写入，备份路径在结果中返回；写入失败回退已替换的文件。用户原题、图片、试卷、索引、密钥引用、筛选偏好和第三方插件设置不在更新清单中。已有题库不复制空白首页或模板，不执行 organize，不迁移或重建用户数据。旧 `question-bank` 从不写入。

## 运行环境与验收

现有 `pythonPath` 可用时直接复用并保持设置原文不变；不可用时保留原值并报告 `needs_attention`，由 Agent 查清原因后处理。没有 Python 路径时自动建立这个工具的独立虚拟环境，只补入 `pythonPath`，保留其他设置。安装器不向系统 Python 或旧 skill 环境安装依赖。

检查 JSON 的 `ok`、`ready`、组件状态与退出码。退出 2 表示程序操作已完成但仍有环境或修改版需要处理；不宣称完整可用。receipt `.tizhuang-install.json` 记录版本及 `runtime.python`，后续本地工作优先用此解释器；若没有 receipt，保留原来验证过的独立环境。

完成后汇报哪些安装、哪些更新、哪些跳过、题库路径及必要的下一步。首次 Obsidian 使用仍需用户启用第三方插件；更新后重载插件，新 skill 则重新开启 Agent 会话。不替用户更改受限模式、其他插件启用列表或账号凭证。
