// Main page JavaScript
let selectedFile = null;
let currentBookId = null;
let parsingBooks = new Map(); // Track parsing books and their task IDs

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    setupUploadHandlers();
    loadBooks();
    setInterval(checkParsingStatus, 3000); // Check status every 3 seconds
});

// Setup upload handlers
function setupUploadHandlers() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');

    uploadArea.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            selectedFile = e.target.files[0];
            showFileInfo();
        }
    });

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');

        if (e.dataTransfer.files.length > 0) {
            selectedFile = e.dataTransfer.files[0];
            showFileInfo();
        }
    });

    uploadBtn.addEventListener('click', uploadFile);
}

function showFileInfo() {
    const uploadArea = document.getElementById('uploadArea');
    const uploadBtn = document.getElementById('uploadBtn');

    uploadArea.querySelector('.upload-prompt').innerHTML = `
        <p style="font-weight: 500;">${t('已选择')}: ${selectedFile.name}</p>
        <p class="file-size-hint">${t('大小')}: ${(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
    `;

    uploadBtn.style.display = 'block';
}

async function uploadFile() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);

    const uploadBtn = document.getElementById('uploadBtn');
    const uploadProgress = document.getElementById('uploadProgress');

    uploadBtn.disabled = true;
    uploadProgress.style.display = 'block';

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            currentBookId = result.book_id;

            // Start parsing
            await startParsing(result.book_id);

            // Reset upload form
            selectedFile = null;
            document.getElementById('fileInput').value = '';
            document.getElementById('uploadArea').querySelector('.upload-prompt').innerHTML = `
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="17 8 12 3 7 8"></polyline>
                    <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <p>${t('点击或拖拽文件到此处上传')}</p>
                <p class="file-size-hint">${t('支持格式: PDF, Word, Markdown, TXT, EPUB (最大 500MB)')}</p>
            `;
            uploadBtn.style.display = 'none';
            uploadProgress.style.display = 'none';

            // Reload books list
            loadBooks();
        } else {
            alert(`${t('upload_failed')}: ${result.error}`);
        }
    } catch (error) {
        alert(`${t('upload_failed')}: ${error.message}`);
    } finally {
        uploadBtn.disabled = false;
    }
}

async function startParsing(bookId) {
    try {
        const response = await fetch('/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ book_id: bookId })
        });

        const result = await response.json();

        if (response.ok) {
            // Track this parsing task
            parsingBooks.set(bookId, result.task_id);
        } else {
            alert(`${t('parsing_started')} ${t('error')}: ${result.error}`);
        }
    } catch (error) {
        console.error('Failed to start parsing:', error);
        alert(`${t('parsing_started')} ${t('error')}: ${error.message}`);
    }
}

async function loadBooks() {
    try {
        const response = await fetch('/api/books');
        const books = await response.json();

        const booksList = document.getElementById('booksList');

        if (books.length === 0) {
            booksList.innerHTML = `<p style="text-align: center; color: var(--text-secondary);">${t('暂无教材,请先上传')}</p>`;
            return;
        }

        booksList.innerHTML = books.map(book => {
            // Check if this book is parsing and has task progress
            const isParsingWithProgress = book.status === 'parsing' && parsingBooks.has(book.id);

            return `
                <div class="book-card ${book.status === 'parsing' ? 'book-parsing' : ''}" onclick="handleBookClick(${book.id}, '${book.status}')">
                    <h3>${book.title || t('未命名')}</h3>
                    ${book.author ? `<p class="book-meta">${t('作者')}: ${book.author}</p>` : ''}
                    ${book.publisher ? `<p class="book-meta">${t('出版社')}: ${book.publisher}</p>` : ''}
                    
                    ${book.status === 'parsing' ? `
                        <div class="parsing-progress" id="progress-${book.id}">
                            <div class="progress-bar-small">
                                <div class="progress-fill-small" style="width: 0%"></div>
                            </div>
                            <p class="progress-text-small">${t('generating')} 0%</p>
                        </div>
                    ` : ''}
                    
                    <div class="book-footer">
                        <span class="book-status status-${book.status}">${getStatusText(book.status)}</span>
                        <div class="book-actions">
                            <button class="btn-icon" onclick="event.stopPropagation(); window.location.href='/content_manager/${book.id}'" title="${t('内容管理')}">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                    <polyline points="14 2 14 8 20 8"></polyline>
                                    <line x1="16" y1="13" x2="8" y2="13"></line>
                                    <line x1="16" y1="17" x2="8" y2="17"></line>
                                    <polyline points="10 9 9 9 8 9"></polyline>
                                </svg>
                            </button>
                            <button class="btn-icon" onclick="event.stopPropagation(); editBook(${book.id})" title="${t('编辑')}">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                </svg>
                            </button>
                            <button class="btn-icon btn-danger" onclick="event.stopPropagation(); deleteBook(${book.id}, '${(book.title || t('未命名')).replace(/'/g, "\\'")}')" title="${t('删除')}">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Update parsing books list
        books.forEach(book => {
            if (book.status === 'parsing') {
                if (!parsingBooks.has(book.id)) {
                    parsingBooks.set(book.id, 'unknown');
                }
            } else {
                parsingBooks.delete(book.id);
            }
        });
    } catch (error) {
        console.error('Failed to load books:', error);
    }
}

function getStatusText(status) {
    const statusMap = {
        'uploaded': t('已上传'),
        'parsing': t('generating'),
        'parsed': t('已解析'),
        'error': t('error')
    };
    return statusMap[status] || status;
}

function handleBookClick(bookId, status) {
    if (status === 'parsed') {
        // Open reading workbench
        window.location.href = `/reading/${bookId}`;
    } else if (status === 'parsing') {
        alert(t('文档正在解析中,请稍候...'));
    } else if (status === 'uploaded') {
        // Show metadata confirmation
        showMetadataModal(bookId);
    } else if (status === 'error') {
        alert(t('文档解析失败,请重新上传'));
    }
}

// Edit book function
async function editBook(bookId) {
    try {
        const response = await fetch(`/api/books/${bookId}`);
        const book = await response.json();

        document.getElementById('modal_book_id').value = book.id;
        document.getElementById('modal_title').value = book.title || '';
        document.getElementById('modal_author').value = book.author || '';
        document.getElementById('modal_publisher').value = book.publisher || '';
        document.getElementById('modal_year').value = book.publish_year || '';
        document.getElementById('modal_isbn').value = book.isbn || '';

        document.getElementById('metadataModal').style.display = 'flex';
    } catch (error) {
        console.error('Failed to load book:', error);
        alert(t('加载教材信息失败'));
    }
}

// Delete book function
async function deleteBook(bookId, bookTitle) {
    if (!confirm(`${t('确定要删除')} 《${bookTitle}》 ${t('吗？')}\n\n${t('此操作将删除教材及其所有相关数据(章节、生成内容等),且不可恢复!')}`)) {
        return;
    }

    try {
        const response = await fetch(`/api/books/${bookId}/delete`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (response.ok) {
            alert(t('delete_success'));
            parsingBooks.delete(bookId); // Remove from tracking
            loadBooks();
        } else {
            alert(`${t('delete_success')} ${t('error')}: ${result.error}`);
        }
    } catch (error) {
        console.error('Failed to delete book:', error);
        alert(t('delete_success') + ' ' + t('error'));
    }
}

async function showMetadataModal(bookId) {
    try {
        const response = await fetch(`/api/books/${bookId}`);
        const book = await response.json();

        document.getElementById('modal_book_id').value = book.id;
        document.getElementById('modal_title').value = book.title || '';
        document.getElementById('modal_author').value = book.author || '';
        document.getElementById('modal_publisher').value = book.publisher || '';
        document.getElementById('modal_year').value = book.publish_year || '';
        document.getElementById('modal_isbn').value = book.isbn || '';

        document.getElementById('metadataModal').style.display = 'flex';
    } catch (error) {
        console.error('Failed to load book metadata:', error);
    }
}

function closeMetadataModal() {
    document.getElementById('metadataModal').style.display = 'none';
}

document.getElementById('metadataForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const bookId = document.getElementById('modal_book_id').value;
    const metadata = {
        title: document.getElementById('modal_title').value,
        author: document.getElementById('modal_author').value || null,
        publisher: document.getElementById('modal_publisher').value || null,
        publish_year: document.getElementById('modal_year').value ? parseInt(document.getElementById('modal_year').value) : null,
        isbn: document.getElementById('modal_isbn').value || null
    };

    try {
        // Use the edit endpoint
        const response = await fetch(`/api/books/${bookId}/edit`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(metadata)
        });

        if (response.ok) {
            closeMetadataModal();
            loadBooks();
            alert(t('save_success'));
        } else {
            alert(t('保存元数据失败'));
        }
    } catch (error) {
        console.error('Failed to save metadata:', error);
        alert(t('保存元数据失败'));
    }
});

// Check parsing status for books in progress
async function checkParsingStatus() {
    if (parsingBooks.size === 0) return;

    try {
        // Check status for each parsing book
        for (const [bookId, taskId] of parsingBooks.entries()) {
            if (taskId === 'unknown') continue;

            const response = await fetch(`/api/parse/status/${taskId}`);
            if (!response.ok) continue;

            const statusInfo = await response.json();
            const progress = statusInfo.progress || 0;
            const status = statusInfo.status;

            // Update progress bar if element exists
            const progressContainer = document.getElementById(`progress-${bookId}`);
            if (progressContainer) {
                const progressBar = progressContainer.querySelector('.progress-fill-small');
                const progressText = progressContainer.querySelector('.progress-text-small');

                if (progressBar) {
                    progressBar.style.width = `${progress}%`;
                }
                if (progressText) {
                    if (status === 'completed') {
                        progressText.textContent = `${t('generating')} 100%`;
                    } else if (status === 'failed' || status === 'error') {
                        progressText.textContent = statusInfo.message || t('error');
                        progressText.title = statusInfo.message || '';
                        progressText.style.color = 'var(--danger-color)';
                    } else {
                        progressText.textContent = `${t('generating')} ${progress}%`;
                    }
                }
            }
        }

        // Reload books to update status
        loadBooks();
    } catch (error) {
        console.error('Failed to check parsing status:', error);
    }
}
