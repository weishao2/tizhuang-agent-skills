# 题庄题库工作台 1.0.1 · 官方安装入口

更新时间：2026-11-09。官方主页：https://tizhuang.qcscience.cc/skills/tizhuang-studio

完整包：https://tizhuang.qcscience.cc/studio/tizhuang-studio-v1.0.1.zip
SHA-256：`31b3601e32ec3b721ce4096d9d44eefd1ffb5362fc0ff6fb346ba1817fd8aa21`
版本清单：https://tizhuang.qcscience.cc/studio/latest.json

下载完整 ZIP，核对 SHA-256，再解压到临时程序目录。包根目录是 `tizhuang-studio/`，请先读其中 `SKILL.md`。不要执行来历不明的同名包。

本版无需 Obsidian。程序安装到当前 Agent 的技能目录，题库工作区必须放在程序目录以外；旧 question-bank / tizhuang-local-bank 和旧题库保持原样。

# 题庄题库工作台：安装与更新

## 老师只需要做这一步

下载官方完整 ZIP，解压后把 `tizhuang-studio` 文件夹交给能操作本机文件的 Agent：

> 请安装这个题庄题库工作台。自动检查已有安装，未安装则安装，旧版更新，同版跳过；保留原题目和配置。请先问我把题库存在哪里，配置独立环境并体检，打开工作台。不要改我的旧 Obsidian 题库或其他技能。

如果已明确指定工作区，直接沿用，不重复询问。账号 Key 在页面“连接题庄”填写，不发到聊天里。

## Agent 执行步骤

1. 使用当前客户端认可的 Skill 安装路径，例如 Codex 的 `$HOME/.codex/skills/tizhuang-studio`。其他 Agent 使用各自技能目录，不假定所有客户端都读取同一路径。
2. 检查 Python 3.10+。Windows 可使用 `py -3`；没有时按 Python 官网安装。不要修改其他 Skill 的 Python 环境。
3. 在已解压包运行以下命令（路径替换成实际绝对路径）：

```powershell
py -3 scripts/install.py --target "$HOME/.codex/skills/tizhuang-studio" --workspace "D:/教学/我的题库"
```

安装器只使用标准库启动，依赖全部装进技能自己的 `.venv`。返回 `ok: true` 且 doctor 通过后才能汇报安装成功。

4. Windows 启动：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME/.codex/skills/tizhuang-studio/scripts/start.ps1" -Workspace "D:/教学/我的题库"
```

macOS/Linux 使用 `.venv/bin/python scripts/studio.py --workspace <目录> serve --port 4186`，仅监听 127.0.0.1。打开返回的本机地址。已有服务先验证并复用，不创建第二个组卷篮。

## 更新规则

- 完整包的 `scripts/install.py` 检查程序哈希：相同跳过，旧内容先备份再更新，较新版不降级。
- 备份在技能安装目录旁的 `tizhuang-studio-backup-*`；保留直到更新验证通过。
- 工作区放在技能目录外，不改其中 SQLite、题目、图片、PDF、试卷或配置。
- 更新了服务端程序时，先告知并保存当前工作，再由 Agent 识别本工作区的实际进程、停止并重新启动。不要根据端口猜测杀进程。页面输入的 Key 仅在服务内存中，重启需要重新连接。
- 更新后再次 doctor，并验证打开的工作区和更新前一致；服务端与网页共用同一个 state/revision。
- 旧 `question-bank` 和 `tizhuang-local-bank` 文件保持原样。旧 Obsidian 题库不会被自动转换；工作台备份恢复只接受工作台支持的格式，不把旧仓库冒充兼容备份。

## 常见问题

- 找不到 Python：安装 Python 3.10+ 后重新执行安装命令。
- 依赖下载失败：检查网络，再执行同一命令；不要删除题库。
- 页面打不开：让 Agent 运行 doctor、检查该工作区服务并重新启动。
- 已连接但刷新后失效：普通刷新不丢 Key，服务重启后需重新连接。
- PDF 上传后没有分题：上传仅准备原页，复制“交给 Agent 分题”的指令，让能够查看图片的 Agent 继续识别，最后由老师核对。
