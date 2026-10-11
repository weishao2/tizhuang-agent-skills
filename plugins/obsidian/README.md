# 题庄本地题库 · Obsidian 插件 0.13.1

面向电脑备课的老师。全中文界面，顶部入口为：首页、网站取题、我的题目、组卷篮、PDF 导入。

**[下载与完整使用说明](https://github.com/weishao2/tizhuang-agent-skills/tree/main/docs/local-bank)**

## 安装与更新

初始包已把插件放入空白题库的 `.obsidian/plugins/tizhuang-question-bank`。在 Obsidian 中打开“题庄本地题库”文件夹，允许第三方插件并启用“题庄本地题库”，然后打开“题库首页”。尚未上架 Obsidian 社区市场。

已有题库可以忽略空白库。关闭插件，将包内同名插件目录的程序文件复制到自己的题库，保留原来的 `data.json`，再重新启用。不要覆盖自己的题目、`.bank` 或其他 Obsidian 配置。

普通本地浏览、网站取题不需要 Python。PDF 准备、自动分类和 Word 组卷需要 Python 3.10+ 与 `helper/requirements.txt` 的依赖。初始包内的 Windows 配置脚本会创建独立环境；已有题库在插件设置中指定该 Python 路径。macOS/Linux 用户可自行创建虚拟环境并安装同一依赖文件。

插件自带本地 helper，不要求安装任何 Agent skill。要通过 Agent 操作同一题库，可以独立安装 `tizhuang-local-bank`；旧 `question-bank` 不受影响。

## 主要功能

- 网站取题：学科、学段必选，章节与知识点可二选一，也可都不选；记住筛选与未保存结果。使用自己的题庄凭证与题目额度。
- 本地浏览：按知识点树、教材章节、原生标签、题型、审核状态和文字筛选；图片与题目保存在本地。
- 自动分类：将明确考点标签匹配到唯一的本地知识节点，不确定的生成 Agent 待办。未知教材不猜章节。
- PDF 导入：保留原页供 Agent 核对，提取可编辑文字、公式及独立配图；不内置远程视觉模型，导入题先为待核对。
- 可视化组卷：勾题、调整题序和分值，生成无答案 DOCX、教师答案 DOCX 和 HTML 打印稿。Word 修改不会自动回写题库。

网站题目按实际接口规则扣额度；保存、本地检索和组卷不重复扣题目额度。新插件的目录按账号“学段 × 学科”范围计数，默认 5 个，同范围重复使用不重新开通；管理员可增加。

有原答案时保留原答案，缺失时明确标注。正式发卷前由老师核对题干、公式、图片及答案。Agent 与插件共用 `tizhuang.bank/v1` 数据格式，请避免同时写入同一题库。

## 凭证与恢复

凭证在插件设置中配置，支持的 Obsidian 版本使用密钥存储，其他版本只在当前运行期间使用。插件配置保存引用，不把凭证放进题目文件或发行包。不要公开分享个人应用配置。

网站请求超时后不会自动重试扣额取题；先刷新额度确认结果。已收到的题目在本地暂存，重新打开后可继续保存。保存失败可重试，本地去重不会退还已经消耗的取题额度。

组卷失败保留组卷篮；同一请求重试复用已经生成的输出。修改题序、分值或设置后生成新版本。

## 本版修复

0.13.1 修复判断题空作答框被误识别为 LaTeX 而导致组卷失败的问题，保留 Word 中的作答空白。真实公式错误会提示题序与题干、答案或解析位置。

## 开发

从仓库根目录安装 `tests/local-bank/requirements.txt` 中的 Python 测试依赖；在 `plugins/obsidian` 运行 `npm ci`、`npm test`。需要指定 Python 时设置环境变量 `TIZHUANG_TEST_PYTHON`。

构建输出为 `dist/tizhuang-question-bank/`，helper 从 `skills/tizhuang-local-bank/scripts` 复制。仓库根目录运行 `python tools/build-local-bank-release.py` 生成唯一的空白起步包。依赖许可证位于 `third-party-licenses`。
