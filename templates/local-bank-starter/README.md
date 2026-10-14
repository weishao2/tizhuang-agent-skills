# 题庄本地题库 · 起步包 2.4.3

空白题库 + 插件 0.13.1 + 新 skill 2.4.3。没有任何人的题目、PDF、目录、账号或凭证。

## 第一次使用，先看这里

**双击同目录的 [先看这里.html](先看这里.html)**，用浏览器离线阅读图文说明。8 张演示截图，覆盖从安装、打开题库，到网站取题、PDF 导入、分类和 Word 组卷；截图可放大，Agent 指令可一键复制。

也可阅读 [使用说明.md](使用说明.md)（配图在 `使用说明图片`）或 [在线图文说明](https://github.com/weishao2/tizhuang-agent-skills/blob/main/docs/local-bank/USER_GUIDE.md)。截图展示网站真实题目，空白库不预装题目，也不包含账号 Key。

## 交给 Agent 即可

把此文件或解压目录交给 Agent：

> 请阅读此包的 skills/tizhuang-local-bank/references/install.md，帮我安装题庄本地题库。检查已有题库、插件和新 skill，缺少就安装，旧版就更新，同版或较新版本就跳过。保留我的题目和配置，旧 question-bank 不动。

已有题库时附上路径。没有题库时 Agent 可在文档目录新建“题庄本地题库”。不要把临时解压目录当作你的长期题库。

Agent 将完成版本检查、程序安装和独立 Python 环境配置。Obsidian 第一次使用需要在“设置 → 第三方插件”中允许并启用“题庄本地题库”；更新后重载插件，新 skill 则新开 Agent 会话。

## 已有用户

空白库可忽略。安装器只替换程序清单里的文件，保留原题、图片、试卷、索引、首页、凭证引用和配置；更新前备份，失败回退。相同完整版本或更高版本跳过，同版缺文件补齐，自定义程序修改会保留并提示。只要插件或只要新 skill 都可以。

原 Python 路径有效就复用；缺少路径时配置独立环境；原路径无效时先报告，不擅自覆盖。安装器不修改旧 question-bank 或它的环境。

## 手动入口（可选）

有 Python 3.10+ 的 Windows 用户可在此文件夹的 PowerShell 中执行，替换下面的路径：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\安装本地环境.ps1 -VaultPath 'D:\我的题库' -SkillDirectory '你的Agent技能目录\tizhuang-local-bank'
```

脚本按版本安装或更新，支持 `-Plan` 只检查。只装插件可用 `-SkipSkill`。Codex 用户可用 `-Agent codex` 代替 `-SkillDirectory`。其他系统使用相同的 Python 安装器即可。

网站取题需要用户自己的凭证和额度；本地保存、检索与组卷不扣题目额度。PDF 由 Agent 提取并核对文字、公式和独立配图，正式发卷前由老师核对。

使用与更新：https://github.com/weishao2/tizhuang-agent-skills/tree/main/docs/local-bank
