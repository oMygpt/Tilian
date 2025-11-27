
from database import db, init_database
import time

# Initialize database
init_database()

def test_save_prompt():
    print("\n=== Testing Save Prompt ===")
    
    # 1. Test creating a new prompt
    print("\n1. Testing creation of new prompt...")
    unique_name = f"Test Prompt {int(time.time())}"
    prompt_id = db.save_prompt('test_type', unique_name, 'Test Content')
    print(f"Created prompt with ID: {prompt_id}")
    
    # Verify it exists
    prompt = db.get_custom_prompt('test_type')
    assert prompt is not None
    assert prompt['name'] == unique_name
    assert prompt['content'] == 'Test Content'
    print("Creation verification passed!")
    
    # 2. Test updating an existing prompt
    print("\n2. Testing update of existing prompt...")
    new_content = 'Updated Test Content'
    new_name = f"{unique_name} Updated"
    
    updated_id = db.save_prompt('test_type', new_name, new_content)
    print(f"Updated prompt with ID: {updated_id}")
    
    # Verify updates
    updated_prompt = db.get_custom_prompt('test_type')
    assert updated_prompt['id'] == prompt_id  # Should be same ID
    assert updated_prompt['content'] == new_content
    assert updated_prompt['name'] == new_name
    print("Update verification passed!")

    # 3. Test specific exercise type
    print("\n3. Testing specific exercise type...")
    ex_type = 'exercise_single_choice'
    ex_name = 'Single Choice Template'
    ex_content = 'SC Content'
    
    ex_id = db.save_prompt(ex_type, ex_name, ex_content)
    print(f"Created exercise prompt with ID: {ex_id}")
    
    # Verify
    ex_prompt = db.get_custom_prompt(ex_type)
    assert ex_prompt is not None
    assert ex_prompt['content'] == ex_content
    print("Exercise type verification passed!")

if __name__ == "__main__":
    try:
        test_save_prompt()
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
