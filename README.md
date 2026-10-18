# 题庄技能

题庄的两个免费 Agent 技能，各自独立安装、独立更新。本仓库只是目录，详细介绍、安装和教程在各技能的文档里。

[官网](https://tizhuang.qcscience.cc/) · [在线组卷](https://tizhuang.qcscience.cc/builder) · [价格与合作](https://tizhuang.qcscience.cc/pricing)

| 技能 | 一句话 | 版本 | 更新时间 | 文档 |
| --- | --- | --- | --- | --- |
| **题庄在线题库**<br />`question-bank` | 说出教材、章节和难度，让 Agent 从题庄真题库里找题。 | 1.0.3 | 2026-10-18 | [介绍与安装](docs/question-bank/README.md) · [官网](https://tizhuang.qcscience.cc/skills/question-bank) |
| **题庄本地题库**<br />`tizhuang-local-bank` | 把网站好题和自己的 PDF 存进本地题库，组卷导出 Word。 | 2.5.1<br /><sub>插件 0.14.1</sub> | 2026-10-17 | [介绍与安装](docs/local-bank/README.md) · [官网](https://tizhuang.qcscience.cc/skills/tizhuang-local-bank) |

## 安装

**在线题库**

```bash
npx skills add weishao2/tizhuang-agent-skills --skill question-bank
```

**本地题库**：把下面这句话发给能读写本地文件的 Agent。

> 请按 https://tizhuang.qcscience.cc/local-bank/INSTALL.md 帮我安装题庄本地题库。先检查已有题库、插件和新 skill；没装就安装，旧版就更新，同版或更新版本就跳过。保留我的题目、图片、试卷和全部原配置，旧 question-bank skill 不动。安装后运行环境体检。

## 目录

```text
skills/question-bank/          在线题库 Skill
skills/tizhuang-local-bank/    本地题库 Skill
plugins/obsidian/              本地题库的 Obsidian 插件
docs/question-bank/            在线题库文档
docs/local-bank/               本地题库文档与更新记录
downloads/local-bank/          本地题库起步包
```

## License

Skill 适配器源码使用 MIT License；ClawHub 上架版本按该平台要求以 MIT-0 发布。题库内容及在线服务适用各自的服务规则。
