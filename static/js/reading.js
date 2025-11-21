// Reading Workbench JavaScript
let currentBookId = null;
let currentChapterId = null;
let currentModel = 'chatgpt';
let availableModels = [];
let selectedChapters = new Set();
let isBatchGenerating = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Get book ID from URL
    const pathParts = window.location.pathname.split('/');
    currentBookId = parseInt(pathParts[pathParts.length - 1]);

    loadAvailableModels();
    loadBookInfo();
    loadChapters();
    setupEventListeners();
});

async function loadAvailableModels() {
    try {
        const response = await fetch('/api/models');
        availableModels = await response.json();

        const modelSelect = document.getElementById('modelSelect');
        modelSelect.innerHTML = availableModels.map(model => `
            <option value="${model.id}">${model.name}</option>
        `).join('');

        if (availableModels.length > 0) {
            currentModel = availableModels[0].id;
        }
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function loadBookInfo() {
    try {
        const response = await fetch(`/api/books/${currentBookId}`);
        const book = await response.json();

        document.getElementById('bookTitle').textContent = book.title || 'Untitled';
    } catch (error) {
        console.error('Failed to load book info:', error);
    }
}

async function loadChapters() {
    try {
        const response = await fetch(`/api/books/${currentBookId}/chapters`);
        const chapters = await response.json();

        const chapterTree = document.getElementById('chapterTree');
        chapterTree.innerHTML = chapters.map(chapter => `
            <div class="chapter-item level-${chapter.level}" data-chapter-id="${chapter.id}">
                <div class="chapter-checkbox-wrapper" onclick="event.stopPropagation()">
                    <input type="checkbox" class="chapter-checkbox" value="${chapter.id}">
                </div>
                <div class="chapter-content-wrapper">
                    <div class="chapter-title-row">
                        <span>${chapter.title}</span>
                    </div>
                    <div class="chapter-stats">
                        <span class="token-count-small">${chapter.token_count || 0} tokens</span>
                        <span class="chapter-progress">0%</span>
                    </div>
                </div>
            </div>
        `).join('');

        // Add click handlers
        document.querySelectorAll('.chapter-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Ignore if clicking checkbox wrapper (already handled by stopPropagation)
                const chapterId = parseInt(item.dataset.chapterId);
                loadChapter(chapterId);
            });
        });

        // Add checkbox handlers
        document.querySelectorAll('.chapter-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const chapterId = parseInt(e.target.value);
                if (e.target.checked) {
                    selectedChapters.add(chapterId);
                } else {
                    selectedChapters.delete(chapterId);
                }
                updateSelectionUI();
            });
        });

        // Load first chapter by default
        if (chapters.length > 0) {
            loadChapter(chapters[0].id);
        }
    } catch (error) {
        console.error('Failed to load chapters:', error);
    }
}

async function loadChapter(chapterId) {
    currentChapterId = chapterId;

    try {
        const response = await fetch(`/api/chapters/${chapterId}`);
        const chapter = await response.json();

        // Update UI
        document.querySelectorAll('.chapter-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-chapter-id="${chapterId}"]`).classList.add('active');

        document.getElementById('chapterTitle').textContent = chapter.title;

        // Update token count display
        const tokenCount = chapter.token_count || 0;
        document.getElementById('chapterTokens').textContent = `${tokenCount.toLocaleString()} tokens`;

        // Show/hide split button based on token count and model limits
        updateSplitButtonVisibility(chapter);

        // Render Markdown content
        const contentDiv = document.getElementById('chapterContent');
        contentDiv.innerHTML = renderMarkdown(chapter.content_md || '');

        // Trigger MathJax rendering
        if (window.MathJax) {
            MathJax.typesetPromise([contentDiv]).catch((err) => console.error('MathJax error:', err));
        }

        // Load generated content and progress
        loadGeneratedContent(chapterId);
        loadProgress(chapterId);
    } catch (error) {
        console.error('Failed to load chapter:', error);
    }
}

function renderMarkdown(markdown) {
    // Simple markdown rendering (you could use a library like marked.js for better support)
    return markdown
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/^(.+)$/gm, '<p>$1</p>')
        .replace(/<p><\/p>/g, '')
        .replace(/<p><h/g, '<h')
        .replace(/<\/h([1-6])><\/p>/g, '</h$1>');
}

async function loadGeneratedContent(chapterId) {
    try {
        const response = await fetch(`/api/chapters/${chapterId}/content`);
        const content = await response.json();

        const contentList = document.getElementById('generatedContent');

        if (content.length === 0) {
            contentList.innerHTML = '<p style="text-align: center; color: var(--text-secondary); font-size: 0.875rem;">暂无生成内容</p>';
            return;
        }

        contentList.innerHTML = content.map(item => createContentCard(item)).join('');

        // Add event listeners for editing
        setupContentCardListeners();
    } catch (error) {
        console.error('Failed to load generated content:', error);
    }
}

function createContentCard(item) {
    const typeText = item.content_type === 'qa' ? '问答' : '习题';
    const statusClass = `status-${item.status}`;
    const statusText = {
        'pending': '待生成',
        'generated': '已生成',
        'verified': '已校验'
    }[item.status];

    return `
        <div class="content-card" data-content-id="${item.id}">
            <div class="content-card-header">
                <span class="content-type">${typeText}</span>
                <span class="content-status ${statusClass}">${statusText}</span>
            </div>
            <div class="content-question editableContent" contenteditable="true" data-field="question">
                ${item.question}
            </div>
            <div class="content-answer editableContent" contenteditable="true" data-field="answer">
                <strong>答案:</strong> ${item.answer}
            </div>
            ${item.explanation ? `
                <div class="content-answer editableContent" contenteditable="true" data-field="explanation">
                    <strong>解析:</strong> ${item.explanation}
                </div>
            ` : ''}
            <div class="content-actions">
                <button class="btn btn-small btn-primary" onclick="saveContent(${item.id})">保存</button>
                ${item.status !== 'verified' ? `
                    <button class="btn btn-small btn-success" onclick="verifyContent(${item.id})">标记为已确认</button>
                ` : ''}
            </div>
        </div>
    `;
}

function setupContentCardListeners() {
    document.querySelectorAll('.editableContent').forEach(el => {
        el.addEventListener('blur', () => {
            const card = el.closest('.content-card');
            const contentId = parseInt(card.dataset.contentId);
            saveContent(contentId);
        });
    });
}

async function saveContent(contentId) {
    const card = document.querySelector(`[data-content-id="${contentId}"]`);
    const updates = {};

    card.querySelectorAll('.editableContent').forEach(el => {
        const field = el.dataset.field;
        updates[field] = el.textContent.replace(/^(答案:|解析:)\s*/, '').trim();
    });

    try {
        const response = await fetch(`/api/content/${contentId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (response.ok) {
            console.log('Content saved');
        }
    } catch (error) {
        console.error('Failed to save content:', error);
    }
}

async function verifyContent(contentId) {
    try {
        const response = await fetch(`/api/content/${contentId}/verify`, {
            method: 'POST'
        });

        if (response.ok) {
            // Reload content and progress
            loadGeneratedContent(currentChapterId);
            loadProgress(currentChapterId);
        }
    } catch (error) {
        console.error('Failed to verify content:', error);
    }
}

async function loadProgress(chapterId) {
    try {
        const response = await fetch(`/api/chapters/${chapterId}/progress`);
        const progress = await response.json();

        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');

        progressFill.style.width = `${progress.percentage}%`;
        progressText.textContent = `${progress.verified} / ${progress.total} (${Math.round(progress.percentage)}%)`;

        // Update chapter tree progress
        const chapterItem = document.querySelector(`[data-chapter-id="${chapterId}"] .chapter-progress`);
        if (chapterItem) {
            chapterItem.textContent = `${Math.round(progress.percentage)}%`;
        }
    } catch (error) {
        console.error('Failed to load progress:', error);
    }
}

function setupEventListeners() {
    document.getElementById('modelSelect').addEventListener('change', (e) => {
        currentModel = e.target.value;
    });

    document.getElementById('generateQA').addEventListener('click', () => {
        generateContent('qa');
    });

    document.getElementById('generateExercise').addEventListener('click', () => {
        generateContent('exercise');
    });

    document.getElementById('viewPrompt').addEventListener('click', () => {
        showPromptModal();
    });

    document.getElementById('exportBook').addEventListener('click', () => {
        exportBook();
    });

    document.getElementById('splitChapterBtn').addEventListener('click', () => {
        showSplitModal();
    });

    // Batch selection handlers
    document.getElementById('selectAllChapters').addEventListener('change', (e) => {
        const checkboxes = document.querySelectorAll('.chapter-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = e.target.checked;
            const chapterId = parseInt(cb.value);
            if (e.target.checked) {
                selectedChapters.add(chapterId);
            } else {
                selectedChapters.delete(chapterId);
            }
        });
        updateSelectionUI();
    });
}

function updateSelectionUI() {
    const count = selectedChapters.size;
    const countSpan = document.getElementById('selectedCount');
    const generateQABtn = document.getElementById('generateQA');
    const generateExerciseBtn = document.getElementById('generateExercise');

    if (count > 0) {
        countSpan.textContent = `已选 ${count} 项`;
        countSpan.style.display = 'inline';

        generateQABtn.innerHTML = `<span class="icon">💬</span> 批量生成问答 (${count})`;
        generateExerciseBtn.innerHTML = `<span class="icon">✏️</span> 批量生成习题 (${count})`;
    } else {
        countSpan.style.display = 'none';
        generateQABtn.innerHTML = `<span class="icon">💬</span> 生成问答对`;
        generateExerciseBtn.innerHTML = `<span class="icon">✏️</span> 生成习题`;
    }
}

function updateSplitButtonVisibility(chapter) {
    const splitBtn = document.getElementById('splitChapterBtn');
    const tokenCount = chapter.token_count || 0;

    // Check if chapter exceeds threshold for current model
    const modelConfig = availableModels.find(m => m.id === currentModel);
    if (!modelConfig) {
        splitBtn.style.display = 'none';
        return;
    }

    const maxTokens = modelConfig.max_tokens || 32768;
    const threshold = maxTokens * 0.8; // Assuming 80% threshold

    if (tokenCount > threshold) {
        splitBtn.style.display = 'inline-flex';
    } else {
        splitBtn.style.display = 'none';
    }
}

function showSplitModal() {
    if (!currentChapterId) {
        alert('请先选择章节');
        return;
    }

    // Load chapter info
    fetch(`/api/chapters/${currentChapterId}`)
        .then(response => response.json())
        .then(chapter => {
            document.getElementById('splitTokenCount').textContent = (chapter.token_count || 0).toLocaleString();

            // Populate model select
            const splitModelSelect = document.getElementById('splitModelSelect');
            splitModelSelect.innerHTML = availableModels.map(model => `
                <option value="${model.id}" ${model.id === currentModel ? 'selected' : ''}>
                    ${model.name} (${model.max_tokens} tokens)
                </option>
            `).join('');

            document.getElementById('splitModal').style.display = 'flex';
        })
        .catch(error => {
            console.error('Failed to load chapter for split:', error);
            alert('加载章节信息失败');
        });
}

function closeSplitModal() {
    document.getElementById('splitModal').style.display = 'none';
}

async function confirmSplit() {
    const selectedModel = document.getElementById('splitModelSelect').value;

    try {
        const response = await fetch(`/api/chapters/${currentChapterId}/split`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: selectedModel })
        });

        const result = await response.json();

        if (response.ok) {
            alert(`成功切分章节！\n原章节: ${result.original_tokens} tokens\n切分为: ${result.chunk_count} 个子章节`);
            closeSplitModal();

            // Reload chapters and select first new chapter
            await loadChapters();
            if (result.new_chapter_ids && result.new_chapter_ids.length > 0) {
                loadChapter(result.new_chapter_ids[0]);
            }
        } else {
            alert(`切分失败: ${result.error}`);
        }
    } catch (error) {
        alert(`切分失败: ${error.message}`);
    }
}

async function generateContent(type) {
    if (isBatchGenerating) return;

    // Check if we have selected chapters for batch generation
    if (selectedChapters.size > 0) {
        await batchGenerate(type);
        return;
    }

    if (!currentChapterId) {
        alert('请先选择章节');
        return;
    }

    const btn = type === 'qa' ? document.getElementById('generateQA') : document.getElementById('generateExercise');
    btn.disabled = true;
    btn.textContent = '生成中...';

    try {
        const response = await fetch(`/api/generate/${type}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chapter_id: currentChapterId,
                model: currentModel
            })
        });

        const result = await response.json();

        if (response.ok) {
            alert(`成功生成 ${result.generated_count} 条内容`);
            loadGeneratedContent(currentChapterId);
            loadProgress(currentChapterId);
        } else {
            alert(`生成失败: ${result.error}`);
        }
    } catch (error) {
        alert(`生成失败: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = type === 'qa' ? '<span class="icon">💬</span> 生成问答对' : '<span class="icon">✏️</span> 生成习题';
    }
}

async function batchGenerate(type) {
    const chapters = Array.from(selectedChapters);
    const total = chapters.length;
    let successCount = 0;
    let failCount = 0;

    isBatchGenerating = true;

    // Update UI for batch mode
    document.getElementById('batchProgress').style.display = 'block';
    const btn = type === 'qa' ? document.getElementById('generateQA') : document.getElementById('generateExercise');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = '准备批量生成...';

    const progressFill = document.getElementById('batchProgressFill');
    const progressText = document.getElementById('batchProgressText');

    for (let i = 0; i < total; i++) {
        const chapterId = chapters[i];
        progressText.textContent = `正在生成 ${i + 1}/${total}...`;
        progressFill.style.width = `${((i) / total) * 100}%`;

        try {
            const response = await fetch(`/api/generate/${type}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chapter_id: chapterId,
                    model: currentModel
                })
            });

            if (response.ok) {
                successCount++;
            } else {
                failCount++;
                console.error(`Failed to generate for chapter ${chapterId}`);
            }
        } catch (error) {
            failCount++;
            console.error(`Error generating for chapter ${chapterId}:`, error);
        }

        // Update progress after item completion
        progressFill.style.width = `${((i + 1) / total) * 100}%`;
    }

    // Completion
    isBatchGenerating = false;
    btn.disabled = false;
    btn.innerHTML = originalText;

    progressText.textContent = `完成! 成功: ${successCount}, 失败: ${failCount}`;
    setTimeout(() => {
        document.getElementById('batchProgress').style.display = 'none';
    }, 5000);

    // Refresh current view if it was one of the processed chapters
    if (selectedChapters.has(currentChapterId)) {
        loadGeneratedContent(currentChapterId);
        loadProgress(currentChapterId);
    }

    alert(`批量生成完成\n成功: ${successCount}\n失败: ${failCount}`);

}

async function showPromptModal() {
    // For simplicity, just show a placeholder
    document.getElementById('promptModal').style.display = 'flex';

    // Load current prompt template
    try {
        const response = await fetch('/api/prompts?type=qa');
        const prompts = await response.json();

        if (prompts.length > 0) {
            document.getElementById('promptEditor').value = prompts[0].content;
        }
    } catch (error) {
        console.error('Failed to load prompts:', error);
    }
}

function closePromptModal() {
    document.getElementById('promptModal').style.display = 'none';
}

function savePrompt() {
    // For this implementation, we'll just close the modal
    // In a full implementation, this would save to database
    alert('Prompt模板已保存(此为演示功能)');
    closePromptModal();
}

async function exportBook() {
    try {
        window.location.href = `/api/export/book/${currentBookId}?format=excel`;
    } catch (error) {
        alert(`导出失败: ${error.message}`);
    }
}

// Make functions globally available
window.saveContent = saveContent;
window.verifyContent = verifyContent;
window.closePromptModal = closePromptModal;
window.savePrompt = savePrompt;
window.closeSplitModal = closeSplitModal;
window.confirmSplit = confirmSplit;
