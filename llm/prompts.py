"""
Prompt management and formatting utilities
"""

from typing import Dict, Any


def format_prompt(template: str, **kwargs) -> str:
    """
    Format a prompt template with provided variables
    Uses simple string replacement to avoid conflicts with JSON curly braces
    
    Args:
        template: Prompt template with {variable} placeholders
        **kwargs: Variables to substitute
    
    Returns:
        Formatted prompt string
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace(f'{{{key}}}', str(value))
    return result


def get_qa_prompt(chapter_title: str, chapter_content: str, custom_template: str = None, count: int = 8) -> str:
    """
    Get formatted Q&A generation prompt
    
    Args:
        chapter_title: Title of the chapter
        chapter_content: Content of the chapter
        custom_template: Optional custom template (if None, uses default)
        count: Number of items to generate
    
    Returns:
        Formatted prompt
    """
    if custom_template is None:
        # Default template - should match database default
        custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}个高质量的问答对。

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 问题应该覆盖关键概念和重要知识点
2. 答案应该准确、完整、清晰
3. 提供详细的解析说明
4. 如果涉及数学公式,请使用LaTeX格式,例如:$x^2 + y^2 = r^2$

请以JSON格式返回,格式如下:
[
  {{
    "question": "问题内容",
    "answer": "答案内容",
    "explanation": "解析说明"
  }}
]'''
    
    return format_prompt(
        custom_template,
        chapter_title=chapter_title,
        chapter_content=chapter_content,
        count=count
    )


def get_exercise_prompt(chapter_title: str, chapter_content: str, custom_template: str = None, count: int = 8, exercise_type: str = None, language: str = 'zh') -> str:
    """
    Get formatted exercise generation prompt
    
    Args:
        chapter_title: Title of the chapter
        chapter_content: Content of the chapter
        custom_template: Optional custom template (if None, uses default)
        count: Number of items to generate
        exercise_type: Specific type of exercise to generate (single_choice, multiple_choice, calculation, short_answer, essay)
        language: Language for generation ('zh' or 'en')
    
    Returns:
        Formatted prompt
    """
    lang_instruction = "请使用中文生成。" if language == 'zh' else "Please generate in English."
    
    if custom_template:
        # Check if placeholder exists, if not append instruction
        if '{lang_instruction}' not in custom_template:
            custom_template += f"\n\n{lang_instruction}"
            
    if custom_template is None:
        # Default templates based on type
        if exercise_type == 'single_choice':
            custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的单项选择题。{lang_instruction}

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
        elif exercise_type == 'multiple_choice':
            custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的多项选择题。{lang_instruction}

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
        elif exercise_type == 'calculation':
            custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的计算题。{lang_instruction}

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
        elif exercise_type == 'short_answer':
            custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的简答题。{lang_instruction}

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
        elif exercise_type == 'essay':
            custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的论述题。{lang_instruction}

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
        else:
            # Default mixed template
            custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的练习题。{lang_instruction}

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 题目类型可以是选择题、填空题或简答题
2. 选择题需要提供4个选项(A/B/C/D)
3. 答案应该准确无误
4. 提供详细的解题过程和解析
5. 指出题目考察的知识点
6. 如果涉及数学公式,请使用LaTeX格式,例如:$\\lim_{{x \\to 0}} \\frac{{\\sin x}}{{x}} = 1$

请以JSON格式返回,格式如下:
[
  {{
    "type": "choice|fill|essay",
    "question": "题干内容",
    "options": ["A选项", "B选项", "C选项", "D选项"],
    "answer": "答案内容",
    "explanation": "解析说明",
    "knowledge_point": "考察的知识点"
  }}
]'''
    
    return format_prompt(
        custom_template,
        chapter_title=chapter_title,
        chapter_content=chapter_content,
        count=count,
        lang_instruction=lang_instruction
    )


def parse_llm_response(response: str) -> list:
    """
    Parse LLM JSON response
    
    Args:
        response: LLM response string
    
    Returns:
        Parsed list of items
    
    Raises:
        ValueError: If response is not valid JSON
    """
    import json
    import re
    
    # Try to extract JSON from code blocks
    json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
    if json_match:
        response = json_match.group(1)
    
    # Try to find JSON array in response
    json_match = re.search(r'\[.*\]', response, re.DOTALL)
    if json_match:
        response = json_match.group(0)
    
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Try to repair JSON
        try:
            repaired = repair_json_string(response)
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}\nRepaired: {repaired[:200]}\nOriginal: {response[:200]}")


def repair_json_string(json_str: str) -> str:
    """
    Attempt to repair invalid JSON string, specifically handling unescaped backslashes in LaTeX
    """
    import re
    
    # 1. Replace single backslashes with double backslashes, 
    # BUT ignore valid escape sequences: \", \\, \/, \uXXXX
    # We aggressively escape everything else (including \n, \t, \b, \f, \r) 
    # because in LaTeX context, \text or \frac should be treated as literal backslashes, not control chars.
    
    # Pattern explanation:
    # \\          Match a single backslash
    # (?!         Negative lookahead (assert that what follows is NOT...)
    #   ["\\/]        One of the valid single-char escapes (quote, backslash, forward slash)
    #   |             OR
    #   u[0-9a-fA-F]{4}  A unicode escape sequence
    # )
    pattern = r'\\(?!(["\\/]|u[0-9a-fA-F]{4}))'
    
    return re.sub(pattern, r'\\\\', json_str)


def validate_qa_item(item: Dict[str, Any]) -> bool:
    """Validate a Q&A item has required fields"""
    required_fields = ['question', 'answer']
    return all(field in item for field in required_fields)


def validate_exercise_item(item: Dict[str, Any]) -> bool:
    """Validate an exercise item has required fields"""
    required_fields = ['question', 'answer', 'type']
    if not all(field in item for field in required_fields):
        return False
    
    # Choice questions must have options
    if item['type'] == 'choice' and 'options' not in item:
        return False
    
    return True
