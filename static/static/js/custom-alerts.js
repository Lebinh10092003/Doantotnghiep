document.addEventListener('DOMContentLoaded', () => {
    // Lắng nghe sự kiện HX-Trigger trên body
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        const triggerHeader = evt.detail.xhr.getResponseHeader('HX-Trigger');
        if (!triggerHeader) return;

        try {
            const triggers = JSON.parse(triggerHeader);

            // Xử lý sự kiện 'show-sweet-alert'
            if (triggers['show-sweet-alert']) {
                const alertDetails = triggers['show-sweet-alert'];

                // Cấu hình mặc định cho modal pop-up
                const options = {
                    timer: 3000,
                    timerProgressBar: true,
                    // Ghi đè cấu hình mặc định bằng dữ liệu từ backend
                    ...alertDetails 
                };

                Swal.fire(options);
            }
        } catch (e) {
            console.error("Lỗi xử lý HX-Trigger:", e);
        }
    });
});