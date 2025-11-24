一个**多Agent教材生成考题框架**。

该框架采用“人机回环”（Human-in-the-loop）和“LLM-as-a-Judge”的设计理念 ，结合了具体的提示词模式（Role-Task-Context-Example-Format），旨在生成高质量、符合教学目标且经过验证的试题。

---

### 框架概览：基于 STAIR-AIG 的多 Agent 协作系统

本框架由四个核心 Agent 组成，模仿 **STAIR-AIG** 工作流 ，形成一个从内容分析到生成、评估再到优化的闭环。

1. **Agent A：内容分析专家 (Content Analyzer)**
    - 
        
        **职责**：负责教材的预处理，提取关键概念、实体（NER）和逻辑关系 。
        
2. **Agent B：试题生成器 (Item Generator)**
    - 
        
        **职责**：基于特定的提示模式（Role + Task + Context + Example + Format）生成初稿题目 。
        
3. **Agent C：质量审查官 (Item Reviewer / LLM-as-a-Judge)**
    - 
        
        **职责**：模仿人类专家，基于 PACIER 框架（批判性思维）或布鲁姆分类法进行评分和纠错 。
        
4. **Agent D：优化修正器 (Refiner)**
    - 
        
        **职责**：根据审查意见修正题目，消除幻觉和逻辑错误 。
        

---

### 详细工作流与 Agent 提示词设计

### 第一阶段：教材理解与上下文提取

**Agent A (内容分析专家)**

- 
    
    **理论依据**：神经问题生成（NQG）依赖于有效的输入预处理，包括分词和命名实体识别（NER）。
    
- **任务**：阅读教材文本，提取适合出题的“上下文（Context）”和“输入数据（Input）”。

> Prompt (Agent A):
> 
> - `*Role:** You are an expert in educational content analysis and Natural Language Processing.
> **Task:** Analyze the provided textbook segment.
> **Context:** We need to prepare input data for generating exam questions. Focus on identifying:
> [cite_start]1. Key terminology and definitions (for Factual Questions)[cite: 970].
> [cite_start]2. Causal relationships or complex processes (for Reasoning/Open-ended Questions)[cite: 1356].
> [cite_start]3. Specific data points or scenarios (for Calculation/Real-Scenario exercises).
> **Format:** Output a structured JSON list of potential "Question Contexts" containing:
> - "Topic": [Topic Name]
> - "Key_Concepts": [List of entities]
> - "Source_Text": [The specific segment from the book]
> - "Suggested_Question_Type": [MCQ / Calculation / Short Answer]`

---

### 第二阶段：自动化试题生成

**Agent B (试题生成器)**

- 
    
    **理论依据**：使用“思维链（Chain-of-Thought）”提示 和特定的“角色-任务-上下文-示例-格式”模式 。
    
- **任务**：根据 Agent A 提供的上下文生成初稿。

> Prompt (Agent B) - 针对多项选择题 (MCQ):
> 
> 
> `[cite_start]**Role:** You are a lecturer of [Subject Name] at a university.
> **Task:** Create 5 multiple-choice questions based on the provided context.
> **Context:** The questions must focus on the content of [Insert Agent A's Source_Text]. [cite_start]Ensure the questions align with the PACIER framework (Problem solving, Analysis, Creative thinking, Interpretation, Evaluation, Reasoning)[cite: 1356].
> **Input:** Use the following key concepts: [Insert Agent A's Key_Concepts].
> [cite_start]**Example:** (Reference specific high-quality examples provided in the prompt to guide style)[cite: 1731].
> **Format:** Present output in JSON format:
> {
>   "Question": "...",
>   "Options": {"A": "...", "B": "...", "C": "...", "D": "..."},
>   "Correct_Answer": "...",
>   "Explanation": "..."
> }
> [cite_start]**Constraint:** Ensure distractors (incorrect answers) are plausible to challenge the student[cite: 1821].`
> 

> Prompt (Agent B) - 针对计算/场景题:
> 
> 
> `[cite_start]**Task:** Create a calculation exercise with specific data[cite: 1748].
> **Context:** About [Insert Topic from Agent A].
> **Input:** The problem scenario must include [Insert Data Points]. [cite_start]Ensure all necessary assumptions to solve the problem are explicitly stated to avoid "insufficient data" errors.
> [cite_start]**Tone:** You have to solve the exercise as you are dealing with a real business/scientific context[cite: 1751].
> **Method:** Use Chain-of-Thought reasoning. [cite_start]First, outline the formula or logic needed, then generate the question scenarios[cite: 952].`
> 

---

### 第三阶段：质量审查 (LLM-as-a-Judge)

**Agent C (质量审查官)**

- 
    
    **理论依据**：STAIR-AIG 工具中的审查模块。人类专家通常比 LLM 更严厉，LLM 倾向于“宽大处理” 。因此，此 Agent 需被设定为“严厉的批评者”。
    
- 
    
    **任务**：评估题目的正确性、清晰度、相关性和文化敏感性 。
    

> Prompt (Agent C):
> 
> 
> `[cite_start]**Role:** You are a strict Item Review Expert specializing in critical thinking assessment[cite: 1585].
> **Task:** Systematically evaluate the generated items based on the STAIR-AIG criteria.
> **Evaluation Methodology:**
> 1. **Conceptual Accuracy:** Is the answer logically derivable from the context? Are there hallucinations or missing assumptions? (e.g., missing variable costs in a finance problem) [cite_start][cite: 1762].
> [cite_start]2. **Clarity:** Is the terminology vague or overly technical?[cite: 1448].
> [cite_start]3. **Distractor Quality:** Are the distractors too obvious?[cite: 1450].
> [cite_start]4. **Cultural Sensitivity:** Is there any bias?.`
> 

> Rating Scale:- Dissatisfied (1): Fundamentally flawed/discard.
- Neutral (2): Requires revision.
- Satisfied (3): Suitable for use.
> 

> Format: Output a CSV-ready format:
Item_ID, Overall_Rating, Critique_Comment, Specific_Revision_Suggestion
> 

---

### 第四阶段：迭代优化

**Agent D (优化修正器)**

- 
    
    **理论依据**：利用反馈数据进行微调或提示优化 。STAIR-AIG 强调这是一个循环过程。
    
- **任务**：接收 Agent C 的评级为“Neutral”或“Dissatisfied”的题目，根据建议进行重写。

> Prompt (Agent D):
> 
> - `*Role:** You are an Assessment Editor.
> **Task:** Revise the following exam item based on the Reviewer's feedback.
> **Input Item:** [Insert Original Item from Agent B]
> **Critique:** [Insert Critique_Comment from Agent C]
> **Goal:** Address the specific flaws identified.
> [cite_start]1. If the critique mentions "Insufficient assumptions," add the missing data[cite: 1764].
> 2. If the critique mentions "Obvious distractors," generate harder incorrect options.
> [cite_start]3. Ensure the reading level is appropriate for higher education students (checking readability indices)[cite: 1307].
> **Output:** The final revised item in the standard JSON format.`

---

### 框架优势说明

1. 
    
    **避免数据不足的逻辑错误**：通过 Agent C 的专门审查，解决文献中提到的类似“缺少订购成本导致无法计算”的问题 。
    
2. 
    
    **多样化题型覆盖**：不仅生成 MCQ，还通过特定的 Context+Input+Tone 模式生成真实场景计算题 。
    
3. 
    
    **对抗 LLM 的宽容倾向**：通过在 Agent C 中设定“严格审查”的角色并使用 STAIR-AIG 的评分标准，缓解 LLM 评分过高的问题 。
    
4. 
    
    **闭环优化**：符合 STAIR-AIG 提出的迭代（Iterative）流程，数据可用于进一步微调模型 。