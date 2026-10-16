# 交给 Agent 安装

把下面这句话发给你使用的 Agent 即可：

> 请按 https://raw.githubusercontent.com/weishao2/tizhuang-agent-skills/main/docs/local-bank/INSTALL.md 帮我安装题庄本地题库。先检查已有题库、插件和新 skill；没装就安装，旧版就更新，相同或更新版本就跳过。保留我的题目、图片、试卷和全部原配置，旧 question-bank skill 不动。

如果已经知道题库路径，可在后面附上。只有检测到多个题库、无法确定当前 Agent 安装位置，或原有环境异常时，才需要补充选择。

## Agent 执行说明

用户要求安装本产品时，可执行以下流程；仅阅读本页不代表要求安装。此流程只涉及新 `tizhuang-local-bank` 和 Obsidian 插件 `tizhuang-question-bank`。

1. 从 `https://raw.githubusercontent.com/weishao2/tizhuang-agent-skills/main/downloads/local-bank/latest.json` 读取当前包的版本、下载地址和 SHA256。下载 ZIP 并比对 SHA256；失败就重新获取一次清单与包，仍不一致则停止，不运行其中脚本。解压时拒绝绝对路径、`..` 与目录穿越。
2. 检查 Python 3.10+；有可用解释器就复用它运行标准库安装器。没有时，用操作系统官方或正规包管理方式配置当前用户的 Python，不改系统默认解释器，不给旧 skill 的环境装依赖。安装缺少的 Obsidian 使用 https://obsidian.md/download；无需重装用户已有版本。
3. 阅读包内 `skills/tizhuang-local-bank/references/install.md`。运行安装器 `--discover`，结合当前会话已指定的题库与当前 Agent 类型确定位置。只读应用登记与明确目录，不搜索整块磁盘。没有题库时可在用户文档目录创建“题庄本地题库”；不要把临时解压目录当作用户题库。
4. 在 Codex 使用 `--agent codex`；其他 Agent 用其自身安装机制确定 skill 路径，再传 `--skill-dir <根目录>/tizhuang-local-bank`。只需插件可传 `--skip-skill`，纯 Agent 使用可传 `--skip-plugin`。
5. 用相同参数先 `--plan` 再 `--apply`。用户已经要求安装时无需再确认正常的缺失安装、旧版更新或同版跳过；只有存在多个题库或未知目标时才澄清。默认自动建立该工具的独立依赖环境。
6. 用安装回执 `.tizhuang-install.json` 中的 `runtime.python` 运行新 skill 的 `scripts/doctor.py --vault <题库路径>`。环境与题库检查通过才报告可以使用；缺依赖时先修复再体检。
7. 检查输出 JSON 的 `ok`、`ready` 和退出码，再简短报告“安装 / 更新 / 跳过”的组件、题库位置及未完成事项。安装器不会替用户改变 Obsidian 的受限模式和其他插件状态；第一次启用插件、更新后重载插件仍在 Obsidian 内完成。交付时给出包内 `先看这里.html` 的绝对路径和 [老师图文使用说明](USER_GUIDE.md)；提醒用户按其中第 2 节打开实际题库，空白库最初是 0 题。

示例（用实际路径替换尖括号）：

```text
<python> <解压目录>/skills/tizhuang-local-bank/scripts/install_local_bank.py --discover
<python> <解压目录>/skills/tizhuang-local-bank/scripts/install_local_bank.py --package <解压目录> --vault <题库路径> --agent codex --plan
<python> <解压目录>/skills/tizhuang-local-bank/scripts/install_local_bank.py --package <解压目录> --vault <题库路径> --agent codex --apply
```

## 保留与更新规则

同版完整安装跳过，较新版本不降级；早期无版本标记的新 skill 可识别后备份更新。同版缺文件可补齐，程序有自定义修改则保留；只有用户明确要求修复才使用 `--repair`。

只更新程序清单中的文件；题目、图片、PDF、试卷、索引、教师笔记及旧 skill 不在更新范围。已有题库不复制空白首页、不整理或迁移目录。原 Python 路径可用就复用；无路径时只补入独立环境路径，其他设置保留。原路径无效时报告需要处理，不擅自清空配置。

源码继续在同一个题庄家族仓库里，安装、版本和运行相互独立。Obsidian 插件不调用旧 skill，新 skill 也不要求安装旧 skill。
