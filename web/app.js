const codeInput = document.querySelector('#codeInput');
const lineNumbers = document.querySelector('#lineNumbers');
const resultBox = document.querySelector('#resultBox');
const generateButton = document.querySelector('#generateButton');
const buttonLabel = document.querySelector('#buttonLabel');
const copyButton = document.querySelector('#copyButton');
const modeLabel = document.querySelector('#modeLabel');
const durationLabel = document.querySelector('#durationLabel');
const statusText = document.querySelector('#statusText');
const sample = `public List<String> filterActiveUsers(List<User> users) {
    return users.stream()
        .filter(user -> user.isActive())
        .map(User::getName)
        .collect(Collectors.toList());
}`;

function updateEditorMeta() {
    const lines = Math.max(1, codeInput.value.split('\n').length);
    lineNumbers.textContent = Array.from({ length: lines }, (_, index) => index + 1).join('\n');
    document.querySelector('#charCount').textContent = `${codeInput.value.length.toLocaleString()} characters`;
}

function setResult(summary, mode, duration) {
    resultBox.className = 'result-box';
    resultBox.innerHTML = `<p class="result-copy">${summary.replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[character]))}</p>`;
    copyButton.disabled = false;
    modeLabel.textContent = mode === 'model' ? 'CoDesc model' : 'Local preview';
    durationLabel.textContent = `${duration} ms`;
}

async function generate() {
    if (!codeInput.value.trim()) {
        codeInput.focus();
        modeLabel.textContent = 'Paste a code sample first';
        return;
    }
    generateButton.disabled = true;
    buttonLabel.textContent = 'Reading your code...';
    const started = performance.now();
    try {
        const response = await fetch('/api/summarize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: codeInput.value }) });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Unable to generate a description.');
        setResult(payload.summary, payload.mode, Math.round(performance.now() - started));
        statusText.textContent = payload.mode === 'model' ? 'Model connected' : 'Preview engine ready';
    } catch (error) {
        modeLabel.textContent = error.message;
    } finally {
        generateButton.disabled = false;
        buttonLabel.textContent = 'Generate description';
    }
}

codeInput.addEventListener('input', updateEditorMeta);
document.querySelector('#sampleButton').addEventListener('click', () => { codeInput.value = sample;
    updateEditorMeta();
    codeInput.focus(); });
document.querySelector('#clearButton').addEventListener('click', () => { codeInput.value = '';
    updateEditorMeta();
    resultBox.className = 'result-box empty';
    resultBox.innerHTML = '<div class="result-placeholder"><span class="placeholder-mark">//</span><p>Your description will appear here.</p><small>Generated summaries stay concise and focused on behavior.</small></div>';
    copyButton.disabled = true;
    modeLabel.textContent = 'Waiting for input';
    durationLabel.textContent = ''; });
generateButton.addEventListener('click', generate);
copyButton.addEventListener('click', async() => { await navigator.clipboard.writeText(document.querySelector('.result-copy').textContent);
    copyButton.textContent = 'Copied';
    setTimeout(() => { copyButton.textContent = 'Copy'; }, 1200); });
codeInput.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') generate(); });
updateEditorMeta();