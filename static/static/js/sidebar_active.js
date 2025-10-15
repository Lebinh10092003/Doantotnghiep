document.addEventListener("DOMContentLoaded", function () {
  // Hàm reset trạng thái active
  function clearActive() {
    document.querySelectorAll(".submenu-link").forEach(l => l.classList.remove("active"));
    document.querySelectorAll(".sidebar-item.has-sub").forEach(i => i.classList.remove("active"));
    document.querySelectorAll(".sidebar-link").forEach(l => l.classList.remove("active"));
  }

  // Xử lý click cho submenu
  document.querySelectorAll(".submenu-link").forEach(link => {
    link.addEventListener("click", function () {
      // Xóa trạng thái active cũ
      clearActive();

      // Đặt active cho chính submenu được click
      this.classList.add("active");

      // Kích hoạt menu cha
      const parent = this.closest(".sidebar-item.has-sub");
      if (parent) parent.classList.add("active");

      // Lưu trạng thái vào localStorage (nếu muốn giữ sáng khi reload)
      localStorage.setItem("activeSidebar", this.textContent.trim());
    });
  });

  // Xử lý click cho menu cấp 1 (nếu có)
  document.querySelectorAll(".sidebar-link").forEach(link => {
    link.addEventListener("click", function () {
      clearActive();
      this.classList.add("active");
      localStorage.setItem("activeSidebar", this.textContent.trim());
    });
  });

  // Khôi phục trạng thái khi reload
  const saved = localStorage.getItem("activeSidebar");
  if (saved) {
    document.querySelectorAll(".sidebar-link, .submenu-link").forEach(link => {
      if (link.textContent.trim() === saved) {
        link.classList.add("active");
        const parent = link.closest(".sidebar-item.has-sub");
        if (parent) parent.classList.add("active");
      }
    });
  }
});
