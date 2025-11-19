// ===== Toastify + HTMX integration =====

// Màu mặc định theo icon/type
const TOAST_COLORS = {
  success: "#16a34a",
  error:   "#dc2626",
  warning: "#d97706",
  info:    "#2563eb",
  default: "#4fbe87"
};

// Helper
function fireToastify({ text, icon, title, gravity, position, duration, close, backgroundColor }) {
  const msg = title || text || "";
  const bg  = backgroundColor || TOAST_COLORS[icon] || TOAST_COLORS.default;
  Toastify({
    text: msg,
    duration: duration ?? 3000,
    close: !!close,
    gravity: gravity || "top",
    position: position || "right",
    backgroundColor: bg
  }).showToast();
}

// JSON body: {icon,title} hoặc {toast:{icon,title,...}}
function tryJsonToast(xhr) {
  try {
    const data = JSON.parse(xhr.responseText);
    const p = data.toast || data;
    if (p && (p.title || p.text)) { fireToastify(p); return true; }
  } catch (_) {}
  return false;
}

// HX-Trigger header: '{"toast":{"icon":"success","title":"...","position":"left"}}'
function tryHeaderTrigger(xhr) {
  const h = xhr.getResponseHeader('HX-Trigger')
        || xhr.getResponseHeader('HX-Trigger-After-Settle')
        || xhr.getResponseHeader('HX-Trigger-After-Swap');
  if (!h) return false;
  try {
    const obj = JSON.parse(h);
    const p = obj.toast || obj.Toast || null;
    if (p && (p.title || p.text)) { fireToastify(p); return true; }
  } catch (_) {
    // nếu header là chuỗi thường → coi là text info
    fireToastify({ icon: "info", title: h });
    return true;
  }
  return false;
}

// HTML fragment: <div data-toast-icon="success" data-toast-title="..."
//                   data-toast-gravity="bottom" data-toast-position="center"></div>
function tryHtmlDataToast(target) {
  const el = target.querySelector('[data-toast-title],[data-toast-text]');
  if (!el) return false;
  fireToastify({
    icon: el.dataset.toastIcon,
    title: el.dataset.toastTitle,
    text: el.dataset.toastText,
    gravity: el.dataset.toastGravity,
    position: el.dataset.toastPosition,
    duration: el.dataset.toastDuration ? Number(el.dataset.toastDuration) : undefined,
    close: el.dataset.toastClose === "true",
    backgroundColor: el.dataset.toastBg
  });
  return true;
}

// ===== Bind HTMX events =====
document.body.addEventListener('htmx:afterRequest', (e) => {
  if (tryJsonToast(e.detail.xhr)) return;
  if (tryHeaderTrigger(e.detail.xhr)) return;
});

document.body.addEventListener('htmx:afterSwap', (e) => {
  tryHtmlDataToast(e.detail.target);
});

// ===== Optional: expose manual helper =====
window.toastify = fireToastify;
