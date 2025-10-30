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

        // 2. Xử lý đóng modal chung (user-modal, group-modal, etc.) và dọn dẹp backdrop
        if (triggers.closeUserModal) {
            // Tìm modal đang hiển thị (có class 'show')
            const openModal = document.querySelector('.modal.show');
            if (openModal) {
                // Lấy instance của modal và ẩn nó đi
                const modalInstance = bootstrap.Modal.getInstance(openModal);
                if (modalInstance) {
                    modalInstance.hide();

                    // Đảm bảo backdrop được gỡ bỏ sau khi modal đã ẩn
                    openModal.addEventListener('hidden.bs.modal', () => {
                        document.body.classList.remove('modal-open');
                        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                    }, { once: true });
                }
            }
        }

        // 3. Xử lý đóng modal đổi mật khẩu
        if (triggers.closePasswordModal) {
            const passwordModal = document.getElementById('passwordModal');
            if (passwordModal) {
                bootstrap.Modal.getInstance(passwordModal)?.hide();
            }
        }

        // 4. Xử lý reset form đổi mật khẩu
        if (triggers.resetPasswordForm) {
            const passwordForm = document.querySelector('#password-modal-content form');
            passwordForm?.reset();
        }

        // 5. Xử lý cập nhật header của trang profile sau khi sửa
        if (triggers.updateProfileHeader) {
            const data = triggers.updateProfileHeader;
            const nameEl = document.getElementById('profile-header-name');
            const avatarEl = document.getElementById('profile-header-avatar');

            if (nameEl) {
                nameEl.textContent = data.fullName;
            }
            if (avatarEl) {
                // Nếu không có avatarUrl, dùng ảnh mặc định. Cần đảm bảo đường dẫn đúng.
                avatarEl.src = data.avatarUrl || '/static/static/images/faces/1.jpg';
            }
        }

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
