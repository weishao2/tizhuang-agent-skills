# 题庄本地题库 · 初始体验包

这是空白初始包，不含任何人的题目、PDF、知识树、账号和 API Key。新 skill 为 2.4.1，插件为 0.13.1。

1. 解压后，在 Obsidian 中“打开文件夹作为仓库”，选择 **题庄本地题库**。
2. 设置 → 第三方插件，允许插件并启用 **题庄本地题库**；打开“题库首页”。
3. 网站取题需要自己的题庄凭证，在插件中设置。不要发送到聊天或公开仓库。
4. PDF 导入、Word 组卷及 Agent 操作需要 Python 3.10+。Windows 用户运行 **安装本地环境.ps1**，它仅在本包目录建立独立环境，并配置此题库的 Python 路径。需要联网下载依赖。
5. 把 `skills/tizhuang-local-bank` 安装到 Agent 的 skills 目录，或请 Agent 按其 SKILL.md 配置。Codex 可放到 `~/.codex/skills/tizhuang-local-bank`。旧 `question-bank` 无需卸载或覆盖。

如果双击脚本只打开编辑器，请在此文件夹的 PowerShell 中执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\安装本地环境.ps1
```

安装后可以告诉 Agent：

> 使用 tizhuang-local-bank，在“填入题庄本地题库文件夹的实际路径”中导入这份 PDF。逐页核对，提取文字、公式和独立配图；先分知识点，教材暂不选。

> 从我的本地题库选已核对题，生成无答案 Word 和教师答案 Word。

PDF 由 Agent 识别和核对，插件不会自己调用一个内置视觉模型。原答案缺失不补造；正式组卷前由老师核对题干、答案和图片。本地检索、保存和组卷不扣题目额度，网站取题使用自己的额度。

## 已经安装过：更新需要的部分，其余忽略

- 已有题库：忽略包内空白题库，不要覆盖自己的题目、`.bank` 或其他 Obsidian 配置。
- 更新插件：先关闭插件；把包内 `题庄本地题库/.obsidian/plugins/tizhuang-question-bank` 的程序文件复制到自己仓库的同名目录，保留原来的 `data.json`；再启用插件。
- 更新新 skill：将 `skills/tizhuang-local-bank` 的文件复制到已安装的新 skill 目录，保留自己的 Python 虚拟环境。不要覆盖旧 `question-bank`。
- 版本相同、暂时不需要某个组件：直接忽略。

Windows 配置脚本默认只配置本包空白题库。已有题库可继续使用自己原来的 Python 路径；若需切换，在插件设置中指定新环境。移动整个解压目录后，重新运行配置脚本。

macOS/Linux 可按 `skills/tizhuang-local-bank/SKILL.md` 建立独立 Python 环境，在插件设置中填写其 Python 路径。

说明与更新：https://github.com/weishao2/tizhuang-agent-skills/tree/main/docs/local-bank
