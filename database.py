"""
Database utilities for the Intelligent Textbook Corpus Generation Platform
Provides connection management, query helpers, and schema initialization
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any
import config


class Database:
    """Database manager for SQLite operations"""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DATABASE_PATH
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database schema from schema.sql"""
        schema_path = Path(__file__).parent / 'schema.sql'
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        with self.get_connection() as conn:
            conn.executescript(schema_sql)
        
        print(f"Database initialized at {self.db_path}")
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a SELECT query and return results as list of dicts"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.rowcount
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT query and return the last inserted row ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid
    
    def get_book_by_id(self, book_id: int) -> Optional[Dict]:
        """Get book by ID"""
        results = self.execute_query(
            "SELECT * FROM books WHERE id = ?", (book_id,)
        )
        return results[0] if results else None
    
    def get_all_books(self) -> List[Dict]:
        """Get all books ordered by upload date"""
        return self.execute_query(
            "SELECT * FROM books ORDER BY upload_date DESC"
        )
    
    def create_book(self, title: str, source_file_path: str, **kwargs) -> int:
        """Create a new book record"""
        fields = ['title', 'source_file_path']
        values = [title, source_file_path]
        
        for key, value in kwargs.items():
            if value is not None:
                fields.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in values])
        query = f"INSERT INTO books ({', '.join(fields)}) VALUES ({placeholders})"
        
        return self.execute_insert(query, tuple(values))
    
    def update_book(self, book_id: int, **kwargs) -> int:
        """Update book fields"""
        if not kwargs:
            return 0
        
        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [book_id]
        
        query = f"UPDATE books SET {set_clause} WHERE id = ?"
        return self.execute_update(query, tuple(values))
    
    def get_chapters_by_book(self, book_id: int) -> List[Dict]:
        """Get all chapters for a book, ordered by order_index"""
        return self.execute_query(
            "SELECT * FROM chapters WHERE book_id = ? ORDER BY order_index",
            (book_id,)
        )
    
    def get_chapter_by_id(self, chapter_id: int) -> Optional[Dict]:
        """Get chapter by ID"""
        results = self.execute_query(
            "SELECT * FROM chapters WHERE id = ?", (chapter_id,)
        )
        return results[0] if results else None

    def get_chapters_by_ids(self, chapter_ids: List[int]) -> List[Dict]:
        """Get chapters by a list of IDs, preserving order"""
        if not chapter_ids:
            return []
            
        placeholders = ','.join(['?' for _ in chapter_ids])
        query = f"SELECT * FROM chapters WHERE id IN ({placeholders})"
        
        results = self.execute_query(query, tuple(chapter_ids))
        
        # Sort results to match input order
        results_map = {r['id']: dict(r) for r in results}
        ordered_results = []
        for cid in chapter_ids:
            if cid in results_map:
                ordered_results.append(results_map[cid])
                
        return ordered_results
    
    def create_chapter(self, book_id: int, title: str, order_index: int, **kwargs) -> int:
        """Create a new chapter"""
        fields = ['book_id', 'title', 'order_index']
        values = [book_id, title, order_index]
        
        for key, value in kwargs.items():
            if value is not None:
                fields.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in values])
        query = f"INSERT INTO chapters ({', '.join(fields)}) VALUES ({placeholders})"
        
        return self.execute_insert(query, tuple(values))
    
    def update_chapter(self, chapter_id: int, **kwargs) -> int:
        """Update chapter fields"""
        if not kwargs:
            return 0
        
        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [chapter_id]
        
        query = f"UPDATE chapters SET {set_clause} WHERE id = ?"
        return self.execute_update(query, tuple(values))
    
    def get_generated_content_by_chapter(self, chapter_id: int) -> List[Dict]:
        """Get all generated content for a chapter"""
        return self.execute_query(
            "SELECT * FROM generated_content WHERE chapter_id = ? ORDER BY created_at",
            (chapter_id,)
        )
    
    def create_generated_content(self, chapter_id: int, content_type: str, 
                                question: str, answer: str, model_name: str, **kwargs) -> int:
        """Create new generated content"""
        fields = ['chapter_id', 'content_type', 'question', 'answer', 'model_name']
        values = [chapter_id, content_type, question, answer, model_name]
        
        for key, value in kwargs.items():
            if value is not None:
                fields.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in values])
        query = f"INSERT INTO generated_content ({', '.join(fields)}) VALUES ({placeholders})"
        
        return self.execute_insert(query, tuple(values))
    
    def update_generated_content(self, content_id: int, **kwargs) -> int:
        """Update generated content"""
        if not kwargs:
            return 0
        
        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [content_id]
        
        query = f"UPDATE generated_content SET {set_clause} WHERE id = ?"
        return self.execute_update(query, tuple(values))

    def delete_generated_content(self, content_id: int) -> int:
        """Delete generated content by ID"""
        return self.execute_update("DELETE FROM generated_content WHERE id = ?", (content_id,))
    
    def get_prompts(self, prompt_type: Optional[str] = None) -> List[Dict]:
        """Get prompt templates, optionally filtered by type"""
        if prompt_type:
            return self.execute_query(
                "SELECT * FROM llm_prompts WHERE prompt_type = ? ORDER BY created_at DESC",
                (prompt_type,)
            )
        return self.execute_query(
            "SELECT * FROM llm_prompts ORDER BY prompt_type, created_at DESC"
        )
    
    def get_user_preference(self, chapter_id: int) -> Optional[Dict]:
        """Get user preference for a chapter"""
        results = self.execute_query(
            "SELECT * FROM user_preferences WHERE chapter_id = ?",
            (chapter_id,)
        )
        return results[0] if results else None
    
    def upsert_user_preference(self, chapter_id: int, **kwargs) -> int:
        """Create or update user preference"""
        existing = self.get_user_preference(chapter_id)
        
        if existing:
            return self.execute_update(
                f"UPDATE user_preferences SET {', '.join([f'{k} = ?' for k in kwargs.keys()])} WHERE chapter_id = ?",
                tuple(list(kwargs.values()) + [chapter_id])
            )
        else:
            fields = ['chapter_id'] + list(kwargs.keys())
            values = [chapter_id] + list(kwargs.values())
            placeholders = ', '.join(['?' for _ in values])
            query = f"INSERT INTO user_preferences ({', '.join(fields)}) VALUES ({placeholders})"
            return self.execute_insert(query, tuple(values))
    
    def get_chapter_progress(self, chapter_id: int) -> Dict:
        """Get verification progress for a chapter"""
        query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'verified' THEN 1 ELSE 0 END) as verified
            FROM generated_content
            WHERE chapter_id = ?
        """
        result = self.execute_query(query, (chapter_id,))
        if not result:
            return {'total': 0, 'verified': 0, 'percentage': 0}
            
        total = result[0]['total']
        verified = result[0]['verified'] or 0
        percentage = (verified / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'verified': verified,
            'percentage': round(percentage, 1)
        }

    def get_book_progress(self, book_id: int) -> Dict:
        """Get verification progress for a book"""
        query = """
            SELECT 
                COUNT(gc.id) as total,
                SUM(CASE WHEN gc.status = 'verified' THEN 1 ELSE 0 END) as verified
            FROM generated_content gc
            JOIN chapters c ON gc.chapter_id = c.id
            WHERE c.book_id = ?
        """
        result = self.execute_query(query, (book_id,))
        if not result:
            return {'total': 0, 'verified': 0, 'percentage': 0}
            
        total = result[0]['total']
        verified = result[0]['verified'] or 0
        percentage = (verified / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'verified': verified,
            'percentage': round(percentage, 1)
        }
    
    def create_parse_task(self, book_id: int, task_id: str) -> int:
        """Create a new parse task"""
        return self.execute_insert(
            "INSERT INTO parse_tasks (book_id, task_id) VALUES (?, ?)",
            (book_id, task_id)
        )
    
    def update_parse_task(self, task_id: str, **kwargs) -> int:
        """Update parse task status"""
        if not kwargs:
            return 0
        
        set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [task_id]
        
        query = f"UPDATE parse_tasks SET {set_clause} WHERE task_id = ?"
        return self.execute_update(query, tuple(values))
    
    def get_parse_task(self, task_id: str) -> Optional[Dict]:
        """Get parse task by task_id"""
        results = self.execute_query(
            "SELECT * FROM parse_tasks WHERE task_id = ?",
            (task_id,)
        )
        return results[0] if results else None

    def search_generated_content(self, book_id: int, chapter_ids: List[int] = None, 
                               content_type: str = None, status: str = None, 
                               keyword: str = None) -> List[Dict]:
        """Search generated content with filters"""
        query = """
            SELECT gc.*, c.title as chapter_title 
            FROM generated_content gc
            JOIN chapters c ON gc.chapter_id = c.id
            WHERE c.book_id = ?
        """
        params = [book_id]
        
        if chapter_ids:
            placeholders = ','.join(['?' for _ in chapter_ids])
            query += f" AND gc.chapter_id IN ({placeholders})"
            params.extend(chapter_ids)
            
        if content_type:
            query += " AND gc.content_type = ?"
            params.append(content_type)
            
        if status:
            query += " AND gc.status = ?"
            params.append(status)
            
        if keyword:
            query += " AND (gc.question LIKE ? OR gc.answer LIKE ?)"
            keyword_param = f"%{keyword}%"
            params.extend([keyword_param, keyword_param])
            
        query += " ORDER BY c.order_index, gc.created_at DESC"
        
        return self.execute_query(query, tuple(params))

    def get_content_by_ids(self, content_ids: List[int]) -> List[Dict]:
        """Get generated content by a list of IDs"""
        if not content_ids:
            return []
            
        placeholders = ','.join(['?' for _ in content_ids])
        query = f"""
            SELECT gc.*, c.title as chapter_title 
            FROM generated_content gc
            JOIN chapters c ON gc.chapter_id = c.id
            WHERE gc.id IN ({placeholders})
            ORDER BY c.order_index, gc.created_at DESC
        """
        
        return self.execute_query(query, tuple(content_ids))
    
    # ============= Prompt Management =============
    
    def get_custom_prompt(self, prompt_type: str) -> Optional[Dict]:
        """Get the most recent custom prompt for a given type (qa or exercise)"""
        results = self.execute_query(
            """SELECT * FROM llm_prompts 
               WHERE prompt_type = ? AND is_global = 1 
               ORDER BY created_at DESC 
               LIMIT 1""",
            (prompt_type,)
        )
        return dict(results[0]) if results else None
    
    def get_all_prompts(self, prompt_type: Optional[str] = None) -> List[Dict]:
        """Get all prompt templates, optionally filtered by type"""
        if prompt_type:
            return self.execute_query(
                "SELECT * FROM llm_prompts WHERE prompt_type = ? ORDER BY created_at DESC",
                (prompt_type,)
            )
        else:
            return self.execute_query(
                "SELECT * FROM llm_prompts ORDER BY prompt_type, created_at DESC"
            )
    
    def update_prompt(self, prompt_id: int, content: str) -> bool:
        """Update a prompt template"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE llm_prompts SET content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (content, prompt_id)
            )
            return cursor.rowcount > 0
    
    def create_prompt(self, prompt_type: str, name: str, content: str, is_global: bool = True) -> int:
        """Create a new prompt template"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO llm_prompts (prompt_type, name, content, is_global) 
                   VALUES (?, ?, ?, ?)""",
                (prompt_type, name, content, 1 if is_global else 0)
            )
            return cursor.lastrowid
    
    # ============= Generated Content Management =============
    
    def add_generated_content(self, chapter_id: int, content_type: str, question: str, 
                             answer: str, explanation: str = None, options_json: str = None,
                             model_name: str = 'deepseek-chat') -> int:
        """Add a generated content item (QA or exercise)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO generated_content 
                   (chapter_id, content_type, question, options_json, answer, explanation, model_name, status) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'generated')""",
                (chapter_id, content_type, question, options_json, answer, explanation, model_name)
            )
            return cursor.lastrowid




# Global database instance
db = Database()


def init_database():
    """Initialize the database (call this on app startup)"""
    db.init_db()
    return db
