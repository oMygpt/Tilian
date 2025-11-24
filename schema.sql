-- Database Schema for Intelligent Textbook Corpus Generation Platform
-- SQLite Database

-- Books table: stores uploaded book metadata
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    isbn TEXT,
    publisher TEXT,
    publish_year INTEGER,
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    source_file_path TEXT NOT NULL,
    parsed_json_path TEXT,
    parsed_md_path TEXT,
    status TEXT DEFAULT 'uploaded' CHECK(status IN ('uploaded', 'parsing', 'parsed', 'error')),
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Chapters table: hierarchical structure for book content
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    parent_chapter_id INTEGER,
    title TEXT NOT NULL,
    content_md TEXT,
    content_json TEXT,
    token_count INTEGER DEFAULT 0,
    order_index INTEGER NOT NULL,
    level INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- LLM Prompts table: manages prompt templates
CREATE TABLE IF NOT EXISTS llm_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_type TEXT NOT NULL CHECK(prompt_type IN ('qa', 'exercise')),
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    is_global BOOLEAN DEFAULT 1,
    version INTEGER DEFAULT 1,
    created_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Generated Content table: stores Q&A pairs and exercises
CREATE TABLE IF NOT EXISTS generated_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    content_type TEXT NOT NULL CHECK(content_type IN ('qa', 'exercise')),
    question TEXT NOT NULL,
    options_json TEXT,
    answer TEXT NOT NULL,
    explanation TEXT,
    model_name TEXT NOT NULL,
    model_version TEXT,
    generation_mode TEXT DEFAULT 'standard',
    status TEXT DEFAULT 'generated' CHECK(status IN ('pending', 'generated', 'verified')),
    verified_at DATETIME,
    verified_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- User Preferences table: stores user settings per chapter
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER NOT NULL,
    preferred_model TEXT,
    custom_settings_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);

-- Parse Tasks table: tracks async parsing tasks
CREATE TABLE IF NOT EXISTS parse_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    task_id TEXT UNIQUE,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
    progress INTEGER DEFAULT 0,
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

-- Agent Workflow Logs table: stores intermediate steps of multi-agent workflows
CREATE TABLE IF NOT EXISTS agent_workflow_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    chapter_id INTEGER,
    agent_name TEXT NOT NULL,
    step_name TEXT NOT NULL,
    input_data TEXT,
    output_data TEXT,
    model_name TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE SET NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);
CREATE INDEX IF NOT EXISTS idx_chapters_book_id ON chapters(book_id);
CREATE INDEX IF NOT EXISTS idx_chapters_parent ON chapters(parent_chapter_id);
CREATE INDEX IF NOT EXISTS idx_chapters_order ON chapters(book_id, order_index);
CREATE INDEX IF NOT EXISTS idx_generated_content_chapter ON generated_content(chapter_id);
CREATE INDEX IF NOT EXISTS idx_generated_content_status ON generated_content(status);
CREATE INDEX IF NOT EXISTS idx_user_preferences_chapter ON user_preferences(chapter_id);
CREATE INDEX IF NOT EXISTS idx_parse_tasks_book ON parse_tasks(book_id);
CREATE INDEX IF NOT EXISTS idx_parse_tasks_status ON parse_tasks(status);

-- Insert default prompt templates
INSERT INTO llm_prompts (prompt_type, name, content, is_global, version) VALUES
('qa', 'Default Q&A Prompt', '你是一位经验丰富的教师。基于以下教材内容，生成5个高质量的问答对。

教材章节：{chapter_title}

教材内容：
{chapter_content}

要求：
1. 问题应该覆盖关键概念和重要知识点
2. 答案应该准确、完整、清晰
3. 提供详细的解析说明
4. 如果涉及数学公式，请使用LaTeX格式，例如：$x^2 + y^2 = r^2$

请以JSON格式返回，格式如下：
[
  {
    "question": "问题内容",
    "answer": "答案内容",
    "explanation": "解析说明"
  }
]', 1, 1),

('exercise', 'Default Exercise Prompt', '你是一位经验丰富的教师。基于以下教材内容，生成5道高质量的练习题。

教材章节：{chapter_title}

教材内容：
{chapter_content}

要求：
1. 题目类型可以是选择题、填空题或简答题
2. 选择题需要提供4个选项（A/B/C/D）
3. 答案应该准确无误
4. 提供详细的解题过程和解析
5. 如果涉及数学公式，请使用LaTeX格式，例如：$\\lim_{{x \\to 0}} \\frac{{\\sin x}}{{x}} = 1$

请以JSON格式返回，格式如下：
[
  {
    "type": "choice|fill|essay",
    "question": "题干内容",
    "options": ["A选项", "B选项", "C选项", "D选项"],  // 仅选择题需要
    "answer": "答案内容",
    "explanation": "解析说明"
  }
]', 1, 1);

-- Trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_books_timestamp 
AFTER UPDATE ON books
BEGIN
    UPDATE books SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_chapters_timestamp 
AFTER UPDATE ON chapters
BEGIN
    UPDATE chapters SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_generated_content_timestamp 
AFTER UPDATE ON generated_content
BEGIN
    UPDATE generated_content SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_user_preferences_timestamp 
AFTER UPDATE ON user_preferences
BEGIN
    UPDATE user_preferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_parse_tasks_timestamp 
AFTER UPDATE ON parse_tasks
BEGIN
    UPDATE parse_tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
