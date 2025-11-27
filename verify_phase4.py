import inspect
from llm.agents import multi_agent_generator
from llm import prompts

def verify():
    print("Verifying Phase 4 changes...")
    
    # Check run_workflow signature
    sig = inspect.signature(multi_agent_generator.run_workflow)
    params = sig.parameters
    if 'exercise_type' in params and 'language' in params:
        print("SUCCESS: run_workflow accepts exercise_type and language.")
    else:
        print("FAILURE: run_workflow missing parameters.")
        
    # Check generate_initial_items signature
    sig = inspect.signature(multi_agent_generator.generate_initial_items)
    params = sig.parameters
    if 'exercise_type' in params and 'language' in params:
        print("SUCCESS: generate_initial_items accepts exercise_type and language.")
    else:
        print("FAILURE: generate_initial_items missing parameters.")
        
    # Check get_exercise_prompt logic (mocking)
    template_without_placeholder = "Some template content."
    formatted = prompts.get_exercise_prompt("Title", "Content", custom_template=template_without_placeholder, language='en')
    if "Please generate in English" in formatted:
        print("SUCCESS: get_exercise_prompt auto-appends language instruction.")
    else:
        print("FAILURE: get_exercise_prompt failed to append instruction.")
        
    print("Verification complete.")

if __name__ == '__main__':
    verify()
