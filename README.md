# 智能教材语料生成与校验平台

一个基于Flask + Python + SQLite的教材处理和语料生成平台,通过MinerU OCR解析和多模型LLM能力,将PDF教材转化为高质量的问答对和习题集。

## 功能特性

### 🎯 核心功能

- **教材导入与解析**: 支持PDF上传,通过MinerU API进行OCR解析,自动提取书籍元数据
- **智能分章**: 自动识别章节结构,计算Token数量,支持大章节自动分割
- **沉浸式阅读工作台**: 三栏式界面(章节导航 + 内容展示 + 控制面板)
- **LaTeX公式渲染**: 使用MathJax 3完美渲染数学公式
- **多模型LLM支持**: 集成Gemini、ChatGPT、DeepSeek、Kimi
- **问答对生成**: 基于章节内容生成高质量Q&A
- **习题生成**: 自动生成选择题、填空题、简答题
- **人机协作校验**: 内联编辑、状态流转、自动保存
- **进度可视化**: 实时显示各章节校验进度
- **数据导出**: Excel/CSV格式导出,保留LaTeX公式,UTF-8 BOM编码

## 技术栈

- **后端**: Flask 3.0
- **数据库**: SQLite
- **前端**: HTML/CSS/JavaScript + MathJax 3
- **LLM集成**: OpenAI API, Google Gemini API, DeepSeek API, Moonshot Kimi API
- **PDF解析**: MinerU API
- **Token计数**: tiktoken
- **数据导出**: openpyxl

## 项目结构

```
llmswufe/
├── app.py                      # Flask主应用
├── config.py                   # 配置管理
├── database.py                 # 数据库工具
├── schema.sql                  # 数据库模式
├── requirements.txt            # Python依赖
├── .env                        # 环境变量(需创建)
├── .env.example                # 环境变量模板
│
├── llm/                        # LLM集成
│   ├── router.py               # LLM路由器
│   └── prompts.py              # Prompt管理
│
├── parsers/                    # 解析器
│   ├── mineru_client.py        # MinerU API客户端
│   ├── metadata_extractor.py   # 元数据提取
│   └── chapter_parser.py       # 章节解析
│
├── exporters/                  # 导出功能
│   └── excel_exporter.py       # Excel/CSV导出
│
├── templates/                  # HTML模板
│   ├── index.html              # 主页
│   └── reading.html            # 阅读工作台
│
└── static/                     # 静态资源
    ├── css/
    │   ├── main.css            # 主样式
    │   └── reading.css         # 阅读工作台样式
    └── js/
        ├── main.js             # 主页脚本
        └── reading.js          # 阅读工作台脚本
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填写API密钥:

```bash
cp .env.example .env
```

编辑 `.env` 文件:

```env
# MinerU API配置
MINERU_API_KEY=your_mineru_api_key
MINERU_API_URL=https://mineru.net/api/v4

# LLM API密钥 (至少配置一个)
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
DEEPSEEK_API_KEY=your_deepseek_key
KIMI_API_KEY=your_kimi_key

# Flask配置
SECRET_KEY=your-random-secret-key
FLASK_ENV=development
```

### 3. 初始化数据库

数据库会在首次运行时自动创建

### 4. 启动应用

```bash
python app.py
```

访问: http://localhost:5001

## 使用流程

### 1. 上传教材

- 点击上传区域或拖拽PDF文件
- 系统自动检查文件大小(最大200MB)
- 上传后自动触发MinerU解析

### 2. 确认元数据

- 解析完成后,系统提取书名、作者、出版社等信息
- 用户确认并修改元数据
- 确认后进入阅读工作台

### 3. 阅读与生成

- 左侧章节树导航
- 中间显示章节内容(支持LaTeX公式)
- 右侧控制面板:
  - 选择LLM模型
  - 生成问答对/习题
  - 查看/编辑Prompt模板
  - 查看验证进度

### 4. 校验内容

- 生成的内容显示在右侧面板
- 点击内容可直接编辑
- 自动保存修改
- 点击"标记为已确认"完成校验

### 5. 导出数据

- 点击"导出数据"按钮
- 选择Excel或CSV格式
- 导出包含所有校验通过的内容

## 数据库模式

### 主要表结构

- **books**: 教材基本信息
- **chapters**: 章节层级结构
- **generated_content**: 生成的问答对和习题
- **llm_prompts**: Prompt模板
- **user_preferences**: 用户偏好设置
- **parse_tasks**: 异步解析任务

详见 `schema.sql`

## API接口

### 上传与解析

- `POST /api/upload` - 上传PDF
- `POST /api/parse` - 开始解析
- `GET /api/parse/status/<task_id>` - 查询解析状态
- `POST /api/metadata/confirm` - 确认元数据

### 章节管理

- `GET /api/books/<book_id>/chapters` - 获取章节列表
- `GET /api/chapters/<chapter_id>` - 获取章节内容

### 内容生成

- `POST /api/generate/qa` - 生成问答对
- `POST /api/generate/exercise` - 生成习题
- `GET /api/prompts` - 获取Prompt模板

### 校验与导出

- `PUT /api/content/<content_id>` - 编辑内容
- `POST /api/content/<content_id>/verify` - 标记为已校验
- `GET /api/chapters/<chapter_id>/progress` - 获取进度
- `GET /api/export/book/<book_id>` - 导出数据

## 配置说明

### MinerU文件大小限制

默认最大200MB,可在 `.env` 中修改:

```env
MINERU_MAX_FILE_SIZE=200  # MB
PDF_SPLIT_SIZE=180         # MB
```

如果PDF超过限制,请先使用工具分割PDF。

### Token计数阈值

章节Token数超过模型上下文窗口80%时,系统会提示分割:

```python
# config.py
TOKEN_THRESHOLD_PERCENTAGE = 0.8  # 80%
```

### LLM模型配置

在 `config.py` 中可配置各模型的参数:

```python
LLM_MODELS = {
    'gemini': {
        'name': 'Gemini Pro',
        'model_id': 'gemini-pro',
        'max_tokens': 30720,
        'temperature': 0.7,
    },
    # ...
}
```

## 开发说明

### 添加新的LLM提供商

1. 在 `llm/router.py` 中创建新的Provider类:

```python
class NewProvider(LLMProvider):
    def generate(self, prompt: str, **kwargs) -> str:
        # 实现生成逻辑
        pass
```

2. 在 `LLMRouter._initialize_providers()` 中注册:

```python
if config.NEW_API_KEY:
    self.providers['new'] = NewProvider(...)
```

### 自定义Prompt模板

Prompt模板存储在数据库 `llm_prompts` 表中,可以通过界面或直接修改数据库来定制。

## 注意事项

1. **API密钥安全**: 不要将 `.env` 文件提交到版本控制
2. **文件大小**: PDF超过200MB需要分割后上传(MinerU官方限制200MB,最多600页)
3. **Token限制**: 注意各LLM模型的上下文窗口限制
4. **公式格式**: 确保教材中的LaTeX公式格式正确
5. **导出编码**: Excel导出使用UTF-8 BOM编码,确保中文显示正常

## 许可证

MIT License

## 支持

如有问题,请查看文档或提交Issue。
