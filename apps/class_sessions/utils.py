from apps.class_sessions.models import ClassSession 

def recalculate_session_indices(klass_pk):
    """
    Đánh số lại index cho toàn bộ các buổi học của một lớp.
    - Sắp xếp theo ngày và giờ bắt đầu.
    - Dùng bulk_update để tối ưu hiệu suất.
    """
    # Lấy tất cả buổi học của lớp, sắp xếp theo thứ tự thời gian
    all_sessions_of_class = ClassSession.objects.filter(klass__pk=klass_pk).order_by('date', 'start_time')
    updated_indices = []
    
    for i, session in enumerate(all_sessions_of_class, 1):
        # Chỉ thêm vào danh sách cập nhật nếu index cần thay đổi
        if session.index != i:
            session.index = i
            updated_indices.append(session)

    # Thực hiện cập nhật hàng loạt (bulk update)
    if updated_indices:
        ClassSession.objects.bulk_update(updated_indices, ['index'])
    
    return len(updated_indices)