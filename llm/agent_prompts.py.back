"""
Prompts for Multi-Agent Question Generation Workflow
Based on STAIR-AIG framework
"""

# Agent A: Content Analyzer
ANALYZER_PROMPT = """**Role:** You are an expert in educational content analysis and Natural Language Processing.
**Task:** Analyze the provided textbook segment.
**Context:** We need to prepare input data for generating exam questions. Focus on identifying:
1. Key terminology and definitions (for Factual Questions).
2. Causal relationships or complex processes (for Reasoning/Open-ended Questions).
3. Specific data points or scenarios (for Calculation/Real-Scenario exercises).

**Source Text:**
{chapter_content}

**Format:** Output a structured JSON list of potential "Question Contexts" containing:
[
  {{
    "Topic": "Topic Name",
    "Key_Concepts": ["Concept 1", "Concept 2"],
    "Source_Text": "The specific segment from the book...",
    "Suggested_Question_Type": "MCQ" or "Calculation" or "Short Answer"
  }}
]
"""

# Agent B: Item Generator (MCQ)
GENERATOR_MCQ_PROMPT = """**Role:** You are a lecturer of the subject at a university.
**Task:** Create {count} multiple-choice questions based on the provided context.
**Context:** The questions must focus on the content of the provided source text. Ensure the questions align with the PACIER framework (Problem solving, Analysis, Creative thinking, Interpretation, Evaluation, Reasoning).
**Input:** 
- Topic: {topic}
- Key Concepts: {concepts}
- Source Text: {source_text}

**Format:** Present output in JSON format:
[
  {{
    "question": "Question text...",
    "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
    "answer": "Correct Answer (e.g., A. Option 1)",
    "explanation": "Detailed explanation..."
  }}
]
**Constraint:** Ensure distractors (incorrect answers) are plausible to challenge the student.
"""

# Agent B: Item Generator (Exercise/Calculation)
GENERATOR_EXERCISE_PROMPT = """**Role:** You are a lecturer of the subject at a university.
**Task:** Create {count} exercise questions (calculation or scenario-based) based on the provided context.
**Context:** About {topic}.
**Input:** 
- Key Concepts: {concepts}
- Source Text: {source_text}

**Tone:** You have to solve the exercise as you are dealing with a real business/scientific context.
**Method:** Use Chain-of-Thought reasoning. First, outline the formula or logic needed, then generate the question scenarios.

**Format:** Present output in JSON format:
[
  {{
    "type": "fill" or "essay",
    "question": "Question text...",
    "answer": "Correct Answer",
    "explanation": "Detailed explanation..."
  }}
]
"""

# Agent C: Item Reviewer
REVIEWER_PROMPT = """**Role:** You are a strict Item Review Expert specializing in critical thinking assessment.
**Task:** Systematically evaluate the generated items based on the STAIR-AIG criteria.

**Items to Review:**
{items_json}

**Evaluation Methodology:**
1. **Conceptual Accuracy:** Is the answer logically derivable from the context? Are there hallucinations or missing assumptions?
2. **Clarity:** Is the terminology vague or overly technical?
3. **Distractor Quality:** Are the distractors too obvious? (For MCQs)
4. **Cultural Sensitivity:** Is there any bias?

**Rating Scale:**
- Dissatisfied (1): Fundamentally flawed/discard.
- Neutral (2): Requires revision.
- Satisfied (3): Suitable for use.

**Format:** Output a JSON list of reviews:
[
  {{
    "item_index": 0, (Index of the item in the input list)
    "rating": 1 or 2 or 3,
    "critique": "Critique comment...",
    "suggestion": "Specific revision suggestion..."
  }}
]
"""

# Agent D: Refiner
REFINER_PROMPT = """**Role:** You are an Assessment Editor.
**Task:** Revise the exam item based on the Reviewer's feedback.

**Original Item:**
{original_item}

**Critique:**
{critique}

**Suggestion:**
{suggestion}

**Goal:** Address the specific flaws identified.
1. If the critique mentions "Insufficient assumptions," add the missing data.
2. If the critique mentions "Obvious distractors," generate harder incorrect options.
3. Ensure the reading level is appropriate for higher education students.

**Format:** Output the final revised item in JSON format (single object):
{{
  "question": "...",
  "options": [...], (if applicable)
  "answer": "...",
  "explanation": "..."
}}
"""
