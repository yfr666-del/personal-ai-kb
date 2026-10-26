# RAG 评估与混合检索 · 执行层交付报告

- 日期：2026-10-25
- 依据：`16_RAG评估与混合检索_执行层任务包.md`、`17_从现有代码学懂评估与混合检索.md`、工作区 `00_WorkBuddy先读_最新课程同步.md`
- 项目：`C:\Users\21511\Desktop\personal-ai-kb`
- 本次角色：主项目唯一写入负责人（执行层）。原理教学与审核由 Codex 负责。
- 环境：`.venv` Python 3.13.5；pytest 已装；**httpx 未装**；未安装任何新依赖、未拉新模型。

---

## 0. 一句话结论

A、C 两层已实跑通过（14 + 17 = 31 条新测试，全量 114 passed）；**B 层因缺 `httpx` 未能实跑，3 条测试明确 skipped，不伪装通过**。所有改动均未提交、未推送。

---

## 1. 实际改动清单

### 新增文件（4 个）

| 文件 | 说明 |
|---|---|
| `learning/evaluation/rag_cases_v1.json` | 三条公开演示资料 + E01/E02/E03 三个起步问题（样本基线，**不覆盖既有项目数据**） |
| `tests/test_rag_input_regression.py` | A 层：输入构造的回归检查，14 条 |
| `tests/test_api_contract.py` | B 层：HTTP 接口契约测试，3 条（**当前全部 skipped**） |
| `tests/test_hybrid_retrieval.py` | C 层：混合检索规格 1–7，17 条 |

### 修改文件（3 个）

**`app/services/retriever.py`**（145 → 271 行）

| 位置 | 内容 |
|---|---|
| L174 | `RRF_K = 60` —— RRF 常数，写成模块级常量并注明来源 |
| L177 | `_rrf_fuse(...)` —— RRF 融合：按**名次**计分 `1/(k+rank)`，与原始分数无关 |
| L214 | `hybrid_search(...)` —— 关键词路与向量路各取候选后融合 |

规格实现要点（对应任务包）：
1. 用名次而非分数融合，因此两路分数不可比的问题天然规避；
2. 去重键为 `doc_id + chunk_index`，同一片段在两路都命中只算一次、分数累加；
3. 关键词路**零分片段直接丢弃**，不参与融合（避免噪声进榜）；
4. 融合窗口取 `min(len(corpus), max(10, top_k))`，不是无界全量；
5. 向量路失败时抛明确异常（沿用 `EmbeddingError`），不静默退化成只用关键词。

**`app/models/retrieval.py`**（`Candidate` 的 docstring，L36）
- 补充第 3 条：混合检索的 `score` 是 RRF 融合分，由**名次**算出，与关键词命中数、余弦相似度三者**含义不同、不可直接比大小**。

**`scripts/ask_demo.py`**（→ 156 行）

| 位置 | 内容 |
|---|---|
| L45 | 导入 `EmbeddingError` |
| L48 | 导入 `hybrid_search` |
| L78 | `--mode` 增加 `hybrid` 选项，**默认仍是 `vector`**（不改动既有默认行为） |
| L100 | 分发：`hybrid` → `hybrid_search(...)` |
| L103–105 | 捕获 `EmbeddingError`，打印「嵌入失败：…」后退出，不让 traceback 冒出后继续跑 |

未改动：`scripts/retrieve_demo.py`（它没有 `--mode` 分发，是固定对照演示，按"否则不碰"处理）。
未改动：问题传参（L55/L62/L108）—— 按任务包要求**不重复修复**。

---

## 2. 测试结果（实际执行，非推断）

| 层 | 命令 | 结果 |
|---|---|---|
| A | `pytest tests/test_rag_input_regression.py -q` | **14 passed** |
| B | `pytest tests/test_api_contract.py -q -rs` | **3 skipped** — 原因：`ModuleNotFoundError`（缺 httpx） |
| C | `pytest tests/test_hybrid_retrieval.py -q` | **17 passed** |
| 全量 | `pytest -q --basetemp=.pytest_tmp_r2` | **114 passed, 3 skipped**（2.83s） |

计数对账：既有 83 + A 14 + C 17 = **114**，与全量一致；3 条 skip 全部来自 B。

**A 层覆盖**（不调用模型）：
- 换问题 → 两份 prompt 必须不同，且各自含自己的问题行
- 来源标识与完整片段文本保留（不被截断、不被替换）
- 候选为空 → 不编造内容
- 库为空 → 不进入 `generate`
- `monkeypatch` 掉 `generator._local_session.post`，检查实际发出的 payload 构造

**C 层覆盖**：任务包列出的混合检索规格 1–7（名次融合、去重键、零分过滤、窗口边界、异常、默认行为不变、与单路结果的关系）。

临时目录已清理（`.pytest_tmp_r2` 等）。

---

## 3. 待验证 / 未完成事项（如实列出）

1. **B 层未实跑**。`httpx` 未安装，`fastapi.testclient.TestClient` 不可用。已按任务包要求：测试写完整、明确 skip 并带原因，**未安装依赖、未伪装通过**。
   - 若要实跑，需你批准安装：`pip install httpx`（仅本地 venv，不新增模型/框架级依赖）。
   - 安装后预计覆盖：`/health`、`/documents/allowed`、不存在的 `doc_id` → 404；`DATA_DIR` 已用 `tmp_path` 隔离，不会污染真实数据目录。
2. **混合检索未做真实端到端验证**。C 层的 17 条用的是构造候选，未经真实 `bge-m3` 嵌入 + 真实语料跑过。`hybrid` 模式在真实数据上的效果（是否优于单路）**尚未评估**，不在本次结论内。
3. **未做效果评估基线**。任务包里的"评估"部分只落地到样本文件与输入回归，尚未产出可比较的指标表（如召回率）。需要真实语料 + 标注才能做，本次未做。
4. **Ollama 服务状态未复核**。本次全部测试均不调用模型，故未检查服务；若下一步要跑真实问答，需先按既有排查手法确认 `OLLAMA_MODELS` 生效（托盘先启动会读空目录）。

---

## 4. 助手实现 vs 本人学习成果（分开记录）

| 类别 | 内容 |
|---|---|
| **执行层（助手）实现** | 上述 4 个新文件 + 3 个修改文件；A/C 测试通过；报告与记录 |
| **本人（学员）本次完成** | 本章（`02 Python数据与容器`）的动手部分：修改 `learning/02_data.py` 的问题与资料、运行并观察输出。**本次 A/B/C 工程交付不由本人完成，不计入学习成果** |
| **不推导** | 测试通过 ≠ 本人掌握；B 层 skip ≠ 接口无问题 |

---

## 5. 边界遵守情况

- 未安装新依赖、未拉新模型、未引入框架/向量库/重排器
- 未另造问答入口（`ask_demo.py` 仍是唯一入口，只加了一个 `--mode` 选项）
- 未重复修复问题传参
- 未修改 C++ 网站、数电学习包、其他助手配置
- 未读取或回传密钥
- 未删除、未外发、未付费、未部署
- **未提交、未推送**（`git status` 保留全部改动待你决定）
- 未覆盖既有未提交工作
