"""
Main Flask Application
Intelligent Textbook Corpus Generation Platform
"""

import os
import json
import threading
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, Response
from werkzeug.utils import secure_filename

import config
from database import db, init_database
from parsers.mineru_client import mineru_client
from parsers.metadata_extractor import extract_metadata_from_json, extract_metadata_from_md, merge_metadata
from parsers.chapter_parser import chapter_parser
from llm import prompts
from llm.router import llm_router, llm_client
from exporters.excel_exporter import excel_exporter

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_SIZE

# Initialize Babel for i18n
from flask_babel import Babel, gettext as _
from flask import session, redirect, url_for

def get_locale():
    # 1. Check if language is explicitly set in session
    if 'lang' in session:
        return session['lang']
    # 2. Check if language is set in cookie (optional, but session is usually enough)
    # 3. Best match from request headers
    return request.accept_languages.best_match(['zh', 'en'])

babel = Babel(app, locale_selector=get_locale)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['zh', 'en']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

def get_js_translations():
    """Return a dictionary of translations for JavaScript"""
    return {
        # General
        'error': _('错误'),
        'success': _('成功'),
        'loading': _('加载中...'),
        'confirm': _('确认'),
        'cancel': _('取消'),
        
        # Upload
        'upload_failed': _('上传失败'),
        'upload_success': _('上传成功'),
        'parsing_started': _('解析任务已开始'),
        
        # Reading
        'select_chapter': _('请选择一个章节'),
        'chapter_tokens': _('当前章节: {tokens} tokens'),
        'generate_success': _('生成任务已提交'),
        'copy_success': _('复制成功'),
        'save_success': _('保存成功'),
        'no_content': _('暂无内容'),
        'generating': _('生成中...'),
        'verifying': _('校验中...'),
        'batch_progress': _('已完成 {done}/{total} 个章节'),
        'batch_complete': _('批量生成完成！'),
        'context_limit_warning': _('⚠️ 警告: 已选择 {count} 个章节，总计 {tokens} tokens。超过模型限制 ({limit})！'),
        'context_usage_safe': _('当前使用: {percent}% ({tokens}/{limit})'),
        
        # Content Manager
        'delete_confirm': _('确定要删除这条内容吗？'),
        'delete_success': _('删除成功'),
        'verify_success': _('校验状态已更新'),
        'export_success': _('导出成功'),
        'select_items': _('请先选择要导出的内容'),
        'no_items_found': _('未找到匹配的内容'),
    }

@app.context_processor
def inject_translations():
    return dict(js_translations=get_js_translations())

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
        # Check file size
        is_pdf = filename.lower().endswith('.pdf')
        if not is_pdf and not mineru_client.check_file_size(file_path):
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            return jsonify({
                'error': f'File too large ({file_size_mb:.2f} MB). Maximum: {config.MINERU_MAX_FILE_SIZE} MB',
                'requires_split': True
            }), 400
        
        # For PDF, we allow larger files as we'll split them
        if is_pdf and file_path.stat().st_size > config.MAX_UPLOAD_SIZE:
             return jsonify({
                'error': f'File too large. Maximum upload size: {config.MAX_UPLOAD_SIZE / (1024*1024)} MB'
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


from parsers.epub_parser import epub_parser
from parsers.docx_parser import docx_parser

@app.route('/api/parse', methods=['POST'])
def start_parsing():
    """Start parsing process (MinerU for PDF, direct for MD/TXT/EPUB/DOCX)"""
    data = request.json
    book_id = data.get('book_id')
    
    if not book_id:
        return jsonify({'error': 'book_id required'}), 400
    
    book = db.get_book_by_id(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    try:
        file_path = Path(book['source_file_path'])
        suffix = file_path.suffix.lower()
        
        # Update book status
        db.update_book(book_id, status='parsing')
        
        if suffix == '.pdf':
            # PDF: Use MinerU (Async)
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
                'task_id': batch_id
            })
            
        elif suffix in ['.md', '.txt', '.epub', '.docx']:
            # Direct parsing (Sync)
            import uuid
            task_id = str(uuid.uuid4().hex)
            
            # Create task record (marked as processing initially)
            db.create_parse_task(book_id, task_id)
            
            content_md = ""
            extracted_metadata = {}
            
            try:
                if suffix == '.epub':
                    content, metadata = epub_parser.parse(file_path)
                    content_md = content
                    extracted_metadata.update(metadata)
                    # Save intermediate MD file for consistency if needed later
                    md_path = file_path.with_suffix('.md')
                    with open(md_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    chapters = chapter_parser.parse_chapters_from_md(md_path)
                    
                else: # .txt
                    # Treat TXT as a single chapter or simple markdown
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Try parsing as MD first (in case it has headers)
                    chapters = chapter_parser.parse_chapters_from_md(file_path)
                    
                    if not chapters:
                        # Fallback: Single chapter
                        chapters = [{
                            'title': file_path.stem,
                            'content': content,
                            'level': 1,
                            'order': 0,
                            'token_count': chapter_parser.count_tokens(content)
                        }]
                
                # 2. Save chapters
                for chapter in chapters:
                    db.create_chapter(
                        book_id=book_id,
                        title=chapter['title'],
                        content_md=chapter['content'],
                        token_count=chapter.get('token_count', 0),
                        order_index=chapter['order'],
                        level=chapter['level']
                    )
                
                # 3. Update status
                db.update_book(
                    book_id, 
                    status='parsed',
                    parsed_md_path=str(file_path.with_suffix('.md')) if suffix == '.epub' else str(file_path)
                )
                db.update_parse_task(task_id, status='completed', progress=100)
                
                return jsonify({
                    'success': True,
                    'task_id': task_id
                })
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                db.update_book(book_id, status='error', error_message=str(e))
                db.update_parse_task(task_id, status='failed', error_message=str(e))
                raise e
                
        else:
            return jsonify({'error': f'Unsupported file type: {suffix}'}), 400
    
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


@app.route('/api/chapters/bulk', methods=['POST'])
def get_bulk_chapters():
    """Get details for multiple chapters"""
    data = request.json
    chapter_ids = data.get('chapter_ids', [])
    
    if not chapter_ids:
        return jsonify([])
        
    chapters = db.get_chapters_by_ids(chapter_ids)
    return jsonify(chapters)


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
    """Generate Q&A pairs for a chapter or multiple chapters"""
    data = request.json
    chapter_id = data.get('chapter_id')
    chapter_ids = data.get('chapter_ids')
    count = data.get('count', 8)  # Default to 8 if not provided
    
    # Handle multiple chapters
    target_chapter_id = None
    merged_content = ""
    merged_title = ""
    
    if chapter_ids and isinstance(chapter_ids, list) and len(chapter_ids) > 0:
        # Use the first chapter as the target for saving content
        target_chapter_id = chapter_ids[0]
        
        # Fetch and merge content from all chapters
        titles = []
        contents = []
        for cid in chapter_ids:
            ch = db.get_chapter_by_id(cid)
            if ch:
                titles.append(ch['title'])
                contents.append(f"--- Chapter: {ch['title']} ---\n{ch['content_md']}")
        
        merged_title = " + ".join(titles)
        merged_content = "\n\n".join(contents)
    elif chapter_id:
        # Single chapter mode
        chapter = db.get_chapter_by_id(chapter_id)
        if not chapter:
            return jsonify({'error': 'Chapter not found'}), 404
        target_chapter_id = chapter_id
        merged_title = chapter['title']
        merged_content = chapter['content_md']
    else:
        return jsonify({'error': 'Chapter ID or Chapter IDs required'}), 400

    # Get custom prompt if exists
    custom_prompt = db.get_custom_prompt('qa')
    template = custom_prompt['content'] if custom_prompt else None
    
    prompt = prompts.get_qa_prompt(
        chapter_title=merged_title,
        chapter_content=merged_content,
        custom_template=template,
        count=count
    )
    
    try:
        # Call LLM
        response = llm_client.generate_text(prompt)
        
        # Parse response
        items = prompts.parse_llm_response(response)
        
        # Save to database (target_chapter_id)
        saved_count = 0
        for item in items:
            if prompts.validate_qa_item(item):
                db.add_generated_content(
                    chapter_id=target_chapter_id,
                    content_type='qa',
                    question=item['question'],
                    answer=item['answer'],
                    explanation=item.get('explanation')
                )
                saved_count += 1
                
        return jsonify({
            'message': 'Generation successful',
            'generated_count': saved_count,
            'total_items': len(items)
        })
        
    except Exception as e:
        import traceback
        print(f"ERROR in generate_qa: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate/exercise', methods=['POST'])
def generate_exercise():
    """Generate exercises for a chapter or multiple chapters"""
    data = request.json
    chapter_id = data.get('chapter_id')
    chapter_ids = data.get('chapter_ids')
    count = data.get('count', 8)  # Default to 8 if not provided
    
    # Handle multiple chapters
    target_chapter_id = chapter_id
    merged_content = ""
    merged_title = ""
    
    if chapter_ids and isinstance(chapter_ids, list) and len(chapter_ids) > 0:
        # Use the first chapter as the target for saving content
        target_chapter_id = chapter_ids[0]
        
        # Fetch and merge content from all chapters
        titles = []
        contents = []
        for cid in chapter_ids:
            ch = db.get_chapter_by_id(cid)
            if ch:
                titles.append(ch['title'])
                contents.append(f"--- Chapter: {ch['title']} ---\n{ch['content_md']}")
        
        merged_title = " + ".join(titles)
        merged_content = "\n\n".join(contents)
    elif chapter_id:
        # Single chapter mode
        chapter = db.get_chapter_by_id(chapter_id)
        if not chapter:
            return jsonify({'error': 'Chapter not found'}), 404
        merged_title = chapter['title']
        merged_content = chapter['content_md']
    else:
        return jsonify({'error': 'Chapter ID or Chapter IDs required'}), 400
        
    # Get custom prompt if exists
    custom_prompt = db.get_custom_prompt('exercise')
    template = custom_prompt['content'] if custom_prompt else None
    
    prompt = prompts.get_exercise_prompt(
        chapter_title=merged_title,
        chapter_content=merged_content,
        custom_template=template,
        count=count
    )
    
    try:
        # Call LLM
        response = llm_client.generate_text(prompt)
        
        # Parse response
        items = prompts.parse_llm_response(response)
        
        # Save to database
        saved_count = 0
        for item in items:
            if prompts.validate_exercise_item(item):
                options_json = None
                if item.get('options'):
                    import json
                    options_json = json.dumps(item['options'])
                    
                db.add_generated_content(
                    chapter_id=target_chapter_id,
                    content_type='exercise',
                    question=item['question'],
                    answer=item['answer'],
                    explanation=item.get('explanation'),
                    options_json=options_json
                )
                saved_count += 1
                
        return jsonify({
            'message': 'Generation successful',
            'generated_count': saved_count,
            'total_items': len(items)
        })
        
    except Exception as e:
        import traceback
        print(f"ERROR in generate_exercise: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate/qa/stream', methods=['POST'])
def generate_qa_stream():
    """Generate Q&A with real-time progress via SSE"""
    data = request.json
    chapter_id = data.get('chapter_id')
    count = data.get('count', 8)
    
    if not chapter_id:
        return jsonify({'error': 'Chapter ID is required'}), 400
        
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    def generate():
        try:
            # Step 1: Preparing
            yield f"data: {json.dumps({'type': 'status', 'message': '正在准备生成...', 'progress': 5})}\n\n"
            
            # Get custom prompt
            custom_prompt = db.get_custom_prompt('qa')
            template = custom_prompt['content'] if custom_prompt else None
            
            prompt = prompts.get_qa_prompt(
                chapter_title=chapter['title'],
                chapter_content=chapter['content_md'],
                custom_template=template,
                count=count
            )
            
            # Step 2: Calling LLM
            yield f"data: {json.dumps({'type': 'status', 'message': '正在调用LLM...', 'progress': 10})}\n\n"
            
            response = llm_client.generate_text(prompt)
            
            # Step 3: Received response
            yield f"data: {json.dumps({'type': 'status', 'message': '已接收响应，正在解析...', 'progress': 50})}\n\n"
            
            # Parse response
            items = prompts.parse_llm_response(response)
            
            yield f"data: {json.dumps({'type': 'status', 'message': f'解析完成，共{len(items)}条内容', 'progress': 70})}\n\n"
            
            # Step 4: Save to database
            saved_count = 0
            for i, item in enumerate(items):
                if prompts.validate_qa_item(item):
                    db.add_generated_content(
                        chapter_id=chapter_id,
                        content_type='qa',
                        question=item['question'],
                        answer=item['answer'],
                        explanation=item.get('explanation'),
                        options_json=None
                    )
                    saved_count += 1
                    
                # Update progress
                progress = 70 + int((i + 1) / len(items) * 25)
                yield f"data: {json.dumps({'type': 'status', 'message': f'正在保存 {i+1}/{len(items)}...', 'progress': progress})}\n\n"
            
            # Complete
            yield f"data: {json.dumps({'type': 'complete', 'message': f'生成完成！共生成{saved_count}条内容', 'progress': 100, 'saved_count': saved_count})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/generate/exercise/stream', methods=['POST'])
def generate_exercise_stream():
    """Generate exercises with real-time progress via SSE"""
    data = request.json
    chapter_id = data.get('chapter_id')
    count = data.get('count', 8)
    
    if not chapter_id:
        return jsonify({'error': 'Chapter ID is required'}), 400
        
    chapter = db.get_chapter_by_id(chapter_id)
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    def generate():
        try:
            # Step 1: Preparing
            yield f"data: {json.dumps({'type': 'status', 'message': '正在准备生成...', 'progress': 5})}\n\n"
            
            # Get custom prompt
            custom_prompt = db.get_custom_prompt('exercise')
            template = custom_prompt['content'] if custom_prompt else None
            
            prompt = prompts.get_exercise_prompt(
                chapter_title=chapter['title'],
                chapter_content=chapter['content_md'],
                custom_template=template,
                count=count
            )
            
            # Step 2: Calling LLM
            yield f"data: {json.dumps({'type': 'status', 'message': '正在调用LLM...', 'progress': 10})}\n\n"
            
            response = llm_client.generate_text(prompt)
            
            # Step 3: Received response
            yield f"data: {json.dumps({'type': 'status', 'message': '已接收响应，正在解析...', 'progress': 50})}\n\n"
            
            # Parse response
            items = prompts.parse_llm_response(response)
            
            yield f"data: {json.dumps({'type': 'status', 'message': f'解析完成，共{len(items)}条内容', 'progress': 70})}\n\n"
            
            # Step 4: Save to database
            saved_count = 0
            for i, item in enumerate(items):
                if prompts.validate_exercise_item(item):
                    options_json = None
                    if item.get('options'):
                        options_json = json.dumps(item['options'])
                        
                    db.add_generated_content(
                        chapter_id=chapter_id,
                        content_type='exercise',
                        question=item['question'],
                        answer=item['answer'],
                        explanation=item.get('explanation'),
                        options_json=options_json
                    )
                    saved_count += 1
                    
                # Update progress
                progress = 70 + int((i + 1) / len(items) * 25)
                yield f"data: {json.dumps({'type': 'status', 'message': f'正在保存 {i+1}/{len(items)}...', 'progress': progress})}\n\n"
            
            # Complete
            yield f"data: {json.dumps({'type': 'complete', 'message': f'生成完成！共生成{saved_count}条内容', 'progress': 100, 'saved_count': saved_count})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/prompts', methods=['GET', 'POST'])
def manage_prompts():
    """Get or create prompt templates"""
    if request.method == 'GET':
        prompt_type = request.args.get('type')
        prompts = db.get_all_prompts(prompt_type)
        return jsonify(prompts)
    else:  # POST
        data = request.json
        prompt_type = data.get('prompt_type')
        name = data.get('name')
        content = data.get('content')
        
        if not all([prompt_type, name, content]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        prompt_id = db.create_prompt(prompt_type, name, content)
        return jsonify({'success': True, 'id': prompt_id})



@app.route('/api/prompts/<int:prompt_id>', methods=['PUT'])
def update_prompt_route(prompt_id):
    """Update prompt template"""
    data = request.json
    content = data.get('content')
    
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    success = db.update_prompt(prompt_id, content)
    return jsonify({'success': success})



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


@app.route('/api/content/<int:content_id>', methods=['DELETE'])
def delete_content(content_id):
    """Delete generated content"""
    success = db.delete_generated_content(content_id)
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to delete content'}), 500


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


@app.route('/api/books/<int:book_id>/progress', methods=['GET'])
def get_book_progress(book_id):
    """Get verification progress for a book"""
    progress = db.get_book_progress(book_id)
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


@app.route('/content_manager/<int:book_id>')
def content_manager(book_id):
    """Content management page"""
    return render_template('content_manager.html', book_id=book_id)


@app.route('/api/books/<int:book_id>/content/search', methods=['POST'])
def search_content(book_id):
    """Search generated content with filters"""
    data = request.json
    chapter_ids = data.get('chapter_ids')
    content_type = data.get('content_type')
    status = data.get('status')
    keyword = data.get('keyword')
    
    results = db.search_generated_content(
        book_id=book_id,
        chapter_ids=chapter_ids,
        content_type=content_type,
        status=status,
        keyword=keyword
    )
    
    return jsonify(results)


@app.route('/api/books/<int:book_id>/content/export', methods=['POST'])
def export_search_content(book_id):
    """Export selected content"""
    data = request.json
    content_ids = data.get('content_ids')
    
    # Get book info for filename
    book = db.get_book_by_id(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    
    if not content_ids:
        return jsonify({'error': 'No content selected'}), 400
        
    results = db.get_content_by_ids(content_ids)
    
    try:
        output_path = excel_exporter.export_content_list(
            results, 
            book['title']
        )
        
        directory = output_path.parent
        filename = output_path.name
        
        return send_from_directory(
            directory,
            filename,
            as_attachment=True
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
