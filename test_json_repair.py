
from llm.prompts import parse_llm_response, repair_json_string
import json

def test_json_repair():
    print("\n=== Testing JSON Repair ===")
    
    test_cases = [
        {
            "name": "Valid JSON",
            "input": '{"key": "value"}',
            "expected_success": True
        },
        {
            "name": "LaTeX with unescaped backslash (invalid JSON)",
            "input": r'{"formula": "x = \sigma"}',
            "expected_success": True,
            "check": lambda x: "\\sigma" in x['formula']
        },
        {
            "name": "LaTeX with multiple unescaped backslashes",
            "input": r'{"formula": "\min_{x} \ell_1"}',
            "expected_success": True,
            "check": lambda x: "\\min" in x['formula'] and "\\ell" in x['formula']
        },
        {
            "name": "Valid escaped backslash",
            "input": r'{"path": "C:\\Windows\\System32"}',
            "expected_success": True,
            "check": lambda x: "\\" in x['path']
        },
        {
            "name": "Valid control characters",
            "input": '{"text": "Line 1\\nLine 2\\tTabbed"}',
            "expected_success": True
        },
        {
            "name": "Mixed valid and invalid",
            "input": r'{"text": "Valid: \n, Invalid: \ell"}',
            "expected_success": True
        },
        {
            "name": "Unicode escape",
            "input": '{"char": "\\u0041"}',
            "expected_success": True,
            "check": lambda x: x['char'] == 'A'
        }
    ]
    
    for case in test_cases:
        print(f"\nTesting: {case['name']}")
        try:
            # We use parse_llm_response logic directly or call repair_json_string
            # Since parse_llm_response expects a list, we'll wrap inputs in []
            wrapped_input = f"[{case['input']}]"
            result = parse_llm_response(wrapped_input)
            
            if case['expected_success']:
                print("PASS: Parsed successfully")
                if 'check' in case:
                    if case['check'](result[0]):
                        print("PASS: Content verification succeeded")
                    else:
                        print("FAIL: Content verification failed")
                        print(f"Actual result: {result[0]}")
                        raise Exception("Content verification failed")
            else:
                print("FAIL: Should have failed but succeeded")
                
        except Exception as e:
            if not case['expected_success']:
                print(f"PASS: Failed as expected ({e})")
            else:
                print(f"FAIL: Unexpected error: {e}")
                raise e

if __name__ == "__main__":
    try:
        test_json_repair()
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nTest failed: {e}")
