// component-toasts.js — auto show Bootstrap Toasts on dynamic insert

(function () {
  function showToasts(root) {
    const list = (root || document).querySelectorAll('.toast:not([data-bs-shown])');
    list.forEach(el => {
      el.setAttribute('data-bs-shown', '1');
      if (window.bootstrap?.Toast) new bootstrap.Toast(el).show();
    });
  }

  // 1) Khi trang load: hiển thị mọi .toast sẵn có
  document.addEventListener('DOMContentLoaded', () => {
    showToasts(document);

    // 2) Theo dõi #toast-container để bắt mọi phần tử .toast mới
    const ctn = document.getElementById('toast-container');
    if (ctn && 'MutationObserver' in window) {
      new MutationObserver(muts => {
        for (const m of muts) {
          m.addedNodes && m.addedNodes.forEach(n => {
            if (n.nodeType === 1) showToasts(n);
          });
        }
      }).observe(ctn, { childList: true, subtree: true });
    }
  });

  // 3) Hỗ trợ HTMX: sau khi swap/settle thì show toast
  document.body.addEventListener('htmx:afterSwap',  e => showToasts(e.detail.target));
  document.body.addEventListener('htmx:afterSettle', e => showToasts(e.detail.target));

  // 4) Cho phép gọi thủ công nếu cần
  window.__showToasts = showToasts;
})();
