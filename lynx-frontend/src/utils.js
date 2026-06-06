let toastTimer = null;

function escHtml(s) {
    if (s === null || s === undefined) return '';
    if (typeof s === 'object') {
        try { s = JSON.stringify(s, null, 2); } catch(e) { s = String(s); }
    } else {
        s = String(s);
    }
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
window.escHtml = escHtml;

function formatDate(s) {
    try { return new Date(s + 'Z').toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }); }
    catch { return '-'; }
}
window.formatDate = formatDate;

function getStatusBadge(s) {
    const map = { processed: '✓ Готово', queued: '⏳ В очереди', failed: '✗ Ошибка', uploaded: '📤 Загружен' };
    return map[s] || s;
}
window.getStatusBadge = getStatusBadge;

function openModal(id) {
    document.getElementById(id).classList.add('active');
}
window.openModal = openModal;

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}
window.closeModal = closeModal;

function showToast(msg, type) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast show ' + (type || '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.className = 'toast'; }, 3000);
}
window.showToast = showToast;
