"""
Test script to verify basic functionality
"""

import sys
import os

# Test imports
print("Testing imports...")
try:
    import flask
    print("✓ Flask imported successfully")
except ImportError as e:
    print(f"✗ Failed to import Flask: {e}")
    sys.exit(1)

try:
    import config
    print("✓ Config module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import config: {e}")
    sys.exit(1)

try:
    from database import db, init_database
    print("✓ Database module imported successfully")
except ImportError as e:
    print(f"✗ Failed to import database: {e}")
    sys.exit(1)

try:
    from llm.router import llm_router
    print("✓ LLM router imported successfully")
except ImportError as e:
    print(f"✗ Failed to import LLM router: {e}")
    sys.exit(1)

try:
    from parsers.chapter_parser import chapter_parser
    print("✓ Chapter parser imported successfully")
except ImportError as e:
    print(f"✗ Failed to import chapter parser: {e}")
    sys.exit(1)

try:
    from exporters.excel_exporter import excel_exporter
    print("✓ Excel exporter imported successfully")
except ImportError as e:
    print(f"✗ Failed to import excel exporter: {e}")
    sys.exit(1)

# Test database initialization
print("\nTesting database initialization...")
try:
    init_database()
    print("✓ Database initialized successfully")
    print(f"  Database location: {config.DATABASE_PATH}")
except Exception as e:
    print(f"✗ Failed to initialize database: {e}")
    sys.exit(1)

# Test database operations
print("\nTesting database operations...")
try:
    # Test creating a book
    book_id = db.create_book(
        title="Test Book",
        source_file_path="/tmp/test.pdf"
    )
    print(f"✓ Created test book with ID: {book_id}")
    
    # Test retrieving the book
    book = db.get_book_by_id(book_id)
    if book and book['title'] == "Test Book":
        print("✓ Retrieved book successfully")
    else:
        print("✗ Failed to retrieve book")
        sys.exit(1)
    
    # Test updating the book
    db.update_book(book_id, author="Test Author")
    book = db.get_book_by_id(book_id)
    if book['author'] == "Test Author":
        print("✓ Updated book successfully")
    else:
        print("✗ Failed to update book")
        sys.exit(1)
    
except Exception as e:
    print(f"✗ Database operation failed: {e}")
    sys.exit(1)

# Test available models
print("\nChecking available LLM models...")
try:
    models = llm_router.get_available_models()
    if models:
        print(f"✓ Found {len(models)} available models:")
        for model in models:
            print(f"  - {model['name']} ({model['id']})")
    else:
        print("⚠ No LLM models configured (API keys not set)")
        print("  This is normal if you haven't set up .env file yet")
except Exception as e:
    print(f"✗ Failed to check models: {e}")

# Test token counting
print("\nTesting token counting...")
try:
    test_text = "This is a test sentence with some mathematical formula: $x^2 + y^2 = r^2$"
    token_count = chapter_parser.count_tokens(test_text)
    print(f"✓ Token counting works ('{test_text}' = {token_count} tokens)")
except Exception as e:
    print(f"✗ Token counting failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "="*50)
print("✓ All basic tests passed!")
print("="*50)
print("\nNext steps:")
print("1. Copy .env.example to .env and add your API keys")
print("2. Run: python app.py")
print("3. Open: http://localhost:5000")
print("\nFor more information, see README.md")
