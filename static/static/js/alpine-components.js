document.addEventListener('alpine:init', () => {
    Alpine.data('toastComponent', () => ({
        toasts: [],
        confirmToast: { show: false, message: '', onConfirm: () => {} },

        init() {
            // Lắng nghe sự kiện htmx:confirm trên toàn bộ trang
            document.body.addEventListener('htmx:confirm', (e) => {
                e.preventDefault();
                this.showConfirmToast(e.detail.question, () => e.detail.issueRequest());
            });

            // Lắng nghe sự kiện HX-Trigger để hiển thị toast thông báo
            document.body.addEventListener('htmx:after-swap', (e) => {
                const triggerHeader = e.detail.xhr.getResponseHeader('HX-Trigger');
                if (triggerHeader) {
                    try {
                        const triggers = JSON.parse(triggerHeader);
                        if (triggers.showToast) {
                            this.addToast(triggers.showToast.message, triggers.showToast.type);
                        }
                    } catch (error) {}
                }
            });
        },

        addToast(message, type = 'success') {
            const id = Date.now();
            this.toasts.push({
                id: id,
                message: message,
                type: type,
                visible: true
            });
            setTimeout(() => {
                this.removeToast(id);
            }, 4000);
        },

        removeToast(id) {
            const index = this.toasts.findIndex(t => t.id === id);
            if (index > -1) {
                this.toasts.splice(index, 1);
            }
        },

        showConfirmToast(message, onConfirmCallback) {
            this.confirmToast.message = message;
            this.confirmToast.onConfirm = onConfirmCallback;
            this.confirmToast.show = true;
        },

        confirmAction() {
            this.confirmToast.onConfirm();
            this.confirmToast.show = false;
        },

        cancelAction() {
            this.confirmToast.show = false;
        }
    }));
});