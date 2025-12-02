# View cho app assessments
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.class_sessions.models import ClassSession

from .forms import AssessmentForm
from .models import Assessment

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