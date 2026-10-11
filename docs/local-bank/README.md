# 题庄本地题库 · 教师版

把自己的题目留在本地，用 Agent 存题、分类、检索和组卷；也可以在 Obsidian 中点击操作。

这是 `tizhuang-local-bank` 的首次公开发行，包含 skill 2.4.1 与 Obsidian 插件 0.13.1。它独立于原来的 `question-bank`，可以分别安装、升级和卸载。

## 一个包开始使用

**[下载完整起步包](../../downloads/local-bank/v2.4.1/tizhuang-local-bank-starter-v2.4.1.zip)**：空白题库、Obsidian 插件、新 skill、中文说明及 Windows 环境配置脚本。

进入文件页面后点击下载按钮。已有题库的人可以忽略空白库，只更新需要的插件或新 skill；旧 `question-bank` 不受影响。包内没有测试题、他人的 PDF、API Key、下载过的知识树或账号配置。校验值见 [SHA256SUMS.txt](../../downloads/local-bank/v2.4.1/SHA256SUMS.txt)。

## 第一次使用

1. 下载并解压初始体验包。
2. 用 [Obsidian](https://obsidian.md/download) 的“打开文件夹作为仓库”，选择解压后的 **题庄本地题库**。
3. 在 Obsidian 设置 → 第三方插件中允许使用插件，找到并启用 **题庄本地题库**。插件尚未上架社区市场，包内已放好文件。
4. 打开 **题库首页**，点击“打开题库工作台”。已有的本地题目也可从“我的题目”浏览。
5. 要导入 PDF、通过 Agent 操作或导出 Word，先装 Python 3.10+，再运行包内的 `安装本地环境.ps1`。它只在解压目录建立独立环境，并将该 Python 路径写入此题库的插件设置；不会替换旧 skill。
6. 安装新 skill：把包内 `skills/tizhuang-local-bank` 复制到你的 Agent 的 skills 目录。Codex 可使用 `~/.codex/skills/tizhuang-local-bank`；其他 Agent 按自身安装说明选择位置。安装后新开会话。

也可以把安装包交给 Agent：

> 安装包内的 tizhuang-local-bank，并为它配置独立 Python 环境。不要覆盖 question-bank。我的 Obsidian 仓库是“这里填写题庄本地题库的实际路径”。

Windows 配置脚本也可在 PowerShell 中运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\安装本地环境.ps1
```

脚本会下载 Python 依赖，需要联网。移动整个解压目录后，重新运行它更新路径。macOS/Linux 用户可按 [独立 skill 说明](../../skills/tizhuang-local-bank/SKILL.md) 建立 Python 虚拟环境，再在插件设置中指定该环境的 Python 路径。

## 能做什么

- **网站取题**：按教材章节或知识点选题，使用自己的题庄 API Key 和题目额度，预览后保存到本地。
- **本地整理**：知识点树与标签都可使用，一道题保留一份正文，多知识点可关联。
- **PDF 导入**：准备原页后，由 Agent 核对并提取可编辑文字、LaTeX 与独立配图。导入题先待核对，不承诺无人审核识别准确。
- **自动分类**：插件先把明确标签匹配到唯一知识节点，不能确定的交给 Agent 判断。教材版本未知时不猜章节。
- **组卷**：勾题、调序、设置分值，通过插件或 Agent 输出无答案 Word、教师答案 Word 和对应 HTML 打印稿。
- **本地保存**：Markdown 与附件可备份、移动和编辑。Word 的修改不自动回写题库。

本地保存、已有题目检索和组卷不扣网站题目额度。网站取题仍按网站实际额度规则计数。新插件下载目录按账号的“学段 × 学科”范围额度管理，默认 5 个，同范围重复使用不再次开通；管理员可增加。旧公开目录接口目前仍保留，这个限制并不覆盖全部旧调用方式。

## 给 Agent 的示例指令

> 使用 tizhuang-local-bank，在“我的题库路径”初始化教师题库。

> 把这份 PDF 分题导入。逐页核对，保留文字、公式、独立配图和原答案，只按知识点分类，暂时不选教材。

> 从我的本地题库找 10 道已核对的一次函数题，基础题在前，每题 5 分，生成无答案 Word 和教师答案版。

原答案缺失时保持缺失；正式组卷前老师核对题干、答案与图片。不要让 Agent 和插件同时写入同一题库。

## 和其他题庄工具的关系

| 工具 | 负责什么 | 安装关系 |
| --- | --- | --- |
| 原 `question-bank` | 在线真题检索、在线练习与网站组卷 | 独立安装，原有文件不变 |
| 新 `tizhuang-local-bank` | 教师本地存题、PDF 入库、分类、检索、Word 组卷 | 不要求安装旧 skill |
| Obsidian 插件 | 上述本地库的可视化入口，并直接向网站取题 | 不调用旧 skill，也不要求先安装新 skill |
| 未来视频 skill | 接收选定题目制作讲解视频 | 尚未实现；计划通过题目包配合 |

它们共用品牌和题目文件协议，由 Agent 按任务选择。在线找新题时可选用旧 skill，将结果导入本地；本地题目不足不会自动触发扣额取题。详细约定见 [家族关系](../../skills/tizhuang-local-bank/references/family.md)。

## 数据与升级

题库首页、题目库、试卷、待整理、教学笔记、资料，是老师使用的目录。`.bank` 保存必要索引与来源，`.obsidian` 保存插件；备份个人题库时应保留隐藏目录。不要把自己的 `.obsidian` 配置、凭证或整个个人题库当安装包公开上传。

更新 skill 只更新 `tizhuang-local-bank`，保留已安装目录里的独立 Python 环境；插件程序在包内 `题庄本地题库/.obsidian/plugins/tizhuang-question-bank`。关闭插件，将这里的程序文件复制到自己的仓库中同名插件目录，保留自己的 `data.json`，然后重新启用。空白题库可以忽略，不要用初始包覆盖已有题库。

## 开发与验证

- 新 skill 源码：`skills/tizhuang-local-bank`。
- 插件源码：`plugins/obsidian`；运行 `npm ci`、`npm run build`，helper 从新 skill 源目录复制。
- 新 skill 测试：先运行 `python -m pip install -r tests/local-bank/requirements.txt`，再运行 `python -m unittest discover -s tests/local-bank -v`。额外的 ReportLab 仅用于生成自编测试样卷，不是用户安装依赖。
- 打包：插件构建后运行 `python tools/build-local-bank-release.py`。

本次修复已通过 46 项本地引擎测试及 51 项插件测试，包括空判断框、Word 原生公式、无答案版答案隔离和失败重试。复杂公式、合并单元格等不支持的情况会明确报错，发放前仍需老师核对。
