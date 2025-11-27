
from database import db, init_database
import os

# Initialize database
init_database()

try:
    # Attempt to call save_prompt which should fail
    print("Attempting to call db.save_prompt...")
    db.save_prompt('qa', 'Test QA Prompt', 'Test Content')
    print("Success! (Unexpected)")
except AttributeError as e:
    print(f"Caught expected error: {e}")
except Exception as e:
    print(f"Caught unexpected error: {e}")
