# 交接：问答闭环现状核实（2026-10-22 23:10）

供主讲层（Codex）根据**真实代码**设计学员修改任务。本轮只做核实、运行与记录，未新增功能、未新增框架、未新建学习脚本、未改提示词。

---

## 1. 当前准确运行方法

前置：Ollama 服务必须在跑，且能列出两个模型。

```powershell
# 查服务是否正常（应看到 bge-m3 与 qwen3）
curl -s --noproxy '*' http://127.0.0.1:11434/api/tags

cd C:\Users\21511\Desktop\personal-ai-kb
.venv\Scripts\python.exe scripts\ask_demo.py "你的问题"                 # 向量检索（默认）
.venv\Scripts\python.exe scripts\ask_demo.py "你的问题" --mode keyword # 关键词检索
.venv\Scripts\python.exe scripts\ask_demo.py "你的问题" --top-k 2      # 候选条数
```

**已知环境坑（本轮又踩到一次）**：Ollama 托盘版（`ollama app.exe`）会自启并占用 11434，它读的是空模型目录 → `/api/tags` 返回 `{"models":[]}` → `/api/embed` 报 **404**。
本轮处理：结束托盘及其拉起的 `ollama.exe`，直接 `ollama.exe serve`（不带任何命令行覆盖），`/api/tags` 正常列出 bge-m3（1.16GB）+ qwen3:4b。
→ 用户级 `OLLAMA_MODELS = D:\OllamaModels` **对新进程确实生效**；托盘正常退出后重开即可，不需要注销、不需要换端口。

---

## 2. 函数调用关系（问题 → 检索 → 上下文 → 模型请求 → 回答与来源）

```
main()                      scripts/ask_demo.py L65
 ├─ load_corpus()           app/services/retriever.py L28     读磁盘上已落盘的片段（10 条）
 ├─ vector_search()         app/services/retriever.py L130    默认；--mode keyword 走 L85
 │   ├─ embed_texts()       app/services/embedder.py L42      /api/embed，模型 bge-m3
 │   ├─ cosine_similarity() app/services/retriever.py L104
 │   └─ _to_candidates()    app/services/retriever.py L56     排序、取名次、装成 Candidate
 ├─ _build_prompt()         scripts/ask_demo.py L55           ⚠️ 拼上下文（问题没进来，见第 5 节）
 ├─ generate()              app/services/generator.py L33     /api/chat，模型 qwen3:4b
 └─ print                   scripts/ask_demo.py L114-117     回答 + token + 耗时
```

- 候选**来源标识**在 `ask_demo.py` L94–97 打印（`[文件名#第几块]` + 文档 id + 原文前 80 字），模型看到的原文也会原样打印（L90 提示语）。
- 系统提示词在 `ask_demo.py` L49–52。
- 配置：`app/core/config.py` —— `llm_model = qwen3:4b`（聊天）、`embed_model = bge-m3`（嵌入），两者分开，互不混用。

---

## 3. 关键代码定位标记（本轮核实）

| 文件 | 行 | 内容 |
|---|---|---|
| `app/services/retriever.py` | L28 | `load_corpus()` |
| | L56 | `_to_candidates()` 排序取名次 |
| | L85 | `keyword_search()` |
| | L104 | `cosine_similarity()` |
| | L130 | `vector_search()` |
| `app/services/embedder.py` | L42 | `embed_texts()`（L116 `embed_one()`） |
| `app/services/generator.py` | L33 | `generate()`，返回 `(回答, token, 秒)` |
| `scripts/ask_demo.py` | L49 | `SYSTEM_TEXT` |
| | L55 | `_build_prompt(candidates)` ⚠️ |
| | L78 / L85 / L87 | 载入语料 / 两种检索 |
| | L101 | `prompt = _build_prompt(candidates)` ⚠️ 调用点，未传问题 |
| | L108 | `generate(prompt, system_text=SYSTEM_TEXT)` |
| | L114–117 | 打印回答 |

---

## 4. 两个案例（**本轮实测**，不是报告记载）

服务已确认正常（tags 列出 bge-m3 + qwen3），两次调用均真实执行。

**案例 A —— 资料里应该有答案**
```
问题 = 这个项目现在是什么版本？
检索方式 = vector / 候选 3 条 / 库里 10 个片段
候选：readme.md#0（0.45 量级）… readme.md#4（0.4544）名次 3 …
回答 = 资料里没有
（输出 token 869 / 服务端总计 16.6 秒）
```
资料里**确实有答案**：单独核实，`readme.md` 有 3 个片段含 `v0.1.0`（#0、#4、#5，其中 #5 原文即 `**v0.1.0**`）。
→ **这是一个失败案例**：资料里有、检索也返回了候选，模型却答「资料里没有」。

**案例 B —— 资料里没有答案**
```
问题 = 我的显卡型号是什么？
候选：readme.md#0、笔记.md#0（0.4527，名次 2、3）…
回答 = 资料里没有
（输出 token 894 / 服务端总计 13.17 秒）
```
→ 结论正确，但**不能当作"模型会拒答"的证据**（原因见下）。

---

## 5. 当前仍缺的连接 / 明显错误

**①【本轮实测 + 代码核实，首要】问题文本没有进入发给模型的 prompt。**

`scripts/ask_demo.py`：

```python
def _build_prompt(candidates) -> str:          # L55  只接收候选，没有 question 参数
    lines = ["下面是检索出来的资料片段，每条开头的方括号是它的来源：", ""]
    for c in candidates:
        lines.append(f"[{c.filename}#{c.chunk_index}] {c.text.strip()}")
    lines.append("")
    lines.append("请只根据以上资料回答问题。")     # L61  到这里结束，问题从未拼进去
    return "\n".join(lines)
...
prompt = _build_prompt(candidates)              # L101 调用点也没传问题
```

模型收到的只有「资料片段 + 请只根据以上资料回答问题」——**没有被问的是什么**。所以案例 A 和案例 B 都答「资料里没有」是必然结果，跟资料够不够无关。

这也解释了 10.21 报告里那次「切分是怎么做的？」→「资料里没有」的观察：当时记录为观察，未定位原因，**本轮找到原因**。

**②【报告记载，未在本轮处理】** `think: false` 在 Ollama 0.40.6 + qwen3:4b 下未关闭思考 —— 按指示保留，不排查。

**③【本轮复现】** 资料无答案时，向量检索仍返回候选（案例 B 三条候选分数 0.45 上下）→ 「高分 ≠ 有答案」再次成立。

**④【结构缺口】** 回答本身**不携带来源**：脚本打印了"给了模型哪些片段"，但模型的回答里没有"我依据哪一条"。引用溯源目前只做到前半程（展示输入），没做到后半程（回答指回来源）。

---

## 6. 给主讲层的建议（不自行决定，供你裁定）

最合适的一处学员修改任务，按真实代码看是 **①**：

- 位置：`scripts/ask_demo.py` L55（函数签名加 `question` 参数）、L61 后（追加一行把问题写进 prompt）、L101（调用点传入 `args.question`）
- 体量：约 3 行
- 可观察：修好后重跑「这个项目现在是什么版本？」，案例 A 应能答出 `v0.1.0`；案例 B 应仍答「资料里没有」。两个案例一正一反，正好验证。

是否布置、怎么讲，由你定。我只负责在你定完后协助核实与运行。

---

## 7. Git 改动整理（独立维护事项，**本轮未提交、未推送**）

当前工作区共 23 项改动、16 项未入库，最新提交仍 `599c3bc`（10.15）。

| 范围 | 内容 | 建议 |
|---|---|---|
| A. 检索能力（10.21–10.22 本轮工作） | 新增 `app/models/retrieval.py`、`app/services/embedder.py`、`retriever.py`、`generator.py`、`tests/test_retrieval.py`、`scripts/ask_demo.py`、`scripts/retrieve_demo.py`；改动 `app/core/config.py`（加 `embed_model`）、`requirements.txt`（加 `requests`） | 可单独一批，语义完整 |
| B. 学员自有改动 | `readme.md`（项目笔记）、根目录草稿脚本移入 `learning/` | 归学员自己 |
| C. 未入库目录 | `learning/`（9 个教学草稿）、`reports/`（交接与日报）、`scripts/`（整目录） | 是否入库由学员决定；`reports/` 属过程文档，可考虑 `.gitignore` |

建议：**先 A 后 B**，C 单独决定。不以提交次数评价学习，也不整库 `git add .` 或推送。执行前需学员确认范围。

---

## 8. 其它按你的第 4 条执行

- 算法：维持周日约 3 小时，不另加 5 小时预算。
- 不要求补做旧的「改端口」练习；不自行启动 Python 基线考试。
- 学员本轮未参与（未布置任何操作），学习时长：**未知**。
