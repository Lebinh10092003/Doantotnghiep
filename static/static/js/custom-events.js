// static/static/js/custom-events.js

/**
 * Xử lý các sự kiện tùy chỉnh được gửi từ backend qua header HX-Trigger.
 * @param {Event} evt - Sự kiện HTMX (ví dụ: htmx:afterRequest).
 */
function handleHtmxTriggerEvents(evt) {
    const header = evt.detail.xhr.getResponseHeader('HX-Trigger');
    if (!header) return;

    try {
        const triggers = JSON.parse(header);

        // 1. Xử lý SweetAlert
        if (triggers['show-sweet-alert']) {
            const alertData = triggers['show-sweet-alert'];
            Swal.fire({
                icon: alertData.icon || 'info',
                title: alertData.title || 'Thông báo',
                text: alertData.text,
                timer: alertData.timer || 3000,
                timerProgressBar: true,
                showConfirmButton: false,
            }).then((result) => {
                // Redirect nếu có
                if (alertData.redirect) {
                    window.location.href = alertData.redirect;
                }
            });
        }

        // 2. Xử lý đóng modal chung
        // Bất kỳ modal nào có id là 'user-modal' sẽ được đóng
        if (triggers.closeUserModal) {
            const userModal = document.getElementById('user-modal');
            if (userModal) {
                bootstrap.Modal.getInstance(userModal)?.hide();
            }
        }
        // Thêm các trình xử lý sự kiện khác ở đây nếu cần
        // Ví dụ: if (triggers.anotherEvent) { ... }

    } catch (e) {
        console.error('Lỗi xử lý HX-Trigger:', e, 'Header:', header);
    }
}

/**
 * Hiển thị modal xác nhận xóa bằng SweetAlert trước khi gửi yêu cầu HTMX.
 * @param {Event} evt - Sự kiện htmx:confirm.
 */
function handleHtmxConfirm(evt) {
    const target = evt.detail.elt;

    // Chỉ hiển thị modal xác nhận nếu phần tử có thuộc tính 'data-confirm-title'.
    // Nếu không, cho phép yêu cầu tiếp tục mà không cần xác nhận.
    if (!target.hasAttribute('data-confirm-title')) {
        return;
    }
    // Ngăn chặn hộp thoại confirm mặc định của trình duyệt
    evt.preventDefault();

    const title = target.getAttribute('data-confirm-title') || 'Bạn có chắc không?';
    const text = target.getAttribute('data-confirm-text') || 'Hành động này không thể hoàn tác!';
    const confirmButtonText = target.getAttribute('data-confirm-button') || 'Đồng ý xóa';

    Swal.fire({
        title: title,
        text: text,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: confirmButtonText,
        cancelButtonText: 'Hủy'
    }).then((result) => {
        if (result.isConfirmed) {
            // Nếu người dùng xác nhận, tiếp tục gửi yêu cầu HTMX
            evt.detail.issueRequest();
        }
    });
}