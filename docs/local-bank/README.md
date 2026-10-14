# 题庄本地题库 · 教师版

把自己的题目留在本地，用 Agent 存题、分类、检索和组卷；也可以在 Obsidian 中点击操作。

**[老师图文使用说明 · 从拿到包到生成 Word](USER_GUIDE.md)**

8 张界面演示截图，按实际操作顺序讲安装、打开题库、网站取题、PDF 导入、知识点 / 标签分类和可视化组卷；另附可复制的 Agent 指令与常见问题。下载包内双击 **先看这里.html**，不用联网也能看，截图可放大。

## 一句话安装

把下面这句话发给你的 Agent：

> 请按 https://raw.githubusercontent.com/weishao2/tizhuang-agent-skills/main/docs/local-bank/INSTALL.md 帮我安装题庄本地题库。先检查已有题库、插件和新 skill；没装就安装，旧版就更新，相同或更新版本就跳过。保留我的题目和配置，旧 question-bank skill 不动。

已知题库路径时附上路径即可。Agent 会识别已有安装、检查版本、配置需要的独立 Python 环境。只有多个题库或原环境异常等不确定情况才需要选择。首次使用仍需在 Obsidian 中允许并启用插件；更新后重载插件，新 skill 安装后新开 Agent 会话。

**[下载完整起步包 2.4.3](../../downloads/local-bank/v2.4.3/tizhuang-local-bank-starter-v2.4.3.zip)** · **[Agent 安装流程](INSTALL.md)**

包内为：空白题库、插件 0.13.1、新 skill 2.4.3、安装器和离线图文说明。不包含用户题目、PDF、知识树、账号或凭证；说明截图展示网站实际获取的带图数学题，不会导入你的题库。[校验值](../../downloads/local-bank/v2.4.3/SHA256SUMS.txt)。

## 已经安装过

- 版本较旧：先备份，再更新程序文件。
- 同版完整或已是更新版本：跳过，不降级。
- 同版缺文件：补齐；有自定义程序修改时保留并提示。
- 已有题库：忽略空白模板，保留题目、图片、试卷、首页、索引和配置。
- 只需要某个组件：可以只装插件或只装新 skill。

安装器复用有效的原 Python 路径；没有路径时补入独立环境路径，其他设置原值保留。无效的原路径会报告需要处理，不擅自替换。旧 `question-bank` 的代码和环境不在安装范围。写入失败会回退替换的程序文件，备份路径随安装结果提供。

## 可以做什么

- **网站取题**：按章节或知识点选题，使用自己的题庄凭证和题目额度，预览后存本地。
- **分类浏览**：知识点树、教材章节、原生标签，一题一份正文，可关联多个考点。
- **PDF 导入**：准备原页后，由 Agent 提取可编辑文字、LaTeX、独立配图和原答案，导入后待核对。
- **自动分类**：明确考点标签匹配到唯一节点；不确定的交给 Agent，未知教材不猜章节。
- **组卷**：勾题、调序、设置分值，生成无答案 Word、教师答案 Word 和 HTML 打印稿。

本地保存、检索和组卷不扣网站题目额度。网站取题按网站规则扣额；新插件目录按账号“学段 × 学科”范围计数，默认 5 个，同范围重复使用不重复开通，管理员可增加。旧公开目录接口目前仍保留。

## 给 Agent 的日常指令

> 使用 tizhuang-local-bank，把这份 PDF 导入“我的题库路径”。逐页核对，保留文字、公式、独立配图与原答案；只分知识点，教材暂不选。

> 从本地找 10 道已核对的一次函数题，基础题在前，每题 5 分，生成无答案 Word 和教师答案版。

原答案缺失时保持缺失；正式发卷前老师核对题干、答案和图片。Word 的修改不自动回写题库。避免 Agent 与插件同时写同一题库。

## 同仓库，独立工具

| 工具 | 负责什么 | 安装关系 |
| --- | --- | --- |
| 原 `question-bank` | 网站真题检索、练习、网站组卷 | 独立安装，原文件不改 |
| 新 `tizhuang-local-bank` | 本地存题、PDF、分类、检索、Word 组卷 | 不依赖旧 skill |
| Obsidian 插件 | 本地题库可视化入口，直接从网站取题 | 不依赖任何已安装 skill |
| 未来视频 skill | 将选定题目制成讲解视频 | 尚未实现；可通过题目包协作 |

共用仓库便于统一入口和维护，不要求一起安装。各自独立目录、版本和更新规则；本地题不够不会自动触发扣额取题。详细约定见 [家族关系](../../skills/tizhuang-local-bank/references/family.md)。

## 开发与验证

- 新 skill 源码：`skills/tizhuang-local-bank`；安装器只依赖 Python 标准库。
- 安装测试依赖：`python -m pip install -r tests/local-bank/requirements.txt`。
- Python 测试：`python -m unittest discover -s tests/local-bank -v`。
- 插件：在 `plugins/obsidian` 运行 `npm ci`、`npm test`。
- 打包：构建插件后，在仓库根目录运行 `python tools/build-local-bank-release.py`，同时生成离线说明并校验 8 张配图。
- 图文源稿：`docs/local-bank/USER_GUIDE.md`；单独构建离线说明：`python tools/build_local_bank_guide.py`。
- 截图来源：实际插件组件 + 经授权获取的网站真题；离线截图过程不连接网站或读取私人题库。脚本为 `tools/capture-local-bank-guide.mjs`，需 Playwright、marked 及可用浏览器；可用 `TZ_GUIDE_EXAMPLES` 提供脱敏的演示数据，不指定时使用自编占位数据。原始接口结果不随包分发，截图记录见 `screenshots/capture.json`。

2.4.3 新增老师图文说明及离线入口；保留 2.4.2 的自动安装 / 更新流程。插件仍为已修复空作答框公式转换问题的 0.13.1。
