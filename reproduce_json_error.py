
from llm.prompts import parse_llm_response
import json

# The problematic JSON string from the user report
# Note: I'm using a raw string and manually adding the problematic part
# The error was: Invalid \escape: line 40 column 212 (char 3258)
# This usually happens with LaTeX like \ell or \min where backslashes are not escaped as \\

problematic_response = r"""
[
  {
    "type": "single_choice",
    "question": "在压缩感知领域，基追踪（Basis Pursuit）问题旨在寻找一个在特定线性约束下具有最小 $\ell_1$ 范数的解，其标准形式为 $\min_{x \in \mathbb{R}^n} \|x\|_1$ s.t. $Ax = b$。如何将此问题等价地转化为一个线性规划（Linear Programming）问题？",
    "options": ["A", "B", "C", "D"],
    "answer": "A",
    "explanation": "Explanation with \LaTeX"
  }
]
"""

print("Attempting to parse problematic response...")
try:
    data = parse_llm_response(problematic_response)
    print("Success! (Unexpected)")
    print(json.dumps(data, indent=2, ensure_ascii=False))
except ValueError as e:
    print(f"Caught expected error: {e}")
except Exception as e:
    print(f"Caught unexpected error: {e}")
