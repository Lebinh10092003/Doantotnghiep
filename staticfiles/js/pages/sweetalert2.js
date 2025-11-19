// ===== SweetAlert2 base =====
const Swal2 = Swal.mixin({ customClass: { input: 'form-control' } });

const Toast = Swal.mixin({
  toast: true,
  position: 'top-end',
  showConfirmButton: false,
  timer: 3000,
  timerProgressBar: true,
  didOpen: (t) => {
    t.addEventListener('mouseenter', Swal.stopTimer);
    t.addEventListener('mouseleave', Swal.resumeTimer);
  }
});

// ===== Modal helper =====
function handleModalAndMaybeRedirect(payload) {
  return Swal.fire({
    icon: payload.icon || 'info',
    title: payload.title || '',
    text: payload.text || '',
    confirmButtonText: 'OK'
  }).then(() => {
    if (payload.redirect) {
      window.location.href = payload.redirect;
    }
  });
}

// ===== Toast helper =====
function fireToast(icon, title) {
  if (!icon || !title) return;
  Toast.fire({ icon, title });
}

// ===== Parsers =====
function tryJsonNotify(xhr) {
  try {
    const data = JSON.parse(xhr.responseText || '{}');
    if (data.modal) {
      handleModalAndMaybeRedirect(data.modal);
      return true;
    }
    const p = data.toast || data;
    if (p && p.icon && p.title) {
      fireToast(p.icon, p.title);
      return true;
    }
  } catch (_) {}
  return false;
}

function tryHeaderTrigger(xhr) {
  const h = xhr.getResponseHeader('HX-Trigger') ||
            xhr.getResponseHeader('HX-Trigger-After-Settle') ||
            xhr.getResponseHeader('HX-Trigger-After-Swap');
  if (!h) return false;
  try {
    const obj = JSON.parse(h);
    if (obj.modal) {
      handleModalAndMaybeRedirect(obj.modal);
      return true;
    }
    const p = obj.toast || obj.Toast || null;
    if (p && p.icon && p.title) {
      fireToast(p.icon, p.title);
      return true;
    }
  } catch (_) {
    // nếu header là chuỗi đơn giản
    fireToast('info', h);
    return true;
  }
  return false;
}

function tryHtmlDataToast(target) {
  const el = target.querySelector('[data-swal-icon][data-swal-title]') ||
             target.querySelector('[data-toast-icon][data-toast-title]');
  if (!el) return false;
  const icon = el.dataset.swalIcon || el.dataset.toastIcon;
  const title = el.dataset.swalTitle || el.dataset.toastTitle;
  fireToast(icon, title);
  return true;
}

// ===== HTMX integration =====
document.body.addEventListener('htmx:afterRequest', (e) => {
  if (tryJsonNotify(e.detail.xhr)) return;
  if (tryHeaderTrigger(e.detail.xhr)) return;
});

document.body.addEventListener('htmx:afterSwap', (e) => {
  tryHtmlDataToast(e.detail.target);
});

// ===== Export helpers =====
window.fireToast = fireToast;
window.handleModalAndMaybeRedirect = handleModalAndMaybeRedirect;
