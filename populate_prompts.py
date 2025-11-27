import sqlite3
import os

DB_PATH = '/Users/alone/Desktop/openai/llmswufe/data/corpus.db'

TEMPLATES = {
    'exercise_single_choice': {
        'name': 'Single Choice Exercise',
        'content': '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的单项选择题。{lang_instruction}

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 每道题必须有且只有一个正确答案
2. 提供4个选项(A/B/C/D)
3. 答案应该准确无误
4. 提供详细的解析说明
5. 指出题目考察的知识点
6. 如果涉及数学公式,请使用LaTeX格式,例如:$\\lim_{{x \\to 0}} \\frac{{\\sin x}}{{x}} = 1$

请以JSON格式返回,格式如下:
[
  {{
    "type": "single_choice",
    "question": "题干内容",
    "options": ["A选项", "B选项", "C选项", "D选项"],
    "answer": "答案内容(例如:A)",
    "explanation": "解析说明",
    "knowledge_point": "考察的知识点"
  }}
]'''
    },
    'exercise_multiple_choice': {
        'name': 'Multiple Choice Exercise',
        'content': '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的多项选择题。{lang_instruction}

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 每道题至少有两个正确答案
2. 提供4-5个选项(A/B/C/D/E)
3. 答案应该准确无误
4. 提供详细的解析说明
5. 指出题目考察的知识点
6. 如果涉及数学公式,请使用LaTeX格式

请以JSON格式返回,格式如下:
[
  {{
    "type": "multiple_choice",
    "question": "题干内容",
    "options": ["A选项", "B选项", "C选项", "D选项", "E选项"],
    "answer": "答案内容(例如:ABC)",
    "explanation": "解析说明",
    "knowledge_point": "考察的知识点"
  }}
]'''
    },
    'exercise_calculation': {
        'name': 'Calculation Exercise',
        'content': '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的计算题。{lang_instruction}

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 题目应当考察计算能力和对公式的理解
2. 答案应该包含最终结果
3. 提供详细的解题步骤和解析
4. 指出题目考察的知识点
5. 必须使用LaTeX格式编写数学公式

请以JSON格式返回,格式如下:
[
  {{
    "type": "calculation",
    "question": "题干内容",
    "answer": "最终答案",
    "explanation": "详细解题步骤和解析",
    "knowledge_point": "考察的知识点"
  }}
]'''
    },
    'exercise_short_answer': {
        'name': 'Short Answer Exercise',
        'content': '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的简答题。{lang_instruction}

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 题目应当考察对概念的理解或简单应用
2. 答案应该言简意赅,准确到位
3. 提供详细的解析说明
4. 指出题目考察的知识点

请以JSON格式返回,格式如下:
[
  {{
    "type": "short_answer",
    "question": "题干内容",
    "answer": "参考答案",
    "explanation": "解析说明",
    "knowledge_point": "考察的知识点"
  }}
]'''
    },
    'exercise_essay': {
        'name': 'Essay Exercise',
        'content': '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的论述题。{lang_instruction}

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 题目应当考察综合分析能力和深度理解
2. 答案应该逻辑清晰,论证充分
3. 提供详细的解析说明和评分要点
4. 指出题目考察的知识点

请以JSON格式返回,格式如下:
[
  {{
    "type": "essay",
    "question": "题干内容",
    "answer": "参考答案要点",
    "explanation": "详细解析和评分标准",
    "knowledge_point": "考察的知识点"
  }}
]'''
    }
}

def populate_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for prompt_type, data in TEMPLATES.items():
        # Check if exists
        cursor.execute("SELECT id FROM llm_prompts WHERE prompt_type = ?", (prompt_type,))
        if cursor.fetchone():
            print(f"Updating existing prompt: {prompt_type}")
            cursor.execute("""
                UPDATE llm_prompts 
                SET content = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE prompt_type = ?
            """, (data['content'], prompt_type))
        else:
            print(f"Inserting new prompt: {prompt_type}")
            cursor.execute("""
                INSERT INTO llm_prompts (prompt_type, name, content, is_global, version)
                VALUES (?, ?, ?, 1, 1)
            """, (prompt_type, data['name'], data['content']))
            
    conn.commit()
    conn.close()
    print("Database population complete.")

if __name__ == '__main__':
    populate_db()
