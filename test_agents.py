
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from llm.agents import multi_agent_generator

def test_workflow():
    print("Testing Multi-Agent Workflow...")
    
    # Mock content
    content = """
    Artificial Intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by animals including humans.
    Leading AI textbooks define the field as the study of "intelligent agents": any system that perceives its environment and takes actions that maximize its chance of achieving its goals.
    Some popular accounts use the term "artificial intelligence" to describe machines that mimic "cognitive" functions that humans associate with the human mind, such as "learning" and "problem solving".
    
    Key concepts include:
    1. Machine Learning: A subset of AI that focuses on the development of algorithms that allow computers to learn from and make predictions or decisions based on data.
    2. Neural Networks: Computing systems vaguely inspired by the biological neural networks that constitute animal brains.
    3. Deep Learning: A class of machine learning algorithms that uses multiple layers to progressively extract higher-level features from the raw input.
    """
    
    print("\n--- Testing QA Generation ---")
    try:
        qa_items = multi_agent_generator.run_workflow(content, count=2, item_type='qa')
        print(f"Generated {len(qa_items)} QA items")
        print(json.dumps(qa_items, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"QA Generation Failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Testing Exercise Generation ---")
    try:
        ex_items = multi_agent_generator.run_workflow(content, count=2, item_type='exercise')
        print(f"Generated {len(ex_items)} Exercise items")
        print(json.dumps(ex_items, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Exercise Generation Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_workflow()
