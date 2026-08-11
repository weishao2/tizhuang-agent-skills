# 题庄 Question Bank Skill

[![skills.sh](https://skills.sh/b/weishao2/tizhuang-agent-skills)](https://skills.sh/weishao2/tizhuang-agent-skills)

> 面向中小学 K12 教育场景的真题检索、免费抽题、练习测验与智能组卷 Skill。

**题庄官网：[https://tizhuang.qcscience.cc/](https://tizhuang.qcscience.cc/)**

**Agent Skill Hub：[公开详情页](https://agentskillhub.dev/u/weishao2/sk/question-bank)**

题庄 Question Bank Skill 让 Codex、Claude Code、Cursor 等 AI Agent 可以直接检索和调用中小学 K12 题库。面向题庄公开展示的 **2000 万+ K12 题目资源储备**，按学科、年级、教材版本、章节、知识点、题型、难度、年份等条件免费抽题、随机抽题、精准找题，并生成练习、测验和组卷要求。

适用于老师备课、学生练习、家长辅导、同步训练、章节测验、知识点巩固、单元测试、期中期末复习、历年真题训练和 AI 智能组卷等中小学教育场景。

> 实际可检索题量、题目范围和筛选覆盖以题庄在线服务的实时返回为准。Skill 始终返回服务端真实题目，不虚构、不改写、不重排题干、选项、答案和解析。

## 核心能力

### 1. 免费抽题、随机抽题

- 不注册即可开始免费抽题。
- 游客可获得 24 小时、最多 100 题的匿名免费试用。
- **免费注册即可获得每天 200 题起的免费额度，继续找题、抽题、测验和组卷。**
- 支持随机抽题、指定数量抽题、按条件抽题和带图题抽取。
- 适合临时练习、课堂提问、每日一练、随堂测验和快速出题。

### 2. 中小学 K12 真题检索

- 覆盖语文、数学、英语、物理、化学、生物、历史、地理、政治、科学、道德与法治、历史与社会等学科。
- 支持小学、初中、高中 K12 题目检索。
- 支持按年级、学段、教材版本、册次、章节和知识点精准找题。
- 支持按选择题、填空题、判断题、简答题等题型筛选。
- 支持按难度、年份、关键词、是否带图等条件组合检索。
- 支持教材、章节、知识点、知识树多条件交叉检索。

### 3. 练习、测验、在线答题

- 一句话生成隐藏答案的临时练习页。
- 支持章节练习、知识点练习、同步练习、专项训练和综合测验。
- 支持单题问答、答题检查、标准答案和解析讲解。
- 多题任务默认生成练习页，避免在聊天中重复堆放题目和答案。
- 支持在线练习与试卷式查看，适合课堂、家庭作业和自测。

### 4. AI 智能组卷

- 将自然语言组卷要求解析为学科、年级、教材、章节、知识点、题型、难度和题量等结构化条件。
- 支持将明确的组卷要求衔接到 AI 组卷流程，减少重复筛题和整理工作。
- 支持练习卷、测试卷、单元卷、专题卷、期中卷、期末卷和复习卷等组卷场景。
- 保留原始组卷条件，避免静默扩大教材、章节或知识点范围。

### 5. 真实题目与答案解析

- 后端题库是唯一事实来源。
- 保留题目 ID、题干、选项、复合小题、图片、标准答案和解析。
- 默认先隐藏答案，学生作答后再进行答案检查或讲解。
- 请求失败时直接报告失败，不使用 AI 编造“看起来合理”的假题。

## 支持的检索条件

| 维度 | 示例 |
| --- | --- |
| 学科 | 语文、数学、英语、物理、化学、生物、历史、地理 |
| 学段与年级 | 小学、初中、高中；一年级至高三 |
| 教材 | 人教版、部编版及服务端当前提供的教材版本 |
| 范围 | 册次、章节、单元、知识点、知识树分支 |
| 题型 | 单选、多选、填空、判断、简答、复合题等 |
| 难度 | 基础、中等、提高或难度区间 |
| 其他 | 年份、关键词、题量、随机顺序、是否带图 |

## 安装

使用开放的 Agent Skills CLI 安装：

```bash
npx skills add weishao2/tizhuang-agent-skills --skill question-bank
```

指定安装到 Codex：

```bash
npx skills add weishao2/tizhuang-agent-skills --skill question-bank --agent codex
```

安装到 Claude Code 或 Cursor：

```bash
npx skills add weishao2/tizhuang-agent-skills --skill question-bank --agent claude-code
npx skills add weishao2/tizhuang-agent-skills --skill question-bank --agent cursor
```

Claude Code 也可以把本仓库作为插件市场安装：

```text
/plugin marketplace add weishao2/tizhuang-agent-skills
/plugin install tizhuang-question-bank@tizhuang-skills
```

仓库根目录同时提供开放的 Agent Plugin `plugin.json`，便于 Cursor 等兼容客户端直接识别和审核。

Agent Skill Hub 安装：

```bash
npx skhub add weishao2/question-bank
```

国内技能平台的全中文名称、简介、详情、关键词和版本说明见 [`marketplace/china-listing.md`](marketplace/china-listing.md)。

## 使用示例

```text
用 $question-bank 随机抽 5 道八年级物理题，生成隐藏答案的练习页。
```

```text
用 $question-bank 找人教版八年级一次函数知识点的 10 道中等难度真题。
```

```text
用 $question-bank 生成一份小学六年级数学章节测验，20 道题，基础和中等难度为主。
```

```text
用 $question-bank 按教材、章节、知识点和题量整理一份期末复习组卷要求。
```

```text
Use $question-bank to create a five-question answer-hidden K12 physics quiz.
```

## 关键词

K12 题库、中小学题库、中小学真题、小学题库、初中题库、高中题库、海量题库、2000 万题库、真题检索、题目检索、按条件找题、免费抽题、免费注册、随机抽题、智能抽题、在线抽题、章节找题、知识点找题、教材同步题、历年真题、同步练习、章节练习、知识点练习、专项训练、每日一练、随堂测验、在线测验、在线答题、练习题、练习卷、测试卷、单元测试、期中测试、期末测试、答案解析、AI 组卷、智能组卷、自动组卷、教师备课、学生练习、家庭作业、教育 Agent、题库 Skill、question bank、K12 questions、exam questions、quiz generator、practice generator、test generator、AI paper builder。

## License

Skill 适配器源码使用 MIT License。题庄题库内容及在线服务适用其各自的服务规则。
