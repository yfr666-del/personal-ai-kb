# personal-ai-kb

个人 AI 知识库系统 —— 支持引用溯源、混合检索与 Agentic RAG。

不依赖框架起步：先用原生 Python 把检索的每一步写明白，再引入 LangChain 之类的框架。
目标是产出一个能讲清原理、拿得出手的工程作品，而不是跟着教程跑的 Demo。

## 技术栈

| 层 | 选型 | 用途 |
|---|---|---|
| 语言 | Python 3.13 | — |
| 数据校验 | Pydantic v2 | 文档元数据、接口入参、配置统一校验 |
| 配置管理 | pydantic-settings | 从 `.env` / 环境变量读取配置 |
| Web 框架 | FastAPI | 接口层（Day 4 起） |
| 测试 | pytest | 单元测试与接口测试（Day 4 起） |

## 快速开始

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate            # PowerShell
# source .venv/Scripts/activate   # Git Bash

# 2. 安装依赖
pip install pydantic pydantic-settings

# 3. 准备配置：把模板复制成 .env，再填入自己的 API Key
copy .env.example .env            # PowerShell
# cp .env.example .env            # Git Bash

# 4. 自检
python learn_pydantic.py          # Pydantic 基础实验
python check_models.py            # 文档模型校验规则
python check_config.py            # 配置读取
```

## 目录说明

```
personal-ai-kb/
├── app/
│   ├── api/         接口层：FastAPI 路由，HTTP 的出入口
│   ├── core/        核心配置与通用工具（config.py）
│   ├── models/      Pydantic 数据模型：所有校验规则的集中地
│   └── services/    业务逻辑：文档切分、检索、LLM 调用
├── data/            本地数据（上传文件、向量库），不进 Git
├── tests/           测试
├── learn_pydantic.py / check_models.py / check_config.py   学习用自检脚本
├── .env             本地配置（含密钥，不进 Git）
└── .env.example     配置模板（进 Git，新克隆的人照着填）
```

## 开发约定

- 提交信息统一前缀：`feat:` 新功能 / `fix:` 修 bug / `chore:` 杂务 / `docs:` 文档
- **密钥只写在 `.env`**（已被 `.gitignore` 屏蔽），仓库里只保留不含真实值的 `.env.example`
- 每个模块顶部写 docstring 说明职责
- 校验规则集中在 `app/models/`，不在业务代码里散落 `if` 判断

## 进度

- [x] M1 Day 1–2 环境搭建与仓库初始化
- [x] M1 Day 3 Python 工程基础（Pydantic + 配置管理）
- [ ] M1 Day 4 FastAPI 骨架 + 文件上传接口 + 第一个测试
- [ ] M1 Day 5 目录结构定稿 + 打 tag v0.0.1
