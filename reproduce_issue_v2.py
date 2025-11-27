
from llm.prompts import repair_json_string
import json
import re

def test_specific_failure():
    # The snippet from the user
    # "question": "若将基追踪问题 $$\\min_{x\\in\\mathbb{R}^n}\\|x\\|_1\\quad\\text{s.t.}\\;Ax=b$$ ...
    # Note: In Python string literal, we need to be careful to represent exactly what the LLM likely output.
    # If the error is "Invalid \escape", the JSON string must contain a single backslash followed by an invalid char.
    # The snippet shows "$$\\min". 
    # If it was "\\min", it would be valid JSON (representing \min).
    # So it must be "\min" (representing invalid escape \m).
    
    # Let's construct the string that causes "Invalid \escape" at "min"
    # We use raw string to avoid python escaping
    
    # Case 1: Single backslash before min
    problematic_json = r'''
[
  {
    "type": "single_choice",
    "question": "若将基追踪问题 $$\min_{x\in\mathbb{R}^n}\|x\|_1\quad\text{s.t.}\;Ax=b$$ 通过引入正负部变量 $$x=x^+-x^-$$ 转化为线性规划，则转化后的目标函数为",
    "options": ["A", "B"]
  }
]
'''
    print("--- Original String ---")
    print(problematic_json)
    
    print("\n--- Repairing ---")
    repaired = repair_json_string(problematic_json)
    print(repaired)
    
    print("\n--- Parsing ---")
    try:
        data = json.loads(repaired)
        print("Success!")
    except json.JSONDecodeError as e:
        print(f"Failed: {e}")

    # Let's also test the regex specifically on the substring
    print("\n--- Regex Debug ---")
    pattern = r'\\(?!(["\\/nrt]|u[0-9a-fA-F]{4}))'
    test_sub = r'$$\min'
    print(f"Testing substring: '{test_sub}'")
    sub_repaired = re.sub(pattern, r'\\\\', test_sub)
    print(f"Repaired substring: '{sub_repaired}'")

if __name__ == "__main__":
    test_specific_failure()
