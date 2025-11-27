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

    // Add listener for model change
    document.getElementById('modelSelect').addEventListener('change', (e) => {
        currentModel = e.target.value;
        updateContextUsage();
    });
});

async function loadAvailableModels() {
    try {
        const response = await fetch('/api/models');
        availableModels = await response.json();

        const modelSelect = document.getElementById('modelSelect');
        modelSelect.innerHTML = availableModels.map(model => `
            <option value="${model.id}" data-max-tokens="${model.max_tokens}">
                ${model.name} (${formatTokenCount(model.max_tokens)} ctx)
            </option>
        `).join('');

        if (availableModels.length > 0) {
            // Prefer deepseek-chat if available
            const deepseek = availableModels.find(m => m.id === 'deepseek-chat');
            currentModel = deepseek ? deepseek.id : availableModels[0].id;
            modelSelect.value = currentModel;
        }

        // Initial update
        updateContextUsage();
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

function formatTokenCount(count) {
    if (count >= 1000000) {
        return (count / 1000000).toFixed(1) + 'M';
    } else if (count >= 1000) {
        return (count / 1000).toFixed(0) + 'k';
    }
    return count;
}

function updateContextUsage() {
    const modelSelect = document.getElementById('modelSelect');
    const selectedOption = modelSelect.options[modelSelect.selectedIndex];
    if (!selectedOption) return;

    const maxTokens = parseInt(selectedOption.dataset.maxTokens) || 0;

    // Calculate total tokens of selected chapters
    let totalTokens = 0;
    const checkboxes = document.querySelectorAll('.chapter-checkbox:checked');

    if (checkboxes.length === 0) {
        // If no chapters selected, check if a single chapter is loaded/active
        // For now, let's just use selected chapters for batch context
        // Or if we are in single chapter view?
        // The prompt implies "selected chapters" for generation.
    }

    checkboxes.forEach(cb => {
        const chapterItem = cb.closest('.chapter-item');
        const tokenText = chapterItem.querySelector('.token-count-small').textContent;
        const tokens = parseInt(tokenText.replace(/[^0-9]/g, '')) || 0;
        totalTokens += tokens;
    });

    const usageDiv = document.getElementById('contextUsage');
    const usageText = usageDiv.querySelector('.usage-text');
    const usageFill = usageDiv.querySelector('.usage-fill');

    if (totalTokens > 0) {
        usageDiv.style.display = 'block';
        const percentage = Math.min((totalTokens / maxTokens) * 100, 100);

        usageText.textContent = t('context_usage_safe', {
            percent: percentage.toFixed(1),
            tokens: formatTokenCount(totalTokens),
            limit: formatTokenCount(maxTokens)
        });
        usageFill.style.width = `${percentage}%`;

        if (totalTokens > maxTokens) {
            usageFill.style.backgroundColor = '#ff4444'; // Red
            usageText.innerHTML += ' <span style="color: #ff4444;">(Exceeds Limit!)</span>';
        } else if (percentage > 80) {
            usageFill.style.backgroundColor = '#ffbb33'; // Orange
        } else {
            usageFill.style.backgroundColor = '#00C851'; // Green
        }
    } else {
        usageDiv.style.display = 'none';
    }
}

async function loadBookInfo() {
    try {
        const response = await fetch(`/api/books/${currentBookId}`);
        const book = await response.json();

        document.getElementById('bookTitle').textContent = book.title || t('未命名');
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
                updateContextUsage(); // Update usage when selection changes
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
        document.getElementById('chapterTokens').textContent = t('chapter_tokens', { tokens: tokenCount.toLocaleString() });

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
    // Content list has been removed from reading page
    // This function is kept empty to prevent errors if called
    return;
}

function createContentCard(item) {
    const typeText = item.content_type === 'qa' ? t('问答对') : t('习题');
    const statusClass = `status-${item.status}`;
    const statusText = {
        'pending': t('待生成'),
        'generated': t('已生成'),
        'verified': t('已校验')
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
                <strong>${t('答案')}:</strong> ${item.answer}
            </div>
            ${item.explanation ? `
                <div class="content-answer editableContent" contenteditable="true" data-field="explanation">
                    <strong>${t('解析')}:</strong> ${item.explanation}
                </div>
            ` : ''}
            <div class="content-actions">
                <button class="btn btn-small btn-primary" onclick="saveContent(${item.id})">${t('保存')}</button>
                ${item.status !== 'verified' ? `
                    <button class="btn btn-small btn-success" onclick="verifyContent(${item.id})">${t('标记为已确认')}</button>
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
        updates[field] = el.textContent.replace(new RegExp(`^(${t('答案')}:|${t('解析')}:)\\s*`), '').trim();
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
        const progressSection = document.getElementById('verificationProgressSection');

        if (progress.total > 0) {
            progressSection.style.display = 'block';
            progressFill.style.width = `${progress.percentage}%`;
            progressText.textContent = `${progress.verified} / ${progress.total} (${Math.round(progress.percentage)}%)`;
        } else {
            progressSection.style.display = 'none';
        }

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

    document.getElementById('generateQaBtn').addEventListener('click', () => {
        generateContent('qa');
    });

    document.getElementById('generateExerciseBtn').addEventListener('click', () => {
        generateContent('exercise');
    });

    document.getElementById('viewPrompt').addEventListener('click', () => {
        showPromptModal();
    });

    // Export button removed from reading page
    // document.getElementById('exportBook').addEventListener('click', () => {
    //     exportBook();
    // });

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
    const generateQABtn = document.getElementById('generateQaBtn');
    const generateExerciseBtn = document.getElementById('generateExerciseBtn');

    if (count > 0) {
        countSpan.textContent = t('已选 {count} 项', { count: count });
        countSpan.style.display = 'inline';

        generateQABtn.innerHTML = `<span class="icon">💬</span> ${t('批量生成问答')} (${count})`;
        generateExerciseBtn.innerHTML = `<span class="icon">✏️</span> ${t('批量生成习题')} (${count})`;

        // Load selected chapters for reading
        loadSelectedChapters();
    } else {
        countSpan.style.display = 'none';
        generateQABtn.innerHTML = `<span class="icon">❓</span> ${t('生成问答')}`;
        generateExerciseBtn.innerHTML = `<span class="icon">📝</span> ${t('生成习题')}`;

        // If we have a current chapter but no selection, ensure it's loaded
        if (currentChapterId && !selectedChapters.has(currentChapterId)) {
            // If current chapter was just deselected, we might want to reload it 
            // or do nothing if it's already visible. 
            // For now, let's just ensure single view mode if selection is cleared
            loadChapter(currentChapterId);
        }
    }
}

async function loadSelectedChapters() {
    const chapterIds = Array.from(selectedChapters).sort((a, b) => a - b);

    try {
        const response = await fetch('/api/chapters/bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chapter_ids: chapterIds })
        });

        const chapters = await response.json();

        // Calculate total tokens
        const totalTokens = chapters.reduce((sum, ch) => sum + (ch.token_count || 0), 0);

        // Update Header
        document.getElementById('chapterTitle').textContent = t('已选 {count} 个章节', { count: chapters.length });
        document.getElementById('chapterTokens').textContent = t('chapter_tokens', { tokens: totalTokens.toLocaleString() });

        // Hide single chapter specific controls
        document.getElementById('splitChapterBtn').style.display = 'none';

        // Render concatenated content
        const contentDiv = document.getElementById('chapterContent');
        const concatenatedContent = chapters.map(ch => `
            <div class="chapter-section">
                <h1 class="chapter-separator-title">${ch.title}</h1>
                <div class="chapter-meta-small">Token: ${ch.token_count || 0}</div>
                ${renderMarkdown(ch.content_md || '')}
                <hr class="chapter-separator">
            </div>
        `).join('');

        contentDiv.innerHTML = concatenatedContent;

        // Trigger MathJax
        if (window.MathJax) {
            MathJax.typesetPromise([contentDiv]).catch((err) => console.error('MathJax error:', err));
        }

        // Clear generated content list as it's specific to single chapter for now
        // document.getElementById('generatedContent').innerHTML = 
        //     '<p style="text-align: center; color: var(--text-secondary);">批量阅读模式下暂不支持查看生成内容</p>';

    } catch (error) {
        console.error('Failed to load selected chapters:', error);
    }
}

// ... (split functions remain same) ...

async function generateContent(type) {
    if (isBatchGenerating) return;

    // Check if we have selected chapters for batch generation
    if (selectedChapters.size > 0) {
        await batchGenerate(type);
        return;
    }

    if (!currentChapterId) {
        alert(t('select_chapter'));
        return;
    }

    const btnId = type === 'qa' ? 'generateQaBtn' : 'generateExerciseBtn';
    const btn = document.getElementById(btnId);
    const originalText = btn.innerHTML;
    const statusDiv = document.getElementById('generationStatus');
    const countInput = document.getElementById('generateCount');
    const count = parseInt(countInput.value) || 8;

    // Show progress elements
    const progressContainer = document.getElementById('batchProgress');
    const progressFill = document.getElementById('batchProgressFill');
    const progressText = document.getElementById('batchProgressText');

    progressContainer.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = t('准备中...');

    btn.disabled = true;
    btn.textContent = t('generating');
    statusDiv.className = 'status-message info';
    statusDiv.textContent = t('正在准备生成...');

    // Use SSE for real-time progress
    const endpoint = type === 'qa' ? '/api/generate/qa/stream' : '/api/generate/exercise/stream';
    const mode = document.getElementById('generationMode').value;

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chapter_id: currentChapterId,
                model: currentModel,
                count: count,
                mode: mode,
                exercise_type: document.getElementById('exerciseType').value,
                language: document.getElementById('generationLanguage').value
            })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.substring(6));

                    if (data.type === 'status') {
                        progressFill.style.width = `${data.progress}%`;
                        progressText.textContent = data.message;
                        statusDiv.textContent = data.message;
                    } else if (data.type === 'complete') {
                        progressFill.style.width = '100%';
                        progressText.textContent = data.message;
                        statusDiv.className = 'status-message success';
                        statusDiv.textContent = data.message;

                        // Reload progress
                        setTimeout(() => {
                            progressContainer.style.display = 'none';
                            loadProgress(currentChapterId);
                            loadGeneratedContent(currentChapterId); // Also reload generated content
                        }, 3000);
                    } else if (data.type === 'error') {
                        statusDiv.className = 'status-message error';
                        statusDiv.textContent = `${t('生成失败')}: ${data.message}`;
                        progressContainer.style.display = 'none';
                    }
                }
            }
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = `${t('生成失败')}: ${error.message}`;
        progressContainer.style.display = 'none';
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
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
    const btn = type === 'qa' ? document.getElementById('generateQaBtn') : document.getElementById('generateExerciseBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = t('准备批量生成...');

    const progressFill = document.getElementById('batchProgressFill');
    const progressText = document.getElementById('batchProgressText');

    // Get generation count
    const countInput = document.getElementById('generateCount');
    const count = parseInt(countInput.value) || 8;

    // Get chapter details for better display
    const chapterDetails = {};
    for (const chapterId of chapters) {
        try {
            const response = await fetch(`/api/chapters/${chapterId}`);
            const chapter = await response.json();
            chapterDetails[chapterId] = chapter.title;
        } catch (error) {
            chapterDetails[chapterId] = `${t('章节')} ${chapterId}`;
        }
    }

    for (let i = 0; i < total; i++) {
        const chapterId = chapters[i];
        const chapterTitle = chapterDetails[chapterId] || `${t('章节')} ${chapterId}`;
        const typeText = type === 'qa' ? t('问答对') : t('习题');

        // Update progress - starting
        const startMsg = `${t('第')} ${i + 1}/${total} ${t('个')}${typeText} - ${chapterTitle} - ${t('正在准备...')}`;
        progressText.textContent = `${i + 1}/${total}`;
        document.getElementById('batchProgressDetail').textContent = startMsg;
        progressFill.style.width = `${((i) / total) * 100}%`;

        try {
            // Show calling LLM status
            const llmMsg = `${t('第')} ${i + 1}/${total} ${t('个')}${typeText} - ${chapterTitle} - ${t('正在调用大模型...')}`;
            document.getElementById('batchProgressDetail').textContent = llmMsg;

            const response = await fetch(`/api/generate/${type}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    chapter_id: chapterId,
                    model: currentModel,
                    count: count,
                    mode: document.getElementById('generationMode').value,
                    exercise_type: document.getElementById('exerciseType').value,
                    language: document.getElementById('generationLanguage').value
                })
            });

            if (response.ok) {
                const result = await response.json();
                const completeMsg = `${t('第')} ${i + 1}/${total} ${t('个')}${typeText} - ${chapterTitle} - ✅ ${t('已完成')} (${t('生成')}${result.generated_count}${t('条')})`;
                document.getElementById('batchProgressDetail').textContent = completeMsg;
                progressText.textContent = `${i + 1}/${total}`;
                successCount++;
            } else {
                const failMsg = `${t('第')} ${i + 1}/${total} ${t('个')}${typeText} - ${chapterTitle} - ❌ ${t('失败')}`;
                document.getElementById('batchProgressDetail').textContent = failMsg;
                progressText.textContent = `${i + 1}/${total}`;
                failCount++;
                console.error(`Failed to generate for chapter ${chapterId}`);
            }
        } catch (error) {
            const errorMsg = `${t('第')} ${i + 1}/${total} ${t('个')}${typeText} - ${chapterTitle} - ❌ ${t('失败')}`;
            document.getElementById('batchProgressDetail').textContent = errorMsg;
            progressText.textContent = `${i + 1}/${total}`;
            failCount++;
            console.error(`Error generating for chapter ${chapterId}:`, error);
        }

        // Update progress after item completion
        progressFill.style.width = `${((i + 1) / total) * 100}%`;

        // Small delay to show completion message
        await new Promise(resolve => setTimeout(resolve, 500));
    }

    // Completion
    isBatchGenerating = false;
    btn.disabled = false;
    btn.innerHTML = originalText;

    const finalMsg = `✅ ${t('batch_complete')} ${t('success')}: ${successCount}, ${t('error')}: ${failCount}`;
    document.getElementById('batchProgressDetail').textContent = finalMsg;
    progressText.textContent = `${total}/${total}`;
    setTimeout(() => {
        document.getElementById('batchProgress').style.display = 'none';
    }, 5000);

    // Refresh current view if it was one of the processed chapters
    if (selectedChapters.has(currentChapterId)) {
        loadProgress(currentChapterId);
    }

    alert(`${t('batch_complete')}\n${t('success')}: ${successCount}\n${t('error')}: ${failCount}`);

}

let currentPromptType = 'qa';
let currentPromptId = null;

async function showPromptModal() {
    document.getElementById('promptModal').style.display = 'flex';

    // Setup tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', async function () {
            // Update active tab
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Load prompt for selected type
            currentPromptType = this.dataset.type;
            await loadPromptForType(currentPromptType);
        });
    });

    // Load initial QA prompt
    await loadPromptForType('qa');
}

async function loadPromptForType(type) {
    try {
        const response = await fetch(`/api/prompts?type=${type}`);
        const prompts = await response.json();

        if (prompts.length > 0) {
            currentPromptId = prompts[0].id;
            document.getElementById('promptEditor').value = prompts[0].content;
        } else {
            currentPromptId = null;
            document.getElementById('promptEditor').value = '';
        }
    } catch (error) {
        console.error('Failed to load prompts:', error);
    }
}

function closePromptModal() {
    document.getElementById('promptModal').style.display = 'none';
}

async function savePrompt() {
    const content = document.getElementById('promptEditor').value;

    if (!content.trim()) {
        alert(t('Prompt内容不能为空'));
        return;
    }

    try {
        if (currentPromptId) {
            // Update existing prompt
            const response = await fetch(`/api/prompts/${currentPromptId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: content })
            });

            const result = await response.json();
            if (result.success) {
                alert(t('Prompt模板已保存'));
                closePromptModal();
            } else {
                alert(`${t('保存失败')}: ` + (result.error || t('未知错误')));
            }
        } else {
            // Create new prompt
            const response = await fetch('/api/prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt_type: currentPromptType,
                    name: `Custom ${currentPromptType} template`,
                    content: content
                })
            });

            const result = await response.json();
            if (result.success) {
                alert(t('Prompt模板已创建'));
                closePromptModal();
            } else {
                alert(`${t('创建失败')}: ` + (result.error || t('未知错误')));
            }
        }
    } catch (error) {
        alert(`${t('保存失败')}: ` + error.message);
    }
}

async function exportBook() {
    try {
        window.location.href = `/api/export/book/${currentBookId}?format=excel`;
    } catch (error) {
        alert(`${t('导出失败')}: ${error.message}`);
    }
}

// Make functions globally available
window.saveContent = saveContent;
window.verifyContent = verifyContent;
window.closePromptModal = closePromptModal;
window.savePrompt = savePrompt;
window.closeSplitModal = closeSplitModal;
window.confirmSplit = confirmSplit;
