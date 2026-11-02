/**
 * Lightweight code editor helpers: line numbers, basic highlighting, copy
 */
window.PotionEditor = {
  updateLineNumbers(textarea, container) {
    const lines = (textarea.value || '').split('\n').length;
    let html = '';
    for (let i = 1; i <= Math.max(lines, 1); i++) {
      html += `<span>${i}</span>`;
    }
    container.innerHTML = html;
  },

  setup(textarea, lineNumbersEl) {
    const update = () => this.updateLineNumbers(textarea, lineNumbersEl);
    textarea.addEventListener('input', update);
    textarea.addEventListener('scroll', () => {
      lineNumbersEl.scrollTop = textarea.scrollTop;
    });
    // Tab support
    textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault();
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + 4;
        textarea.dispatchEvent(new Event('input'));
      }
    });
    update();
  },

  async copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      return true;
    }
  },
};
