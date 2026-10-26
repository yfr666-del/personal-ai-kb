# 交接：本地语义检索能力（增量，未重写项目）

日期：2026-10-21　执行：WorkBuddy（实机助教）　给：主讲层（ChatGPT）
后续：**等你按实际代码安排带读，我不自行排新课**

---

## 1. 实际修改的文件

**新增（4 个，全部是新文件，未改任何已有业务代码）**

| 文件 | 行数 | 职责 |
|---|---|---|
| `app/models/retrieval.py` | 43 | 两个 Pydantic 模型：`CorpusChunk`（库里的片段，带 doc_id / filename / chunk_index / global_index）、`Candidate`（检索返回的候选，带 rank / score / text） |
| `app/services/embedder.py` | 93 | 本地嵌入调用组件，只做一件事：调 Ollama `/api/embed` 拿向量 |
| `app/services/retriever.py` | 145 | 三个检索函数：`load_corpus()` / `keyword_search()` / `vector_search()`，外加 `cosine_similarity()` |
| `scripts/retrieve_demo.py` | 177 | 运行入口：5 个问题对照 + 4 个失败场景 + 聊天模型当嵌入的实证 |

**改动（2 处，都是加字段/加依赖，没动逻辑）**

- `app/core/config.py` L39：新增 `embed_model: str = "bge-m3"`（与 `llm_model` 分开两个配置项）
- `requirements.txt` L9：新增 `requests==2.34.2`（此前项目没显式依赖它）

**不属于本轮的改动**（`git status` 里能看到，说明一下免得混淆）：`readme.md` 的 3 行增删是学员自己的 M1 收尾（把根目录学习脚本移入 `learning/`）；`learning/` 下的文件移动也不是本轮做的。

---

## 2. 调用与数据流

```
磁盘 data/docs/  ──storage.load_chunks()──>  文本片段
                                                 │
                        load_corpus()            │  retriever.py L28
                                                 ▼
                                        CorpusChunk 列表（本次 10 条）
                                                 │
                    ┌────────────────────────────┴──────────────────────┐
                    ▼                                                   ▼
        keyword_search()                                    vector_search()
        retriever.py L85                                    retriever.py L124
        关键词：把问题切成 2 字组，              把每条片段 + 问题各自嵌入，
        数片段里命中几组，累加得分                      算余弦相似度
        （不调模型）                                        │
                    │                                       │ embed_texts()
                    │                                       ▼  embedder.py L42
                    │                            Ollama /api/embed（bge-m3）
                    └────────────────┬──────────────────────┘
                                     ▼
                              Candidate（rank / score / doc_id / filename /
                                        chunk_index / text）
```

**关键点**：本轮**只打通到"问题 → 候选资料"**，**没有接回答链路**。下一步要不要把候选喂给 `qwen3:4b`，等你定。

---

## 3. 嵌入模型及配置

| 项 | 值 |
|---|---|
| 模型 | **bge-m3**（Ollama library 官方，`ollama pull bge-m3`） |
| 落地位置 | `D:\OllamaModels`（沿用已有 `OLLAMA_MODELS` 环境变量） |
| 磁盘占用 | 1.2 GB（下载耗时 24 分 48 秒，尾部网络掉到 32–67 KB/s） |
| 实测向量维度 | **1024** |
| 实测向量模长 | **1.0**（已归一化 → 余弦相似度与点积等价） |
| 相似度方式 | 余弦（bge-m3 官方推荐） |
| 配置项 | `app/core/config.py` L39 `embed_model` |

**为什么不是 nomic-embed-text（274MB，更小）**：语料是中文 readme.md，bge-m3 官方标称 100+ 语言（XLM-RoBERTa 基座），中文 retrieval 明显更强；nomic 主攻英文。这个取舍你要是不同意，可以推翻。

**实证：聊天模型确实不能当嵌入模型**（这条我实跑验证了，不是凭感觉）
```
聊天模型：qwen3:4b / 嵌入模型：bge-m3
  HTTP 状态码：501
  {"error":"This server does not support embeddings. Start it with `--embeddings`"}
```
⚠️ 这个错误文案是**过时的**：照它说的加 `--embeddings`，Ollama 0.40.6 报 `unknown flag`（该标志已移除）。真实含义是"这个模型不支持嵌入"。

---

## 4. 运行入口

```powershell
cd C:\Users\21511\Desktop\personal-ai-kb
# 前置：Ollama 服务要在跑（托盘版读不到 D:\OllamaModels，见第 8 节）
.venv\Scripts\python.exe scripts\retrieve_demo.py
```

**给学员留的小操作**：改 `scripts\retrieve_demo.py` **L37–43** 的 `QUESTIONS` 列表（改问题或加一行），再跑一次看候选怎么变。**只是观察候选变化，不要求写任何组件代码。**

---

## 5. 关键词 vs 向量：真实对比（5 题，同批资料、同一问题）

资料：磁盘上真实的 10 个片段（readme.md 6 块 + demo.pdf 1 块 + 3 个同名"笔记.md"各 1 块）。
**说明：分数只用来看排序，不代表答案对不对。**

| 问题 / 要测什么 | 关键词检索结果 | 向量检索结果 | 观察 |
|---|---|---|---|
| `pytest`（字面匹配） | chunk0/1/2 **并列 5.0** | chunk2 第 1（0.5744） | 关键词三个平局分不出先后；向量把真正写 `pytest -v` 的 chunk2 排到了第 1 |
| `怎么跑测试`（换说法，资料里没有"跑测试"连续出现） | chunk1 / chunk2 **并列 2.0** | chunk2 第 1（0.6659） | 两者都把答案放进候选了；向量把分差拉开，关键词仍是平局 |
| `v0.1.0`（精确版本号，无语义） | chunk0/4/5 **并列 5.0**，含它的 chunk5 排第 3 | chunk5 第 1（0.6162） | **这一题向量明显更好**：关键词并列且把答案排到了第 3 |
| `文档元数据的校验规则写在哪个文件`（语义 + 精确路径，答案在 chunk3） | chunk0/2/3 **并列 6.0**，答案 chunk3 排第 3 | chunk2 第 1（0.5819），**答案 chunk3 第 2**（0.5586） | **两种都没把答案排到第一，但都把它放进了候选** |
| `我用的显卡型号是什么`（资料里没答案） | 3 个候选**全是 0.0 分** | chunk0 第 1（**0.5155**） | **两种都硬返回了候选**。向量最高分 0.5155 并不低 —— 印证了"高相似度 ≠ 有答案" |

**两点我不敢推广，只说本次样本**：
- 关键词的"并列平局"在 5 题里出现 4 次，是因为它按字数计分、粒度太粗。这是**本次这 10 条资料**上的观察。
- 第 4 题是唯一出现"正确资料进了候选但没排第一"的例子 —— 只有 1 次，**不足以支撑"引入重排"的结论**。按你的要求，我不自行扩展；要不要再攒样本判断，等你定。

---

## 6. 失败案例（4 项全部实跑通过）

| 场景 | 实际结果 |
|---|---|
| 空输入 | `ValueError：文本里有空内容，嵌入模型不支持空输入` |
| 向量维度不一致 | `ValueError：两个向量维度不一致：2 vs 3` |
| 服务不可用 | `EmbeddingUnavailableError：连不上本地嵌入服务：http://127.0.0.1:59999/api/embed`（不崩） |
| 空检索库 | 返回 0 个候选 |

额外处理：返回体里没有 `embeddings`、维度不一致、向量为空，也各自有对应报错。

---

## 7. 学员本人操作

**本轮学员没有动手。** 他只下发了任务，实现、运行、核查都是我做的。
→ 按你的要求，**这些组件不登记为学员独立掌握**。是否让他做上面第 4 节那个小操作，等你安排，我不主动布置。

---

## 8. 仍需帮助 / 已知问题

1. **Ollama 托盘版会顶坏环境**：学员之前开过桌面托盘版，它在设 `OLLAMA_MODELS` 之前就启动了，读的是空目录 → `/api/tags` 返回空、`/api/chat` 报 404。上午我 kill 掉托盘进程后脚本自拉的服务才正常。**建议告诉学员：短期内别重开托盘**（要开就先注销/重启一次让环境变量生效）。要不要让脚本换备用端口彻底避开，等你定。
2. **`requests` 默认走系统代理**，会把 `127.0.0.1` 的请求也送去代理，结果是"服务没起却报 502"的假象。已在 `embedder.py` L30–31 用 `Session()` + `trust_env = False` 修掉。**这条建议同步给学员**，他以后写本地 HTTP 调用会再遇到。
3. **检索组件尚未接入回答链路**：`qwen3:4b` 目前只在对比例子里出现过一次（证明它不能做嵌入）。下一步怎么接，等你。
4. 之前挂起的 `think: false` 未能关闭思考，仍按指示保留未解。
