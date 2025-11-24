
import sys
import os
import uuid

# Add project root to path
sys.path.append(os.getcwd())

from database import db
from llm.agents import multi_agent_generator

def test_agent_model_selection():
    print("Testing Multi-Agent Model Selection...")
    
    # Mock data
    workflow_id = str(uuid.uuid4())
    chapter_id = 999
    content = "Test content."
    target_model = "doubao-thinking"
    
    # Mock LLM client
    original_generate = multi_agent_generator.client.generate_text
    
    # Capture used model
    used_models = []
    
    def mock_generate(prompt, provider_id=None, **kwargs):
        used_models.append(provider_id)
        if "Analyze" in prompt:
            return '[{"Topic": "Test", "Key_Concepts": ["C"], "Source_Text": "S"}]'
        elif "Generate" in prompt:
            return '[{"question": "Q", "answer": "A", "explanation": "E"}]'
        elif "Review" in prompt:
            return '[]'
        elif "Refine" in prompt:
            return '{}'
        return "{}"
        
    multi_agent_generator.client.generate_text = mock_generate
    
    try:
        # Run workflow with specific model
        print(f"Running workflow with model: {target_model}")
        multi_agent_generator.run_workflow(content, 1, 'qa', workflow_id, chapter_id, model_id=target_model)
        
        # Verify
        print(f"Used models: {used_models}")
        if all(m == target_model for m in used_models):
            print("SUCCESS: All agents used the target model.")
        else:
            print("FAILED: Some agents did not use the target model.")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        multi_agent_generator.client.generate_text = original_generate

if __name__ == "__main__":
    test_agent_model_selection()
