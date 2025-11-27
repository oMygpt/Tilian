
import re

def test_regex():
    # Aggressive regex: Escape EVERYTHING except ", \, /, and uXXXX
    # This means \n becomes \\n, \t becomes \\t
    pattern = r'\\(?!(["\\/]|u[0-9a-fA-F]{4}))'
    
    test_cases = [
        (r'{"x": "\min"}', r'{"x": "\\min"}'),
        (r'{"x": "\text"}', r'{"x": "\\text"}'),
        (r'{"x": "\n"}', r'{"x": "\\n"}'),
        (r'{"x": "\\"}', r'{"x": "\\"}'),
        (r'{"x": "\""}', r'{"x": "\""}'),
        (r'{"x": "\u1234"}', r'{"x": "\u1234"}'),
        (r'{"x": "\u123"}', r'{"x": "\\u123"}'),
    ]
    
    for original, expected in test_cases:
        repaired = re.sub(pattern, r'\\\\', original)
        print(f"Original: {original}")
        print(f"Repaired: {repaired}")
        if repaired == expected:
            print("PASS")
        else:
            print(f"FAIL. Expected: {expected}")
            
if __name__ == "__main__":
    test_regex()
