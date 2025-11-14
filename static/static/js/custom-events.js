/**
 * Hàm khởi tạo TomSelect cho các ô input.
 * Hàm này phải được gọi SAU KHI thư viện tom-select.js đã được tải.
 */
function initializeTomSelect(elements) {
  if (typeof elements.forEach !== 'function') return;
  elements.forEach((el) => {
    if (!el.classList.contains('tomselected')) {
      let tom = new TomSelect(el, {
        create: true, // Đảm bảo có thể tạo giá trị mới nếu cần
        sortField: { field: "text", direction: "asc" },
        openOnFocus: true, 
      });
      // Đánh dấu là đã khởi tạo
      el.tomselect = tom;
    }
  });
}

/**
 * Xử lý các tác vụ sau khi HTMX request hoàn thành, bao gồm:
 * 1. Hiển thị thông báo SweetAlert.
 * 2. Đóng các modal.
 * 3. Tải lại các bảng dữ liệu.
 * 4. Cập nhật các phần tử UI khác.
 * @param {Event} evt - Sự kiện HTMX.
 */
function handleHtmxTriggerEvents(evt) {
    if (!evt.detail?.xhr) return; // Bỏ qua nếu không có xhr
    const header = evt.detail.xhr.getResponseHeader('HX-Trigger');
    if (!header) return;

    try {
        const triggers = JSON.parse(header);

        // --- HÀM HỖ TRỢ: Kích hoạt sự kiện tùy chỉnh trên body ---
        const dispatchCustomEvent = (eventName) => {
            if (triggers[eventName]) {
                document.body.dispatchEvent(new CustomEvent(eventName));
            }
        };
        
        const clearModalBody = () => {
            try {
                const openModals = document.querySelectorAll('.modal.show [id$="-modal-content"]');
                openModals.forEach(el => {
                    el.innerHTML = '';
                });
            } catch (_) { /* noop */ }
        };

        // 1. Xử lý SweetAlert
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
            clearModalBody();
        }

        // 2. Đóng modal chung
        if (triggers.closeUserModal 
            || triggers.closeGroupModal 
            || triggers.closeCenterModal 
            || triggers.closeRoomModal 
            || triggers.closeSubjectModal
            || triggers.closeFilterModal
            || triggers.closeClassModal
            || triggers.closeSessionModal 
            || triggers.closeAppModal
        ) {
            try {
                const sourceEl = evt.detail.elt;
                const scopedModal = sourceEl?.closest ? sourceEl.closest('.modal') : null;
                const openModals = scopedModal ? [scopedModal] : document.querySelectorAll('.modal.show');
                
                const cleanup = () => {
                     try {
                        const anyOpen = document.querySelector('.modal.show');
                        if (anyOpen) return;
                        if (document.body.classList.contains('modal-open')) return;
                        document.body.classList.remove('modal-open');
                        document.body.style.overflow = '';
                        document.body.style.paddingRight = '';
                        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                    } catch (_) { /* noop */ }
                };

                const hidePromises = Array.from(openModals).map(m => {
                    const inst = bootstrap.Modal.getInstance(m);
                    if (inst) {
                        return new Promise(resolve => {
                            m.addEventListener('hidden.bs.modal', resolve, { once: true });
                            inst.hide();
                        });
                    } else {
                        m.classList.remove('show');
                        m.setAttribute('aria-hidden', 'true');
                        m.style.display = 'none';
                        return Promise.resolve();
                    }
                });
                Promise.all(hidePromises).then(() => {
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

        // 7. Kích hoạt sự kiện tải lại bộ lọc đã lưu
        Object.keys(triggers).forEach(key => {
            if (key.startsWith('reload-saved-filters-')) {
                document.body.dispatchEvent(new CustomEvent(key));
            }
        });

    } catch (e) {
        // console.error('Lỗi xử lý HX-Trigger:', e, 'Header:', header);
    }
}

/**
 * Xử lý sự kiện htmx:confirm để hiển thị hộp thoại xác nhận tùy chỉnh bằng SweetAlert2.
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
        confirmButtonColor: '#d33', // Màu đỏ cho nút xóa
        cancelButtonColor: '#3085d6', // Màu xanh cho nút hủy
        confirmButtonText: confirmButtonText,
        cancelButtonText: 'Hủy'
    }).then((result) => {
        if (result.isConfirmed) {
            // Nếu người dùng xác nhận, tiếp tục gửi request
            evt.detail.issueRequest();
        }
    });
}

/**
 * Xử lý các hành động trên formset (thêm/xóa dòng).
 * Sử dụng event delegation.
 * @param {Event} evt - Sự kiện click.
 */
function handleFormsetActions(evt) {
    const target = evt.target;
    const addBtn = target.closest('[data-action="add-schedule-form"]');
    const removeBtn = target.closest('[data-action="remove-schedule-form"]');

    if (addBtn) {
        const formList = document.getElementById('schedule-form-list');
        const totalFormsInput = document.getElementById('id_schedules-TOTAL_FORMS');
        const emptyFormTemplate = document.getElementById('empty-form');

        if (!formList || !totalFormsInput || !emptyFormTemplate) return;

        const formIdx = parseInt(totalFormsInput.value);
        const newFormHtml = emptyFormTemplate.innerHTML.replace(/__prefix__/g, formIdx);
        
        formList.insertAdjacentHTML('beforeend', newFormHtml);
        totalFormsInput.value = formIdx + 1;
        return;
    }

    if (removeBtn) {
        const formRow = removeBtn.closest('.schedule-form');
        if (!formRow) return;
        
        // Tìm bất kỳ input nào có name kết thúc bằng "-DELETE" (cả checkbox và hidden)
        const deleteInput = formRow.querySelector('input[name$="-DELETE"]');

        if (deleteInput) {
            // Dù là form đã tồn tại (checkbox) hay form mới (hidden),
            // chúng ta đều đánh dấu nó để xóa và ẩn đi.
            // Đối với checkbox, thao tác này sẽ check nó.
            // Đối với hidden input, nó không có thuộc tính 'checked', nhưng việc ẩn dòng là đủ.
            // Để đảm bảo form được gửi đúng, ta sẽ set giá trị cho hidden input nếu nó là hidden.
            if (deleteInput.type === 'hidden') {
                deleteInput.value = 'on'; // Đánh dấu để Django xử lý xóa
            }
            deleteInput.checked = true;
            formRow.style.display = 'none';
        }
    }
}


document.addEventListener('DOMContentLoaded', () => {
    
    // --- Hàm dọn dẹp modal (từ file gốc) ---
    const forceModalCleanup = () => {
        try {
            const anyOpen = document.querySelector('.modal.show');
            if (anyOpen) return;
            if (document.body.classList.contains('modal-open')) return;
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        } catch (_) { /* noop */ }
    };

    document.addEventListener('hidden.bs.modal', () => {
        setTimeout(forceModalCleanup, 0);
    });
    
    // --- GẮN CÁC LISTENER CHÍNH ---

    // 1. Xử lý trigger từ server
    document.body.addEventListener('htmx:afterRequest', handleHtmxTriggerEvents);

    // 2. Ghi đè confirm mặc định
    document.body.addEventListener('htmx:confirm', handleHtmxConfirm);

    // Helper: only prevent swap/show for the same modal as target
    function isClosingTargetModal(triggers, targetModalEl) {
        try {
            if (!triggers || !targetModalEl) return false;
            const id = targetModalEl.id || '';
            const closeMap = {
                'user-modal': 'closeUserModal',
                'group-modal': 'closeGroupModal',
                'center-modal': 'closeCenterModal',
                'room-modal': 'closeRoomModal',
                'curriculum-modal': 'closeSubjectModal',
                'filter-modal': 'closeFilterModal',
                'classes-modal': 'closeClassModal',
                'sessions-modal': 'closeSessionModal',
                'password-modal': 'closePasswordModal',
                'app-modal': 'closeAppModal',
            };
            const key = closeMap[id];
            return key ? !!triggers[key] : false;
        } catch(_) { return false; }
    }

    // Xử lý thêm/xóa formset
    document.body.addEventListener('click', handleFormsetActions);

    // 3. Xử lý sau khi swap
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        const target = evt.detail.target;
        if (!target) return;

        // --- Logic 1: Tự động mở modal ---
        // Tự động mở modal nếu nội dung được swap vào #modal-content
        const contentEl = (target.matches && target.matches('[id$="-modal-content"]')) ? target : (target.closest && target.closest('[id$="-modal-content"]'));
        if (contentEl) {
            const modalEl = contentEl.closest('.modal');
            let shouldShow = true;
            try {
                // Kiểm tra xem response này có *đồng thời* yêu cầu đóng modal không
                const header = evt.detail?.xhr?.getResponseHeader('HX-Trigger');
                if (header) {
                    const triggers = JSON.parse(header);
                    if (isClosingTargetModal(triggers, modalEl)) {
                        shouldShow = false;
                    }
                }
            } catch (_) { /* noop */ }

            if (shouldShow) {
                // Chỉ show nếu modal chưa được hiển thị
                if (modalEl && !modalEl.classList.contains('show')) { 
                    const instance = bootstrap.Modal.getOrCreateInstance(modalEl);
                    forceModalCleanup();
                    instance.show();
                }
            }
        }

        // --- Logic 2: Khởi tạo TomSelect ---
        // Khởi tạo TomSelect cho các element mới
        if (typeof target.querySelectorAll === 'function') {
            const newElements = target.querySelectorAll('.tom-select');
            if (newElements.length > 0) {
                initializeTomSelect(newElements);
            }
        }

        // --- Logic 3: Đặt tiêu đề modal khi nội dung đã load ---
        try {
            const modalContent = (target.id && target.id.endsWith('-modal-content')) ? target : null;
            if (modalContent) {
                let titleText = '';
                // Ưu tiên tiêu đề có sẵn trong partial (nếu có)
                const prefer = modalContent.querySelector('h5.modal-title') || modalContent.querySelector('h5') || modalContent.querySelector('h3');
                if (prefer && prefer.textContent) {
                    titleText = prefer.textContent.trim();
                }
                if (titleText) {
                    const headerTitle = document.querySelector('#sessions-modal .modal-title');
                    if (headerTitle) {
                        headerTitle.textContent = titleText;
                    }
                    // Cập nhật Alpine (nếu có) để giữ đồng bộ
                    try {
                        const root = document.querySelector('#main');
                        if (root && root.__x && root.__x.$data) {
                            root.__x.$data.modalTitle = titleText;
                        }
                    } catch (_) { /* noop */ }
                }
            }
        } catch (_) { /* noop */ }
    });
    
    // 4. Xử lý TRƯỚC KHI SWAP 
    document.body.addEventListener('htmx:beforeSwap', function (evt) {
        const target = evt.detail.target;
        if (!target) return;

        // Chỉ áp dụng logic này cho các target là modal
        const contentEl = (target.matches && target.matches('[id$="-modal-content"]')) ? target : (target.closest && target.closest('[id$="-modal-content"]'));
        const isModalTarget = !!contentEl;
        if (!isModalTarget) return;

        const xhr = evt.detail.xhr;
        if (!xhr) return;

        // --- KIỂM TRA 1: Nếu có trigger đóng modal ---
        try {
            const header = xhr?.getResponseHeader('HX-Trigger');
            if (header) {
                const triggers = JSON.parse(header);
                // Nếu response không đóng đúng modal mục tiêu, vô hiệu hóa các cờ close* để không hủy swap
                try {
                    const modalElGuard = contentEl ? contentEl.closest('.modal') : null;
                    if (!isClosingTargetModal(triggers, modalElGuard)) {
                        delete triggers.closeUserModal;
                        delete triggers.closeGroupModal;
                        delete triggers.closeCenterModal;
                        delete triggers.closeRoomModal;
                        delete triggers.closeSubjectModal;
                        delete triggers.closeFilterModal;
                        delete triggers.closeClassModal;
                        delete triggers.closeSessionModal;
                        delete triggers.closeAppModal;
                    }
                } catch(_) { /* noop */ }
                if (triggers.closeUserModal || triggers.closeGroupModal || 
                    triggers.closeCenterModal || triggers.closeRoomModal || 
                    triggers.closeSubjectModal || triggers.closeFilterModal ||
                    triggers.closeClassModal || triggers.closeSessionModal || // <--- Trigger của bạn
                    triggers.closeAppModal) 
                {
                    evt.detail.shouldSwap = false; // Hủy swap
                    // handleHtmxTriggerEvents sẽ chạy sau (trong afterRequest) và xử lý việc đóng modal
                    return; 
                }
            }
        } catch(_) { /* noop */ }

        // --- KIỂM TRA 2: Nếu response rỗng (thường là sau khi POST/DELETE thành công) ---
        try {
            const status = xhr?.status;
            const text = xhr?.responseText ?? '';
            const isEmpty = (text === undefined || text === null || String(text).trim() === '');

            // Nếu response là 204 hoặc 200 rỗng
            if (status === 204 || (status === 200 && isEmpty)) {
                evt.detail.shouldSwap = false; // Hủy swap
            }
        } catch (_) { /* noop */ }
    });
});

function _toISO(d) {
    const z = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

function _mondayOf(date) {
    const d = new Date(date);
    const day = d.getDay(); // 0..6, 0=CN, 1=T2
    const diff = (day === 0 ? -6 : 1 - day);
    d.setDate(d.getDate() + diff);
    return d;
}

function bindMySchedule() {
    const form = document.getElementById('my-schedule-filters');
    if (!form || form.dataset.bound === '1') return;
    form.dataset.bound = '1';

    const startInput = () => form.elements['start'];
    const endInput = () => form.elements['end'];

    function adjustWeek(delta) {
        const start = startInput().value ? new Date(startInput().value) : new Date();
        const newStart = new Date(start);
        newStart.setDate(newStart.getDate() + (7 * delta));
        const newEnd = new Date(newStart);
        newEnd.setDate(newEnd.getDate() + 6);
        startInput().value = _toISO(newStart);
        endInput().value = _toISO(newEnd);
        form.requestSubmit();
    }

    const prevBtn = document.getElementById('prev-week');
    const nextBtn = document.getElementById('next-week');
    const thisBtn = document.getElementById('this-week');
    prevBtn?.addEventListener('click', () => adjustWeek(-1));
    nextBtn?.addEventListener('click', () => adjustWeek(1));
    thisBtn?.addEventListener('click', () => {
        const now = new Date();
        const mon = _mondayOf(now);
        const sun = new Date(mon);
        sun.setDate(mon.getDate() + 6);
        startInput().value = _toISO(mon);
        endInput().value = _toISO(sun);
        form.requestSubmit();
    });
}

function bindTeachingSchedule() {
    const form = document.getElementById('teaching-schedule-filters');
    if (!form || form.dataset.bound === '1') return;
    form.dataset.bound = '1';

    const dateInput = () => form.elements['date'];

    function adjustWeek(delta) {
        const base = dateInput().value ? new Date(dateInput().value) : new Date();
        base.setDate(base.getDate() + (7 * delta));
        dateInput().value = _toISO(base);
        form.requestSubmit();
    }

    const prevBtn = document.getElementById('prev-week');
    const nextBtn = document.getElementById('next-week');
    const thisBtn = document.getElementById('this-week');
    prevBtn?.addEventListener('click', () => adjustWeek(-1));
    nextBtn?.addEventListener('click', () => adjustWeek(1));
    thisBtn?.addEventListener('click', () => { dateInput().value = _toISO(new Date()); form.requestSubmit(); });
}

document.addEventListener('DOMContentLoaded', () => {
    try { bindMySchedule(); } catch(_) {}
    try { bindTeachingSchedule(); } catch(_) {}
    try { bindTeachingClasses(); } catch(_) {}
});

function bindTeachingClasses() {
    const form = document.getElementById('teaching-classes-filters');
    if (!form || form.dataset.bound === '1') return;
    form.dataset.bound = '1';
    // No extra JS needed; HTMX on form handles submit.
}
