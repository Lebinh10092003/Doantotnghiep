// static/js/custom-events.js

document.addEventListener('DOMContentLoaded', () => {
    // Utilities to aggressively clean up modal side-effects,
    // but only when there is no modal currently shown.
    const forceModalCleanup = () => {
        try {
            // If any modal is visible, skip cleanup to avoid racing with a new open.
            const anyOpen = document.querySelector('.modal.show');
            if (anyOpen) return;
            // If body indicates a modal is in open/transition state, skip cleanup
            // to avoid removing a just-created backdrop.
            if (document.body.classList.contains('modal-open')) return;
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        } catch (_) { /* noop */ }
    };

    // Defensive: after a modal is fully hidden, ensure cleanup
    document.addEventListener('hidden.bs.modal', () => {
        setTimeout(forceModalCleanup, 0);
    });
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
                // If rooms table reloads, keep centers table in sync by default
                if (triggers['reload-rooms-table'] && !triggers['reload-centers-table']) {
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
            if (triggers.closeUserModal 
                || triggers.closeGroupModal 
                || triggers.closeCenterModal 
                || triggers.closeRoomModal 
                || triggers.closeSubjectModal
                || triggers.closeFilterModal
                || triggers.closeAppModal // <-- Trigger chung cho CRUD
            ) {
                try {
                    // Prefer closing the modal that initiated the request
                    const sourceEl = evt.detail.elt;
                    const scopedModal = sourceEl?.closest ? sourceEl.closest('.modal') : null;
                    const openModals = scopedModal ? [scopedModal] : document.querySelectorAll('.modal.show');

                    const cleanup = forceModalCleanup;

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
            dispatchCustomEvent('reload-subjects-table');
            dispatchCustomEvent('reload-modules-table');
            dispatchCustomEvent('reload-lessons-table');
            dispatchCustomEvent('reload-classes-table');
            dispatchCustomEvent('reload-sessions-table');

            // 7. Kích hoạt sự kiện tải lại bộ lọc đã lưu (cho model cụ thể)
            Object.keys(triggers).forEach(key => {
                if (key.startsWith('reload-saved-filters-')) {
                    document.body.dispatchEvent(new CustomEvent(key));
                }
            });

        } catch (e) {
            // console.error('Lỗi xử lý HX-Trigger:', e, 'Header:', header);
        }
    }

    // Trước khi swap: nếu response rỗng vào #modal-content, huỷ swap và đóng modal
    document.body.addEventListener('htmx:beforeSwap', function (evt) {
        const target = evt.detail.target;
        if (!target) return;
        const isModalTarget = target.id === 'modal-content' || (target.closest && target.closest('#modal-content'));
        if (!isModalTarget) return;

        const xhr = evt.detail.xhr;
        try {
            const status = xhr?.status;
            let text = '';
            try { text = xhr?.responseText ?? ''; } catch (_) { /* noop */ }
            const isEmpty = (text === undefined || text === null || String(text).trim() === '');

            if (status === 204 || (status === 200 && isEmpty)) {
                // Không có nội dung để hiển thị trong modal => không swap, đóng modal & dọn dẹp
                evt.detail.shouldSwap = false;
                try {
                    const openModals = document.querySelectorAll('.modal.show');
                    openModals.forEach(m => {
                        const inst = bootstrap.Modal.getOrCreateInstance(m);
                        if (inst) inst.hide();
                        // Fallback hard hide in case no instance
                        m.classList.remove('show');
                        m.setAttribute('aria-hidden', 'true');
                        m.style.display = 'none';
                    });
                } catch (_) { /* noop */ }
                setTimeout(forceModalCleanup, 0);
            }
        } catch (_) { /* noop */ }
    });
    
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

        // Chỉ auto-show khi swap trực tiếp vào #modal-content
        if (target.id === 'modal-content') {
            // Nếu server yêu cầu đóng modal (sau POST thành công), không mở lại
            let shouldShow = true;
            try {
                const header = evt.detail?.xhr?.getResponseHeader('HX-Trigger');
                if (header) {
                    const triggers = JSON.parse(header);
                    if (triggers.closeUserModal 
                        || triggers.closeGroupModal 
                        || triggers.closeCenterModal 
                        || triggers.closeRoomModal 
                        || triggers.closeSubjectModal
                        || triggers.closeFilterModal
                        || triggers.closeAppModal // <-- THÊM MỚI
                    ) {
                        shouldShow = false;
                    }
                }
            } catch (_) { /* noop */ }

            if (shouldShow) {
                const modalEl = target.closest('.modal');
                if (modalEl && !modalEl.classList.contains('show')) {
                    const instance = bootstrap.Modal.getOrCreateInstance(modalEl);
                    // Ensure no stale body/backdrop before showing
                    forceModalCleanup();
                    instance.show();
                }
            }
        }
    });
});