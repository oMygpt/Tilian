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


def get_exercise_prompt(chapter_title: str, chapter_content: str, custom_template: str = None, count: int = 8) -> str:
    """
    Get formatted exercise generation prompt
    
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
        custom_template = '''你是一位经验丰富的教师。基于以下教材内容,生成{count}道高质量的练习题。

教材章节:{chapter_title}

教材内容:
{chapter_content}

要求:
1. 题目类型可以是选择题、填空题或简答题
2. 选择题需要提供4个选项(A/B/C/D)
3. 答案应该准确无误
4. 提供详细的解题过程和解析
5. 如果涉及数学公式,请使用LaTeX格式,例如:$\\lim_{{x \\to 0}} \\frac{{\\sin x}}{{x}} = 1$

请以JSON格式返回,格式如下:
[
  {{
    "type": "choice|fill|essay",
    "question": "题干内容",
    "options": ["A选项", "B选项", "C选项", "D选项"],
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
        data = json.loads(response)
        if not isinstance(data, list):
            raise ValueError("Response must be a JSON array")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}\nResponse: {response[:200]}")


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
