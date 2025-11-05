// static/js/custom-events.js

document.addEventListener('DOMContentLoaded', () => {
    /**
     * Xử lý các tác vụ sau khi HTMX request hoàn thành, bao gồm:
     * 1. Hiển thị thông báo SweetAlert.
     * 2. Đóng các modal.
     * 3. Tải lại các bảng dữ liệu.
     * 4. Cập nhật các phần tử UI khác.
     * @param {Event} evt - Sự kiện HTMX.
     */
    function handleHtmxTriggerEvents(evt) {
        const header = evt.detail.xhr.getResponseHeader('HX-Trigger');
        if (!header) return;

        try {
            const triggers = JSON.parse(header);

            // Backward-compat mappings for legacy trigger keys
            try {
                if (triggers['reloadCentersTable'] && !triggers['reload-centers-table']) {
                    triggers['reload-centers-table'] = true;
                }
            } catch (_) { /* noop */ }

            // --- HÀM HỖ TRỢ: Kích hoạt sự kiện tùy chỉnh trên body ---
            const dispatchCustomEvent = (eventName) => {
                if (triggers[eventName]) {
                    document.body.dispatchEvent(new CustomEvent(eventName));
                }
            };
            
            // 1. Xử lý SweetAlert (luôn được xử lý)
            const clearModalBody = () => {
                try {
                    const openModals = document.querySelectorAll('.modal.show #modal-content');
                    openModals.forEach(el => {
                        el.innerHTML = '';
                    });
                } catch (_) { /* noop */ }
            };

            if (triggers['show-sweet-alert']) {
                const alertData = triggers['show-sweet-alert'];
                const options = {
                    icon: alertData.icon || 'info',
                    title: alertData.title || 'Thông báo',
                    timer: 3000,
                    timerProgressBar: true,
                    showConfirmButton: false, 
                    ...alertData
                };

                Swal.fire(options).then((result) => {
                    if (alertData.redirect) {
                        window.location.href = alertData.redirect;
                    }
                    if (triggers.clearRoomModalBody) {
                        clearModalBody();
                    }
                });
            }
            else if (triggers.clearRoomModalBody) {
                // No alert; clear immediately
                clearModalBody();
            }

            // 2. Đóng modal chung và dọn dẹp backdrop
            if (triggers.closeUserModal || triggers.closeGroupModal || triggers.closeCenterModal || triggers.closeRoomModal) {
                try {
                    const openModals = document.querySelectorAll('.modal.show');

                    const cleanup = () => {
                        document.body.classList.remove('modal-open');
                        document.body.style.overflow = '';
                        document.body.style.paddingRight = '';
                        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                    };

                    const hidePromises = Array.from(openModals).map(m => {
                        const inst = bootstrap.Modal.getInstance(m);
                        if (inst) {
                            return new Promise(resolve => {
                                m.addEventListener('hidden.bs.modal', resolve, { once: true });
                                inst.hide();
                            });
                        } else {
                            // Fallback: if no instance, force-hide classes so cleanup can proceed
                            m.classList.remove('show');
                            m.setAttribute('aria-hidden', 'true');
                            m.style.display = 'none';
                            return Promise.resolve();
                        }
                    });
                    // Always cleanup, even if no open modals found
                    Promise.all(hidePromises).then(() => {
                        // Small delay allows Bootstrap to remove transition classes
                        setTimeout(cleanup, 0);
                    });
                } catch (_) { /* noop */ }
            }

            // 3. Xử lý đóng modal đổi mật khẩu
            if (triggers.closePasswordModal) {
                const passwordModal = document.getElementById('passwordModal');
                bootstrap.Modal.getInstance(passwordModal)?.hide();
            }

            // 4. Xử lý reset form đổi mật khẩu
            if (triggers.resetPasswordForm) {
                const passwordForm = document.querySelector('#password-modal-content form');
                passwordForm?.reset();
            }

            // 5. Xử lý cập nhật header của trang profile 
            if (triggers.updateProfileHeader) {
                const data = triggers.updateProfileHeader;
                const nameEl = document.getElementById('profile-header-name');
                const avatarEl = document.getElementById('profile-header-avatar');

                if (nameEl) nameEl.textContent = data.fullName;
                if (avatarEl) avatarEl.src = data.avatarUrl || '/static/static/images/faces/1.jpg';
            }
            
            // 6. Kích hoạt các sự kiện tải lại bảng
            dispatchCustomEvent('reload-accounts-table');
            dispatchCustomEvent('reload-groups-table');
            dispatchCustomEvent('reload-centers-table');
            dispatchCustomEvent('reload-rooms-table');
        } catch (e) {
            // console.error('Lỗi xử lý HX-Trigger:', e, 'Header:', header);
        }
    }
    
    /**
     * Xử lý sự kiện htmx:confirm để hiển thị hộp thoại xác nhận tùy chỉnh bằng SweetAlert2.
     * @param {Event} evt - Sự kiện HTMX htmx:confirm.
     */
    function handleHtmxConfirm(evt) {
        const target = evt.detail.elt;

        if (!target.hasAttribute('data-confirm-title')) {
            return;
        }
        evt.preventDefault();

        const title = target.getAttribute('data-confirm-title') || 'Bạn chắc chứ?';
        const text = target.getAttribute('data-confirm-text') || 'Hành động này không thể được hoàn tác!';
        const confirmButtonText = target.getAttribute('data-confirm-button') || 'Xác nhận';

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
                evt.detail.issueRequest();
            }
        });
    }

    // Bắt sự kiện htmx:confirm để sử dụng SweetAlert
    document.body.addEventListener('htmx:confirm', handleHtmxConfirm);
    
    // Xử lý các trigger từ server sau MỌI request (cả swap và no-swap)
    document.body.addEventListener('htmx:afterRequest', handleHtmxTriggerEvents);

    // Tự động mở modal sau khi HTMX đã swap nội dung vào #modal-content
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        const target = evt.detail.target;

        // Chỉ xử lý khi nội dung được swap vào một phần tử có ID là 'modal-content'
        // hoặc là một form bên trong modal (trường hợp trả về lỗi validation)
        const isModalContent = target.id === 'modal-content' || target.closest('#modal-content');

        if (isModalContent) {
            const modalEl = target.closest('.modal');
            if (modalEl) {
                const instance = bootstrap.Modal.getOrCreateInstance(modalEl);
                if (!modalEl.classList.contains('show')) {
                    instance.show();
                }
            }
        }
    });
});
