"""
Main Flask Application
Intelligent Textbook Corpus Generation Platform
"""

import os
import json
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename

import config
from database import db, init_database
from parsers.mineru_client import mineru_client
from parsers.metadata_extractor import extract_metadata_from_json, extract_metadata_from_md, merge_metadata
from parsers.chapter_parser import chapter_parser
from llm.router import llm_router
from llm.prompts import get_qa_prompt, get_exercise_prompt, parse_llm_response, validate_qa_item, validate_exercise_item
from exporters.excel_exporter import excel_exporter

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_SIZE

# Initialize database on startup
with app.app_context():
    try:
        init_database()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


# ============= Upload & Parsing Routes =============

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle PDF file upload"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        file_path = config.UPLOAD_DIR / filename
        file.save(file_path)
        
        # Check file size
        if not mineru_client.check_file_size(file_path):
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            return jsonify({
                'error': f'File too large ({file_size_mb:.2f} MB). Maximum: {config.MINERU_MAX_FILE_SIZE} MB',
                'requires_split': True
            }), 400
        
        # Create book record
        book_id = db.create_book(
            title=filename.rsplit('.', 1)[0],
            source_file_path=str(file_path),
            status='uploaded'
        )
        
        return jsonify({
            'success': True,
            'book_id': book_id,
            'filename': filename
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/parse', methods=['POST'])
def start_parsing():
    """Start PDF parsing with MinerU"""
    data = request.json
    book_id = data.get('book_id')
    
    if not book_id:
        return jsonify({'error': 'book_id required'}), 400
    
    book = db.get_book_by_id(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    try:
        # Update book status
        db.update_book(book_id, status='parsing')
        
        # Start async parsing
        file_path = Path(book['source_file_path'])
        batch_id, _, _ = mineru_client.parse_pdf(file_path)
        
        # Create parse task record
        db.create_parse_task(book_id, batch_id)
        
        # Start background thread to monitor parsing
        threading.Thread(
            target=monitor_parsing_task,
            args=(batch_id, book_id)
        ).start()
        
        return jsonify({
            'success': True,
            'task_id': batch_id  # Actually batch_id, kept as task_id for API compatibility
        })
    
    except Exception as e:
        db.update_book(book_id, status='error', error_message=str(e))
        return jsonify({'error': str(e)}), 500


def monitor_parsing_task(task_id: str, book_id: int):
    """Background task to monitor MinerU parsing"""
    try:
        # Wait for completion
        success = mineru_client.wait_for_completion(task_id)
        
        if success:
            # Download results
            output_dir = config.PARSED_DIR / str(book_id)
            json_path, md_path = mineru_client.download_results(task_id, output_dir)
            
            if json_path and md_path:
                # Extract metadata
                json_meta = extract_metadata_from_json(json_path)
                md_meta = extract_metadata_from_md(md_path)
                
                book = db.get_book_by_id(book_id)
                merged_meta = merge_metadata(json_meta, md_meta, book['source_file_path'])
                
                # Update book with metadata and paths
                db.update_book(
                    book_id,
                    status='parsed',
                    parsed_json_path=str(json_path),
                    parsed_md_path=str(md_path),
                    **merged_meta
                )
                
                # Parse chapters
                chapters = chapter_parser.parse_chapters_from_json(json_path)
                
                # Save chapters to database
                for chapter in chapters:
                    db.create_chapter(
                        book_id=book_id,
                        title=chapter['title'],
                        content_md=chapter['content'],
                        token_count=chapter['token_count'],
                        order_index=chapter['order'],
                        level=chapter['level']
                    )
                
                db.update_parse_task(task_id, status='completed', progress=100)
            else:
                raise Exception("Failed to download parsing results")
        else:
            raise Exception("Parsing failed or timed out")
    
    except Exception as e:
        db.update_book(book_id, status='error', error_message=str(e))
        db.update_parse_task(task_id, status='failed', error_message=str(e))


@app.route('/api/parse/status/<task_id>', methods=['GET'])
def get_parse_status(task_id):
    """Get parsing status"""
    task = db.get_parse_task(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    return jsonify({
        'status': task['status'],
        'progress': task.get('progress', 0),
        'error': task.get('error_message')
    })


@app.route('/api/metadata/confirm', methods=['POST'])
def confirm_metadata():
    """Confirm and update book metadata"""
    data = request.json
    book_id = data.get('book_id')
    
    if not book_id:
        return jsonify({'error': 'book_id required'}), 400
    
    # Update metadata fields
    update_fields = {}
    for field in ['title', 'author', 'isbn', 'publisher', 'publish_year']:
        if field in data:
            update_fields[field] = data[field]
    
    if update_fields:
        db.update_book(book_id, **update_fields)
    
    return jsonify({'success': True})


# ============= Chapter Management Routes =============

@app.route('/api/books/<int:book_id>/chapters', methods=['GET'])
def get_book_chapters(book_id):
    """Get all chapters for a book"""
    chapters = db.get_chapters_by_book(book_id)
    return jsonify(chapters)


@app.route('/api/chapters/<int:chapter_id>', methods=['GET'])
def get_chapter(chapter_id):
    """Get specific chapter content"""
    chapter = db.get_chapter_by_id(chapter_id)
    
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    return jsonify(chapter)


@app.route('/api/chapters/<int:chapter_id>/split', methods=['POST'])
def split_chapter(chapter_id):
    """Split a chapter into smaller chunks based on token limits"""
    data = request.json
    model_id = data.get('model', 'chatgpt')
    
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    try:
        # Get token limit for the selected model
        max_tokens = config.LLM_MODELS.get(model_id, {}).get('max_tokens', 32768)
        threshold = int(max_tokens * config.TOKEN_THRESHOLD_PERCENTAGE)
        
        # Check if chapter actually needs splitting
        if chapter['token_count'] <= threshold:
            return jsonify({
                'error': f'Chapter has {chapter["token_count"]} tokens, below threshold of {threshold}',
                'needs_split': False
            }), 400
        
        # Split the chapter
        chapter_dict = {
            'title': chapter['title'],
            'content': chapter['content_md'],
            'level': chapter['level'],
            'order': chapter['order_index'],
            'chapter_num': None,
            'token_count': chapter['token_count']
        }
        
        chunks = chapter_parser.split_large_chapter(chapter_dict, threshold)
        
        if len(chunks) <= 1:
            return jsonify({'error': 'Unable to split chapter effectively'}), 400
        
        # Save chunks as new chapters
        book_id = chapter['book_id']
        new_chapter_ids = []
        
        for chunk in chunks:
            new_id = db.create_chapter(
                book_id=book_id,
                title=chunk['title'],
                content_md=chunk['content'],
                token_count=chunk['token_count'],
                order_index=chunk['order'],
                level=chapter['level']
            )
            new_chapter_ids.append(new_id)
        
        # Delete original chapter
        db.execute_update("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        
        return jsonify({
            'success': True,
            'original_tokens': chapter['token_count'],
            'chunk_count': len(chunks),
            'new_chapter_ids': new_chapter_ids
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ============= Content Generation Routes =============

@app.route('/api/generate/qa', methods=['POST'])
def generate_qa():
    """Generate Q&A pairs for a chapter"""
    data = request.json
    chapter_id = data.get('chapter_id')
    model_id = data.get('model', 'chatgpt')
    custom_prompt = data.get('custom_prompt')
    
    if not chapter_id:
        return jsonify({'error': 'chapter_id required'}), 400
    
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    try:
        # Get prompt
        prompt = get_qa_prompt(
            chapter['title'],
            chapter['content_md'],
            custom_prompt
        )
        
        # Generate content
        response = llm_router.generate(model_id, prompt)
        
        # Parse response
        items = parse_llm_response(response)
        
        # Save to database
        saved_ids = []
        for item in items:
            if validate_qa_item(item):
                content_id = db.create_generated_content(
                    chapter_id=chapter_id,
                    content_type='qa',
                    question=item['question'],
                    answer=item['answer'],
                    explanation=item.get('explanation', ''),
                    model_name=model_id,
                    status='generated'
                )
                saved_ids.append(content_id)
        
        return jsonify({
            'success': True,
            'generated_count': len(saved_ids),
            'ids': saved_ids
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate/exercise', methods=['POST'])
def generate_exercise():
    """Generate exercises for a chapter"""
    data = request.json
    chapter_id = data.get('chapter_id')
    model_id = data.get('model', 'chatgpt')
    custom_prompt = data.get('custom_prompt')
    
    if not chapter_id:
        return jsonify({'error': 'chapter_id required'}), 400
    
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    try:
        # Get prompt
        prompt = get_exercise_prompt(
            chapter['title'],
            chapter['content_md'],
            custom_prompt
        )
        
        # Generate content
        response = llm_router.generate(model_id, prompt)
        
        # Parse response
        items = parse_llm_response(response)
        
        # Save to database
        saved_ids = []
        for item in items:
            if validate_exercise_item(item):
                # Serialize options for choice questions
                options_json = None
                if item['type'] == 'choice' and 'options' in item:
                    options_json = json.dumps(item['options'], ensure_ascii=False)
                
                content_id = db.create_generated_content(
                    chapter_id=chapter_id,
                    content_type='exercise',
                    question=item['question'],
                    answer=item['answer'],
                    explanation=item.get('explanation', ''),
                    options_json=options_json,
                    model_name=model_id,
                    status='generated'
                )
                saved_ids.append(content_id)
        
        return jsonify({
            'success': True,
            'generated_count': len(saved_ids),
            'ids': saved_ids
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    """Get prompt templates"""
    prompt_type = request.args.get('type')
    prompts = db.get_prompts(prompt_type)
    return jsonify(prompts)


@app.route('/api/prompts/<int:prompt_id>', methods=['PUT'])
def update_prompt(prompt_id):
    """Update prompt template"""
    # For simplicity, we'll create a new version instead of updating
    # This preserves history
    data = request.json
    
    # Implementation would create new prompt version
    # For now, return success
    return jsonify({'success': True})


# ============= Verification Routes =============

@app.route('/api/content/<int:content_id>', methods=['GET'])
def get_content(content_id):
    """Get generated content by ID"""
    content = db.execute_query(
        "SELECT * FROM generated_content WHERE id = ?",
        (content_id,)
    )
    
    if not content:
        return jsonify({'error': 'Content not found'}), 404
    
    return jsonify(content[0])


@app.route('/api/content/<int:content_id>', methods=['PUT'])
def update_content(content_id):
    """Update generated content"""
    data = request.json
    
    update_fields = {}
    for field in ['question', 'answer', 'explanation', 'options_json']:
        if field in data:
            update_fields[field] = data[field]
    
    if update_fields:
        db.update_generated_content(content_id, **update_fields)
    
    return jsonify({'success': True})


@app.route('/api/content/<int:content_id>/verify', methods=['POST'])
def verify_content(content_id):
    """Mark content as verified"""
    db.update_generated_content(
        content_id,
        status='verified',
        verified_at=datetime.now().isoformat()
    )
    
    return jsonify({'success': True})


@app.route('/api/chapters/<int:chapter_id>/progress', methods=['GET'])
def get_chapter_progress(chapter_id):
    """Get verification progress for a chapter"""
    progress = db.get_chapter_progress(chapter_id)
    return jsonify(progress)


@app.route('/api/chapters/<int:chapter_id>/content', methods=['GET'])
def get_chapter_content(chapter_id):
    """Get all generated content for a chapter"""
    content = db.get_generated_content_by_chapter(chapter_id)
    return jsonify(content)


# ============= Export Routes =============

@app.route('/api/export/book/<int:book_id>', methods=['GET'])
def export_book(book_id):
    """Export book to Excel/CSV"""
    format_type = request.args.get('format', 'excel')
    
    try:
        if format_type == 'csv':
            output_path = excel_exporter.export_to_csv(book_id)
        else:
            output_path = excel_exporter.export_book(book_id)
        
        directory = output_path.parent
        filename = output_path.name
        
        return send_from_directory(
            directory,
            filename,
            as_attachment=True
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============= Book Management Routes =============

@app.route('/api/books', methods=['GET'])
def get_books():
    """Get all books"""
    books = db.get_all_books()
    return jsonify(books)


@app.route('/api/books/<int:book_id>', methods=['GET', 'PUT', 'DELETE'])
def get_book(book_id):
    """Get specific book"""
    book = db.get_book_by_id(book_id)
    
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    return jsonify(book)


@app.route('/api/books/<int:book_id>/edit', methods=['PUT'])
def update_book_info(book_id):
    """Update book metadata"""
    book = db.get_book_by_id(book_id)
    
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    data = request.json
    
    # Update metadata fields
    update_fields = {}
    for field in ['title', 'author', 'isbn', 'publisher', 'publish_year']:
        if field in data:
            update_fields[field] = data[field]
    
    if update_fields:
        db.update_book(book_id, **update_fields)
    
    return jsonify({'success': True})


@app.route('/api/books/<int:book_id>/delete', methods=['DELETE'])
def delete_book(book_id):
    """Delete a book and all associated data"""
    book = db.get_book_by_id(book_id)
    
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    try:
        # Delete from database (CASCADE will handle chapters and content)
        db.execute_update("DELETE FROM books WHERE id = ?", (book_id,))
        
        # Optionally delete uploaded files
        import os
        import shutil
        
        if book.get('source_file_path') and os.path.exists(book['source_file_path']):
            try:
                os.remove(book['source_file_path'])
            except:
                pass
        
        # Delete parsed files directory
        parsed_dir = config.PARSED_DIR / str(book_id)
        if parsed_dir.exists():
            try:
                shutil.rmtree(parsed_dir)
            except:
                pass
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/models', methods=['GET'])
def get_available_models():
    """Get available LLM models"""
    models = llm_router.get_available_models()
    return jsonify(models)


# ============= Frontend Routes =============

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')


@app.route('/reading/<int:book_id>')
def reading_workbench(book_id):
    """Reading workbench page"""
    return render_template('reading.html', book_id=book_id)


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)


if __name__ == '__main__':
    # Validate configuration before starting
    try:
        config.validate_config()
        print("Configuration validated successfully")
        print(f"Available models: {config.get_available_models()}")
    except ValueError as e:
        print(f"Configuration error: {e}")
        exit(1)
    
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=config.DEBUG
    )
