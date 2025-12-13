# apps/attendance/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
from .models import Attendance
from .forms import AttendanceForm
from apps.class_sessions.models import ClassSession
from apps.accounts.models import User

# Cập nhật điểm danh cho một học sinh trong một buổi học
@require_POST
@login_required
@permission_required("attendance.change_attendance") # Hoặc "attendance.add_attendance"
def update_attendance(request, session_id, student_id):
    session = get_object_or_404(ClassSession, pk=session_id)
    student = get_object_or_404(User, pk=student_id)
    
    # Lấy hoặc tạo mới bản ghi điểm danh
    attendance, created = Attendance.objects.get_or_create(
        session=session, 
        student=student,
        defaults={'status': 'P'} # Mặc định là 'Có mặt' nếu tạo mới
    )
    
    form = AttendanceForm(request.POST, instance=attendance)
    
    if form.is_valid():
        updated_attendance = form.save()
        context = {
            'session': session,
            'student': student,
            'attendance': updated_attendance
        }
        # Trả về fragment template (sẽ tạo ở Bước 5)
        return render(request, '_attendance_form_cell.html', context)
    
    # Nếu form không valid, trả về lỗi (ít khả năng xảy ra với form đơn giản)
    return HttpResponseBadRequest("Dữ liệu không hợp lệ")