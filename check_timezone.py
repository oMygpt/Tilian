
from database import db, init_database
from datetime import datetime
import time

# Initialize database
init_database()

def check_timezone():
    print(f"Local time: {datetime.now()}")
    
    # Insert a dummy generated content
    # We need a valid chapter_id. Let's assume chapter 1 exists or create a dummy one if needed.
    # For safety, let's just try to insert with chapter_id=1 (FK constraint might fail if empty db)
    # But usually there is data. If not, we'll catch error.
    
    try:
        # Check if any chapter exists
        chapters = db.execute_query("SELECT id FROM chapters LIMIT 1")
        if not chapters:
            print("No chapters found. Creating a dummy book and chapter...")
            book_id = db.create_book("Dummy Book", "dummy.pdf")
            chapter_id = db.create_chapter(book_id, "Dummy Chapter", 1)
        else:
            chapter_id = chapters[0]['id']
            
        print(f"Using chapter_id: {chapter_id}")
        
        # Insert content
        content_id = db.add_generated_content(
            chapter_id=chapter_id,
            content_type='qa',
            question='Timezone Test',
            answer='Test',
            model_name='test'
        )
        
        # Fetch it back
        result = db.execute_query("SELECT created_at FROM generated_content WHERE id = ?", (content_id,))
        db_time_str = result[0]['created_at']
        print(f"DB stored time: {db_time_str}")
        
        # Compare
        local_now = datetime.now()
        try:
            db_time = datetime.strptime(db_time_str, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            db_time = datetime.strptime(db_time_str, "%Y-%m-%d %H:%M:%S")
        
        diff = abs((local_now - db_time).total_seconds())
        print(f"Difference in seconds: {diff}")
        
        if diff > 300: # > 5 minutes difference likely means timezone mismatch (e.g. 8 hours)
            print("FAIL: Significant time difference detected (likely UTC vs Local)")
        else:
            print("PASS: Time difference is small (Local time used)")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_timezone()
