document.addEventListener('DOMContentLoaded', () => {
    /**
     * Xử lý các sự kiện tùy chỉnh được gửi từ backend qua header HX-Trigger.
     * @param {Event} evt - Sự kiện HTMX (ví dụ: htmx:afterSwap).
     */
    function handleHtmxTriggerEvents(evt) {
        const header = evt.detail.xhr.getResponseHeader('HX-Trigger');
        if (!header) return;

        try {
            const triggers = JSON.parse(header);

            // 1. Xử lý SweetAlert
            if (triggers['show-sweet-alert']) {
                const alertData = triggers['show-sweet-alert'];
                const options = {
                    timer: 3000,
                    timerProgressBar: true,
                    showConfirmButton: false, // Mặc định ẩn nút confirm
                    ...alertData
                };

                Swal.fire(options).then((result) => {
                    // Redirect nếu có
                    if (alertData.redirect) {
                        window.location.href = alertData.redirect;
                    }
                });
            }

            // 2. Xử lý đóng modal chung (user-modal, group-modal, etc.) và dọn dẹp backdrop
            if (triggers.closeUserModal || triggers.closeGroupModal) {
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

                if (nameEl) nameEl.textContent = data.fullName;
                if (avatarEl) avatarEl.src = data.avatarUrl || '/static/static/images/faces/1.jpg';
            }

        } catch (e) {
            console.error('Lỗi xử lý HX-Trigger:', e, 'Header:', header);
        }
    }

    // Lắng nghe sự kiện HX-Trigger trên body sau khi swap nội dung
    document.body.addEventListener('htmx:afterSwap', handleHtmxTriggerEvents);
});