/* ============================================================
   Victoria IDE Surface — logic
   Monaco editor + file tree + terminal + AI chat, wired to
   /api/ide/* and Victoria's /api/chat brain.
   ============================================================ */
(function () {
    'use strict';

    const $ = (id) => document.getElementById(id);

    const el = {
        wsName: $('wsName'), treeBody: $('treeBody'), treeFilter: $('treeFilter'),
        tabs: $('tabs'), editorHost: $('editorHost'), editorEmpty: $('editorEmpty'),
        chatLog: $('chatLog'), chatText: $('chatText'), chatSend: $('chatSend'), chatModel: $('chatModel'),
        termOut: $('termOut'), termCmd: $('termCmd'), termRun: $('termRun'), termClear: $('termClear'),
        btnSave: $('btnSave'), btnAsk: $('btnAsk'), btnRefresh: $('btnRefresh'), btnHud: $('btnHud'),
        toast: $('toast'),
    };

    const state = { tabs: [], active: null, editor: null, workspace: '', models: new Map(), treeRoot: '' };

    // ---------- helpers ----------
    function esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function toast(msg, kind) {
        if (!el.toast) return;
        el.toast.textContent = msg;
        el.toast.className = 'ide-toast show' + (kind ? ' ' + kind : '');
        clearTimeout(el.toast._t);
        el.toast._t = setTimeout(() => { el.toast.className = 'ide-toast'; }, 2600);
    }
    async function api(path, opts) {
        const res = await fetch(path, opts);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || ('HTTP ' + res.status));
        return data;
    }
    function tabFor(path) { return state.tabs.find(t => t.path === path); }

    // ---------- Monaco ----------
    function initEditor() {
        state.editor = monaco.editor.create(el.editorHost, {
            value: '', language: 'plaintext', theme: 'vs-dark',
            automaticLayout: true, fontSize: 13, fontFamily: "'JetBrains Mono', monospace",
            minimap: { enabled: true }, scrollBeyondLastLine: false, tabSize: 4,
            renderWhitespace: 'selection', smoothScrolling: true,
        });
        state.editor.onDidChangeModelContent(() => {
            const t = tabFor(state.active);
            if (!t) return;
            const cur = state.editor.getValue();
            const dirty = cur !== t.original;
            if (dirty !== t.dirty) { t.dirty = dirty; renderTabs(); }
        });
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); saveActive(); }
        });
        showEditorEmpty();
    }

    function showEditorEmpty() {
        if (el.editorEmpty) el.editorEmpty.style.display = state.active ? 'none' : 'flex';
        if (el.editorHost) el.editorHost.style.visibility = state.active ? 'visible' : 'hidden';
    }

    // ---------- tabs ----------
    function renderTabs() {
        el.tabs.innerHTML = '';
        state.tabs.forEach(t => {
            const d = document.createElement('div');
            d.className = 'tab' + (t.path === state.active ? ' active' : '');
            const name = t.path.split('/').pop();
            d.innerHTML = `<span>${esc(name)}</span>${t.dirty ? '<span class="dirty">●</span>' : ''}<span class="close">×</span>`;
            d.addEventListener('click', (e) => {
                if (e.target.classList.contains('close')) { closeTab(t.path); }
                else activate(t.path);
            });
            el.tabs.appendChild(d);
        });
    }

    function activate(path) {
        const t = tabFor(path);
        if (!t) return;
        if (state.active && tabFor(state.active) && state.editor) {
            tabFor(state.active).viewState = state.editor.saveViewState();
        }
        state.active = path;
        if (!state.models.has(path)) {
            state.models.set(path, monaco.editor.createModel(t.content, t.language || 'plaintext'));
        }
        state.editor.setModel(state.models.get(path));
        if (t.viewState) state.editor.restoreViewState(t.viewState);
        state.editor.focus();
        renderTabs(); showEditorEmpty();
        markActiveTreeRow();
    }

    function closeTab(path) {
        const i = state.tabs.findIndex(t => t.path === path);
        if (i < 0) return;
        const t = state.tabs[i];
        if (t.dirty && !confirm(`Discard unsaved changes in ${path}?`)) return;
        state.tabs.splice(i, 1);
        if (state.models.has(path)) { state.models.get(path).dispose(); state.models.delete(path); }
        if (state.active === path) {
            state.active = state.tabs.length ? state.tabs[Math.max(0, i - 1)].path : null;
            if (state.active) activate(state.active); else { state.editor.setModel(null); renderTabs(); showEditorEmpty(); }
        } else { renderTabs(); }
    }

    async function openFile(path) {
        if (tabFor(path)) { activate(path); return; }
        try {
            const data = await api('/api/ide/file?path=' + encodeURIComponent(path));
            state.tabs.push({ path: data.path, content: data.content, original: data.content, language: data.language, dirty: false, viewState: null });
            renderTabs();
            activate(data.path);
        } catch (e) { toast('Open failed: ' + e.message, 'err'); }
    }

    async function saveActive() {
        const t = tabFor(state.active);
        if (!t) { toast('No file open', 'err'); return; }
        try {
            const content = state.editor.getValue();
            await api('/api/ide/file', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: t.path, content }),
            });
            t.content = content; t.original = content; t.dirty = false;
            if (state.models.has(t.path)) state.models.get(t.path).setValue(content);
            renderTabs();
            toast('Saved ' + t.path, 'ok');
        } catch (e) { toast('Save failed: ' + e.message, 'err'); }
    }

    // ---------- file tree ----------
    function treeRow(entry, depth) {
        const row = document.createElement('div');
        row.className = 'tree-row' + (entry.type === 'dir' ? ' dir' : '');
        row.dataset.path = entry.path;
        row.style.paddingLeft = (10 + depth * 12) + 'px';
        row.innerHTML = `<span class="ic">${entry.type === 'dir' ? '📁' : '📄'}</span><span class="nm">${esc(entry.name)}</span>`;
        return row;
    }

    async function loadTree(path, container, depth) {
        try {
            const data = await api('/api/ide/tree?path=' + encodeURIComponent(path || ''));
            container.innerHTML = '';
            const q = (el.treeFilter.value || '').trim().toLowerCase();
            data.entries.forEach(entry => {
                if (q && entry.type === 'file' && !entry.name.toLowerCase().includes(q) && !entry.path.toLowerCase().includes(q)) return;
                const row = treeRow(entry, depth);
                container.appendChild(row);
                if (entry.type === 'dir') {
                    const kids = document.createElement('div');
                    kids.className = 'tree-children';
                    kids.style.display = 'none';
                    container.appendChild(kids);
                    row.addEventListener('click', async (ev) => {
                        ev.stopPropagation();
                        const open = kids.style.display !== 'none';
                        kids.style.display = open ? 'none' : 'block';
                        row.querySelector('.ic').textContent = open ? '📁' : '📂';
                        if (!open && !kids.dataset.loaded) { kids.dataset.loaded = '1'; await loadTree(entry.path, kids, depth + 1); }
                    });
                } else {
                    row.addEventListener('click', () => openFile(entry.path));
                }
            });
            if (!container.children.length) container.innerHTML = '<div class="editor-empty" style="padding:12px;">empty</div>';
        } catch (e) {
            container.innerHTML = `<div class="editor-empty" style="padding:12px;">${esc(e.message)}</div>`;
        }
    }

    function markActiveTreeRow() {
        document.querySelectorAll('.tree-row').forEach(r => {
            r.classList.toggle('active', r.dataset.path === state.active);
        });
    }

    // ---------- terminal ----------
    function termAppend(text, cls) {
        const span = document.createElement('span');
        if (cls) span.className = cls;
        span.textContent = text;
        el.termOut.appendChild(span);
        el.termOut.scrollTop = el.termOut.scrollHeight;
    }
    async function runCommand() {
        const cmd = el.termCmd.value.trim();
        if (!cmd) return;
        el.termCmd.value = '';
        termAppend('\n$ ' + cmd + '\n', 'ok');
        try {
            const d = await api('/api/ide/run', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: cmd, cwd: '' }),
            });
            if (d.stdout) termAppend(d.stdout);
            if (d.stderr) termAppend(d.stderr, 'err');
            termAppend(`[exit ${d.code}]\n`, d.code === 0 ? 'ok' : 'err');
        } catch (e) { termAppend('Error: ' + e.message + '\n', 'err'); }
    }

    // ---------- chat ----------
    function chatAdd(role, text) {
        const d = document.createElement('div');
        d.className = 'chat-msg ' + role;
        d.textContent = text;
        el.chatLog.appendChild(d);
        el.chatLog.scrollTop = el.chatLog.scrollHeight;
        return d;
    }

    function editorContext() {
        const t = tabFor(state.active);
        if (!t || !state.editor) return '';
        const sel = state.editor.getSelection();
        const selected = sel && !sel.isEmpty() ? state.editor.getModel().getValueInRange(sel) : '';
        const body = selected || state.editor.getValue();
        const clipped = body.length > 4000 ? body.slice(0, 4000) + '\n…[truncated]' : body;
        return `[Current file: ${t.path}${selected ? ' (selected lines)' : ''}]\n\`\`\`\n${clipped}\n\`\`\`\n\n`;
    }

    async function askVictoria(message) {
        if (!message) return;
        chatAdd('user', message);
        const pending = chatAdd('bot', '…thinking');
        try {
            const d = await api('/api/chat', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: editorContext() + message, speak: false }),
            });
            pending.textContent = d.response || '(no response)';
            if (d.active_model && el.chatModel) el.chatModel.textContent = d.active_model;
        } catch (e) { pending.textContent = 'Error: ' + e.message; }
        el.chatLog.scrollTop = el.chatLog.scrollHeight;
    }

    // ---------- wiring ----------
    function wire() {
        el.btnSave && el.btnSave.addEventListener('click', saveActive);
        el.btnRefresh && el.btnRefresh.addEventListener('click', () => loadTree('', el.treeBody, 0));
        el.btnHud && el.btnHud.addEventListener('click', () => { window.location.href = '/'; });
        el.btnAsk && el.btnAsk.addEventListener('click', () => {
            const t = tabFor(state.active);
            if (!t) { toast('Open a file first', 'err'); return; }
            askVictoria(`Explain this file and suggest improvements: ${t.path}`);
        });

        let filterT = null;
        el.treeFilter && el.treeFilter.addEventListener('input', () => {
            clearTimeout(filterT); filterT = setTimeout(() => loadTree('', el.treeBody, 0), 250);
        });

        el.termRun && el.termRun.addEventListener('click', runCommand);
        el.termCmd && el.termCmd.addEventListener('keydown', (e) => { if (e.key === 'Enter') runCommand(); });
        el.termClear && el.termClear.addEventListener('click', () => { el.termOut.textContent = ''; });

        el.chatSend && el.chatSend.addEventListener('click', () => {
            const v = el.chatText.value.trim(); el.chatText.value = ''; askVictoria(v);
        });
        el.chatText && el.chatText.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                const v = el.chatText.value.trim(); el.chatText.value = ''; askVictoria(v);
            }
        });
    }

    // ---------- boot ----------
    async function boot() {
        wire();
        try {
            const info = await api('/api/ide/info');
            state.workspace = info.workspace;
            if (el.wsName) el.wsName.textContent = '📂 ' + info.workspace;
            if (!info.allow_run && el.termCmd) { el.termCmd.disabled = true; el.termCmd.placeholder = 'Command execution disabled (ide.allow_run=false)'; }
        } catch (e) { toast('Workspace info failed: ' + e.message, 'err'); }
        await loadTree('', el.treeBody, 0);
    }

    require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs' } });
    require(['vs/editor/editor.main'], function () {
        initEditor();
        boot();
    });
})();
