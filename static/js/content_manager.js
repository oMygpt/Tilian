// Global state
let selectedContentIds = new Set();
let contentList = [];

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    setupPreviewListeners();
    // Initial load
    searchContent();
    loadProgress();
});



function setupEventListeners() {
    // Search input debounce
    let timeout = null;
    document.getElementById('keywordSearch').addEventListener('input', (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            searchContent();
        }, 500);
    });

    // Filter checkboxes
    document.querySelectorAll('input[name="contentType"], input[name="status"]').forEach(cb => {
        cb.addEventListener('change', searchContent);
    });

    // Select all content
    document.getElementById('selectAllContent').addEventListener('change', (e) => {
        const checkboxes = document.querySelectorAll('.content-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = e.target.checked;
            const contentId = parseInt(cb.value);
            if (e.target.checked) {
                selectedContentIds.add(contentId);
            } else {
                selectedContentIds.delete(contentId);
            }
        });
        updateSelectionUI();
    });

    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', searchContent);

    // Export button
    document.getElementById('exportBtn').addEventListener('click', exportContent);

    // Modal close
    document.querySelector('.close').addEventListener('click', closeEditModal);
}

// loadChapters and renderChapterFilter functions are removed as per instruction.

async function searchContent() {
    const container = document.getElementById('contentList');
    container.innerHTML = '<div class="loading-state">正在加载内容...</div>';

    // Collect filters
    const keyword = document.getElementById('keywordSearch').value;

    const contentTypes = Array.from(document.querySelectorAll('input[name="contentType"]:checked'))
        .map(cb => cb.value);

    const statuses = Array.from(document.querySelectorAll('input[name="status"]:checked'))
        .map(cb => cb.value);

    try {
        // Fetch all content for the book (filtered by keyword if present)
        // We send empty chapter_ids to get all chapters
        const response = await fetch(`/api/books/${BOOK_ID}/content/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chapter_ids: null,
                keyword: keyword
            })
        });

        const allResults = await response.json();

        // Client side filtering for multi-select checkboxes
        contentList = allResults.filter(item => {
            if (!contentTypes.includes(item.content_type)) return false;
            if (!statuses.includes(item.status)) return false;
            return true;
        });

        renderContentList();

        // Update progress/stats after content loads
        loadProgress();
    } catch (error) {
        console.error('Failed to search content:', error);
        document.getElementById('contentList').innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

function renderContentList() {
    const container = document.getElementById('contentList');
    document.getElementById('resultCount').textContent = `${contentList.length} 条结果`;

    // Clear selection when list refreshes (optional, but safer)
    selectedContentIds.clear();
    updateSelectionUI();
    document.getElementById('selectAllContent').checked = false;

    if (contentList.length === 0) {
        container.innerHTML = '<div class="empty-state">没有找到符合条件的内容</div>';
        return;
    }

    container.innerHTML = contentList.map((item, index) => {
        const typeLabel = item.content_type === 'qa' ? '问答' : '习题';
        const statusLabel = {
            'pending': '待生成',
            'generated': '已生成',
            'verified': '已校验'
        }[item.status] || item.status;

        let optionsHtml = '';
        if (item.options_json) {
            try {
                const options = JSON.parse(item.options_json);
                optionsHtml = `
                    <div class="field-group">
                        <div class="field-label">选项</div>
                        <ul class="options-list">
                            ${options.map(opt => `<li>${opt}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } catch (e) { }
        }

        return `
            <div class="content-card" id="card-${item.id}">
                <div class="card-header">
                    <div class="card-meta">
                        <div class="checkbox-wrapper">
                            <input type="checkbox" class="content-checkbox" value="${item.id}">
                            <span class="index-number">#${index + 1}</span>
                        </div>
                        <span class="badge ${item.content_type}">${typeLabel}</span>
                        <span class="badge ${item.status}">${statusLabel}</span>
                        <span class="badge ${item.generation_mode === 'multi_agent' ? 'mode-multi' : 'mode-std'}">
                            ${item.generation_mode === 'multi_agent' ? '🤖 多智能体' : '⚡️ 标准'}
                        </span>
                        <span class="badge model-name" title="生成模型">
                            🧠 ${item.model_name || 'Unknown'}
                        </span>
                        <span class="chapter-info">所属章节: ${item.chapter_title}</span>
                        <span class="time-info" title="生成时间">${new Date(item.created_at + 'Z').toLocaleString()}</span>
                    </div>
                    <div class="card-actions">
                        <button class="btn-icon" onclick="editContent(${item.id})" title="编辑">
                            ✏️
                        </button>
                        ${item.status !== 'verified' ? `
                        <button class="btn-icon" onclick="verifyContent(${item.id})" title="标记为已校验">
                            ✅
                        </button>
                        ` : ''}
                        <button class="btn-icon delete" onclick="deleteContent(${item.id})" title="删除">
                            🗑️
                        </button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="field-group">
                        <div class="field-label">题干 / 问题</div>
                        <div class="field-content">${item.question}</div>
                    </div>
                    ${optionsHtml}
                    <div class="field-group">
                        <div class="field-label">答案</div>
                        <div class="field-content">${item.answer}</div>
                    </div>
                    <div class="field-group">
                        <div class="field-label">解析</div>
                        <div class="field-content">${item.explanation || '无'}</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Add checkbox listeners
    document.querySelectorAll('.content-checkbox').forEach(cb => {
        cb.addEventListener('change', (e) => {
            const contentId = parseInt(e.target.value);
            if (e.target.checked) {
                selectedContentIds.add(contentId);
            } else {
                selectedContentIds.delete(contentId);
            }
            updateSelectionUI();

            // Update select all state
            const allChecked = Array.from(document.querySelectorAll('.content-checkbox'))
                .every(c => c.checked);
            document.getElementById('selectAllContent').checked = allChecked;
        });
    });

    // Trigger MathJax for rendered content
    if (window.MathJax) {
        MathJax.typesetPromise([container]).catch((err) => console.log(err));
    }
}

function updateSelectionUI() {
    const count = selectedContentIds.size;
    document.getElementById('selectionCount').textContent = `已选 ${count} 项`;
    document.getElementById('exportBtn').disabled = count === 0;
}

function editContent(id) {
    const item = contentList.find(i => i.id === id);
    if (!item) return;

    document.getElementById('editContentId').value = item.id;
    document.getElementById('editQuestion').value = item.question;
    document.getElementById('editAnswer').value = item.answer;
    document.getElementById('editExplanation').value = item.explanation || '';

    const optionsGroup = document.getElementById('editOptionsGroup');
    const optionsInput = document.getElementById('editOptions');

    if (item.options_json) {
        optionsGroup.style.display = 'flex';
        try {
            const options = JSON.parse(item.options_json);
            optionsInput.value = options.join('\n');
        } catch (e) {
            optionsInput.value = item.options_json;
        }
    } else {
        optionsGroup.style.display = 'none';
        optionsInput.value = '';
    }

    // Show modal with overlay
    const modal = document.getElementById('editModal');
    modal.style.display = 'flex';
    modal.classList.add('active');

    // Initialize previews
    setupPreviewListeners(); // Assuming initializePreviewListeners is a typo and refers to setupPreviewListeners

    // Trigger initial preview for all fields
    document.querySelectorAll('.latex-input').forEach(input => {
        updatePreview(input.id, input.dataset.preview); // Adjusted to match existing updatePreview signature
    });
}

function closeEditModal() {
    const modal = document.getElementById('editModal');
    modal.classList.remove('active');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 200); // Match animation duration
}

// Preview logic
function setupPreviewListeners() {
    const inputs = document.querySelectorAll('.latex-input');
    inputs.forEach(input => {
        input.addEventListener('input', (e) => {
            const previewId = e.target.dataset.preview;
            updatePreview(e.target.id, previewId);
        });
    });
}

function updatePreview(inputId, previewId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);
    if (!input || !preview) return;

    const content = input.value;
    // Simple markdown-like rendering for newlines
    preview.innerHTML = content.replace(/\n/g, '<br>');

    // Trigger MathJax
    if (window.MathJax) {
        MathJax.typesetPromise([preview]).catch((err) => console.log(err));
    }
}

async function saveContentEdit() {
    const id = document.getElementById('editContentId').value;
    const question = document.getElementById('editQuestion').value;
    const answer = document.getElementById('editAnswer').value;
    const explanation = document.getElementById('editExplanation').value;
    const optionsStr = document.getElementById('editOptions').value;

    const updateData = {
        question,
        answer,
        explanation
    };

    if (document.getElementById('editOptionsGroup').style.display !== 'none') {
        // Parse options back to JSON
        const options = optionsStr.split('\n').filter(line => line.trim());
        updateData.options_json = JSON.stringify(options);
    }

    try {
        const response = await fetch(`/api/content/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });

        if (response.ok) {
            alert('保存成功');
            closeEditModal();
            searchContent(); // Refresh list
        } else {
            alert('保存失败');
        }
    } catch (error) {
        alert(`保存失败: ${error.message}`);
    }
}

async function verifyContent(id) {
    if (!confirm('确认标记为已校验？')) return;

    try {
        const response = await fetch(`/api/content/${id}/verify`, {
            method: 'POST'
        });

        if (response.ok) {
            searchContent(); // Refresh list
            loadProgress(); // Refresh progress
        } else {
            alert('操作失败');
        }
    } catch (error) {
        alert(`操作失败: ${error.message}`);
    }
}

async function deleteContent(id) {
    if (!confirm('确定要删除这条内容吗？此操作不可恢复。')) return;

    try {
        const response = await fetch(`/api/content/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            searchContent(); // Refresh list
            loadProgress(); // Refresh progress
        } else {
            alert('删除失败');
        }
    } catch (error) {
        alert(`删除失败: ${error.message}`);
    }
}

async function exportContent() {
    const btn = document.getElementById('exportBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.textContent = '导出中...';

    try {
        const response = await fetch(`/api/books/${BOOK_ID}/content/export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content_ids: Array.from(selectedContentIds)
            })
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `export.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        } else {
            const err = await response.json();
            alert(`导出失败: ${err.error}`);
        }
    } catch (error) {
        alert(`导出失败: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

async function loadProgress() {
    try {
        const response = await fetch(`/api/books/${BOOK_ID}/progress`);
        const progress = await response.json();

        document.getElementById('totalGenerated').textContent = progress.total;
        document.getElementById('totalVerified').textContent = progress.verified;
        document.getElementById('overallProgressFill').style.width = `${progress.percentage}%`;
        document.getElementById('overallProgressText').textContent = `${Math.round(progress.percentage)}%`;
    } catch (error) {
        console.error('Failed to load progress:', error);
    }
}
