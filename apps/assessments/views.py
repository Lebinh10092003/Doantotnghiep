# apps/assessments/views.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
from .models import Assessment
from .forms import AssessmentForm
from apps.class_sessions.models import ClassSession
from apps.accounts.models import User

@require_POST
@login_required
@permission_required("assessments.change_assessment") # Hoặc "assessments.add_assessment"
def update_assessment(request, session_id, student_id):
    session = get_object_or_404(ClassSession, pk=session_id)
    student = get_object_or_404(User, pk=student_id)
    
    # Lấy hoặc tạo mới bản ghi đánh giá
    assessment, created = Assessment.objects.get_or_create(
        session=session, 
        student=student
    )
    
    form = AssessmentForm(request.POST, instance=assessment)
    
    if form.is_valid():
        updated_assessment = form.save()
        context = {
            'session': session,
            'student': student,
            'assessment': updated_assessment
        }
        # Trả về fragment template (sẽ tạo ở Bước 5)
        return render(request, '_assessment_form_cell.html', context)
        
    return HttpResponseBadRequest("Dữ liệu không hợp lệ")