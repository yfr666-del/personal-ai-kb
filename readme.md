# personal-ai-kb

个人 AI 知识库系统 —— 支持引用溯源、混合检索与 Agentic RAG。

不依赖框架起步：先用原生 Python 把检索的每一步写明白，再引入 LangChain 之类的框架。
目标是产出一个能讲清原理、拿得出手的工程作品，而不是跟着教程跑的 Demo。

> **当前状态：M1 骨架 v0.1**（tag `v0.1.0`）
> 「收资料」全链路已打通：上传 → 解析 → 切分 → 落盘，62 个测试守着。

## 技术栈

| 层 | 选型 | 用途 |
|---|---|---|
| 语言 | Python 3.13 | — |
| 数据校验 | Pydantic v2 | 文档元数据、接口入参、配置统一校验 |
| 配置管理 | pydantic-settings | 从 `.env` / 环境变量读取配置 |
| Web 框架 | FastAPI | 接口层 |
| 服务器 | Uvicorn | 本地开发运行，`--reload` 改完自动重启 |
| PDF 解析 | pypdf | 把 PDF 里的文字抠出来 |
| 演示界面 | Streamlit | M1 的可视化演示页 |
| 测试 | pytest | 规则、接口与页面测试 |

## 快速开始

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate            # PowerShell
# source .venv/Scripts/activate   # Git Bash

# 2. 安装依赖
pip install -r requirements.txt

# 3. 准备配置：把模板复制成 .env，再填入自己的 API Key
copy .env.example .env            # PowerShell
# cp .env.example .env            # Git Bash

# 4. 启动服务
uvicorn app.main:app --reload
# 浏览器打开 http://127.0.0.1:8000/docs 试用接口

# 5. 启动演示页（另开一个终端）
.venv\Scripts\python.exe -m streamlit run streamlit_app.py
# 浏览器打开 http://127.0.0.1:8501

# 6. 跑测试
pytest -v
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查，确认服务活着 |
| POST | `/documents/upload` | 上传文件：校验 → 解析 → 切分 → 落盘 |
| GET | `/documents/allowed` | 查询当前允许上传的文件类型 |
| GET | `/documents` | 列出已收进来的所有文档 |
| GET | `/documents/{doc_id}` | 取一份文档的完整内容（含所有切分块） |

校验规则统一写在 `app/models/document.py`，业务流程统一写在 `app/services/`，接口层只负责把 HTTP 翻译成业务调用 —— 规则改一处，全项目生效。

## 目录说明

```
personal-ai-kb/
├── app/
│   ├── main.py      应用入口：创建 FastAPI 实例、挂载路由
│   ├── api/         接口层：HTTP 的出入口，只做翻译不做业务
│   ├── core/        核心配置（config.py）
│   ├── models/      Pydantic 数据模型：所有校验规则的集中地
│   └── services/    业务逻辑（收资料的四个步骤都在这里）
│       ├── ingest.py   入库总流程：校验 → 解析 → 切分 → 落盘
│       ├── parser.py   解析：把文件字节变成纯文字（PDF / txt / md）
│       ├── chunker.py  切分：把长文本切成带重叠的小块
│       └── storage.py  存储：把文件与块落到 data/ 目录
├── tests/           测试
├── data/            本地数据（原文件、切好的块），不进 Git
├── streamlit_app.py Streamlit 演示页
├── pytest.ini       pytest 配置
├── requirements.txt 依赖清单
├── learn_pydantic.py / check_models.py / check_config.py   学习用自检脚本
├── .env             本地配置（含密钥，不进 Git）
└── .env.example     配置模板（进 Git，新克隆的人照着填）
```

## 开发约定

- 提交信息统一前缀：`feat:` 新功能 / `fix:` 修 bug / `chore:` 杂务 / `docs:` 文档 / `test:` 测试
- **密钥只写在 `.env`**（已被 `.gitignore` 屏蔽），仓库里只保留不含真实值的 `.env.example`
- 每个模块顶部写 docstring 说明职责
- 校验规则集中在 `app/models/`，不在业务代码里散落 `if` 判断
- 改完代码跑 `pytest -v`，绿了再提交

## 进度

- [x] M1 Day 1–2 环境搭建与仓库初始化
- [x] M1 Day 3 Python 工程基础（Pydantic + 配置管理）
- [x] M1 Day 4 FastAPI 骨架 + 文件上传接口
- [x] M1 Day 5 白名单接口 + 单元测试（12 例）+ 打 tag **v0.1.0**
- [x] M1 收资料链路：解析（PDF/txt/md）→ 切分（带重叠）→ 落盘
- [x] M1 第一篇项目笔记（`blog/01-project-structure.md`）
- [x] M1 Streamlit 演示页
- [ ] M1 收尾：根目录草稿脚本归置
- [ ] M2 RAG 最简闭环 + 20 题评估集
