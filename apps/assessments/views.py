# View cho app assessments

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min, Q
from django.http import HttpResponseBadRequest, QueryDict
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.class_sessions.models import ClassSession
from apps.common.utils.http import is_htmx_request
from apps.filters.models import SavedFilter
from apps.filters.utils import build_filter_badges, determine_active_filter_name

from .filters import (
    AssessmentRecordFilter,
    AssessmentSummaryFilter,
    StudentAssessmentFilter,
)
from .forms import AssessmentForm
from .models import Assessment


def _ensure_mutable_querydict(params_source):
    if isinstance(params_source, QueryDict):
        cloned = params_source.copy()
        cloned._mutable = True
        return cloned

    qd = QueryDict("", mutable=True)
    if not params_source:
        return qd

    items = params_source.items() if hasattr(params_source, "items") else params_source
    for key, value in items:
        if isinstance(value, (list, tuple)):
            for item in value:
                qd.appendlist(key, item)
        else:
            qd.appendlist(key, value)
    return qd


def _build_filter_ui_context(
    request,
    filterset,
    *,
    model_name: str,
    target_id: str = "filterable-content",
    data=None,
):
    params_source = data if data is not None else request.GET
    active_filter_badges = build_filter_badges(filterset)

    current_query = _ensure_mutable_querydict(params_source)
    for key in ("page", "per_page"):
        current_query.pop(key, None)
    current_query_params = current_query.urlencode()

    saved_filters = SavedFilter.objects.filter(model_name=model_name).filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()
    active_filter_name = determine_active_filter_name(
        request, saved_filters, query_params=current_query
    )

    return {
        "filter": filterset,
        "active_filter_badges": active_filter_badges,
        "active_filter_name": active_filter_name,
        "current_query_params": current_query_params,
        "model_name": model_name,
        "target_id": target_id,
    }


@login_required
@permission_required("assessments.view_assessment", raise_exception=True)
def assessment_list(request):
    base_queryset = (
        Assessment.objects.select_related(
            "session__klass__center",
            "session__klass__subject",
            "session__klass__main_teacher",
            "session__lesson",
            "session",
            "student",
        )
        .order_by("-session__date", "-session__index", "student__username")
    )

    filterset = AssessmentRecordFilter(request.GET or None, queryset=base_queryset)
    filtered_qs = filterset.qs

    stats = filtered_qs.aggregate(
        total=Count("id"),
        scored=Count("id", filter=Q(score__isnull=False)),
        pending=Count("id", filter=Q(score__isnull=True)),
        avg_score=Avg("score"),
    )

    paginator = Paginator(filtered_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "stats": stats,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="AssessmentRecord",
        )
    )

    if is_htmx_request(request):
        return render(
            request,
            "assessments/_assessment_list_filterable_content.html",
            context,
        )
    return render(request, "assessments/assessment_list.html", context)


@login_required
@permission_required("assessments.view_assessment", raise_exception=True)
def student_results(request):
    students_base = (
        User.objects.filter(assessments__isnull=False)
        .select_related("center")
        .distinct()
    )

    filterset = StudentAssessmentFilter(request.GET or None, queryset=students_base)

    students = filterset.qs.annotate(
        assessments_count=Count("assessments", distinct=True),
        completed_count=Count(
            "assessments",
            filter=Q(assessments__score__isnull=False),
            distinct=True,
        ),
        avg_score=Avg("assessments__score"),
        max_score=Max("assessments__score"),
        min_score=Min("assessments__score"),
        last_session_date=Max("assessments__session__date"),
    ).order_by("-avg_score", "username")

    paginator = Paginator(students, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    cleaned_data = filterset.form.cleaned_data if filterset.form.is_valid() else {}

    assessment_scope = Assessment.objects.select_related("student", "session__klass")

    center = cleaned_data.get("center")
    if center:
        assessment_scope = assessment_scope.filter(student__center=center)

    start_date = cleaned_data.get("start_date")
    if start_date:
        assessment_scope = assessment_scope.filter(session__date__gte=start_date)

    end_date = cleaned_data.get("end_date")
    if end_date:
        assessment_scope = assessment_scope.filter(session__date__lte=end_date)

    search_value = cleaned_data.get("search")
    if search_value:
        keyword = search_value.strip()
        if keyword:
            assessment_scope = assessment_scope.filter(
                Q(student__first_name__icontains=keyword)
                | Q(student__last_name__icontains=keyword)
                | Q(student__username__icontains=keyword)
                | Q(student__email__icontains=keyword)
            )

    assessment_scope = assessment_scope.filter(
        student__in=filterset.qs.values_list("pk", flat=True)
    )

    summary = {
        "total_students": filterset.qs.count(),
        "total_assessments": assessment_scope.count(),
        "scored_assessments": assessment_scope.filter(score__isnull=False).count(),
        "avg_score": assessment_scope.aggregate(avg=Avg("score"))["avg"],
    }

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "summary": summary,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="AssessmentStudentResults",
        )
    )

    if is_htmx_request(request):
        return render(
            request,
            "assessments/_student_results_filterable_content.html",
            context,
        )
    return render(request, "assessments/student_results.html", context)


@login_required
@permission_required("assessments.view_assessment", raise_exception=True)
def assessment_summary(request):
    base_queryset = Assessment.objects.select_related(
        "session__klass__center",
        "session__klass__subject",
        "session",
        "student",
    )

    filterset = AssessmentSummaryFilter(request.GET or None, queryset=base_queryset)
    filtered_qs = filterset.qs

    stats = filtered_qs.aggregate(
        total_assessments=Count("id"),
        scored_assessments=Count("id", filter=Q(score__isnull=False)),
        pending_assessments=Count("id", filter=Q(score__isnull=True)),
        avg_score=Avg("score"),
        latest_session=Max("session__date"),
        distinct_students=Count("student", distinct=True),
        distinct_classes=Count("session__klass", distinct=True),
    )

    score_distribution = {
        "excellent": filtered_qs.filter(score__gte=9).count(),
        "good": filtered_qs.filter(score__gte=8, score__lt=9).count(),
        "fair": filtered_qs.filter(score__gte=6.5, score__lt=8).count(),
        "average": filtered_qs.filter(score__gte=5, score__lt=6.5).count(),
        "below_average": filtered_qs.filter(score__lt=5, score__isnull=False).count(),
        "no_score": filtered_qs.filter(score__isnull=True).count(),
    }
    score_distribution_total = sum(score_distribution.values())

    center_stats = list(
        filtered_qs.filter(score__isnull=False)
        .values("session__klass__center__id", "session__klass__center__name")
        .annotate(
            assessment_count=Count("id"),
            avg_score=Avg("score"),
            student_count=Count("student", distinct=True),
        )
        .order_by("session__klass__center__name")
    )

    top_classes = list(
        filtered_qs.filter(score__isnull=False)
        .values(
            "session__klass__id",
            "session__klass__name",
            "session__klass__code",
            "session__klass__center__name",
        )
        .annotate(
            avg_score=Avg("score"),
            assessment_count=Count("id"),
            student_count=Count("student", distinct=True),
        )
        .order_by("-avg_score", "-assessment_count")[:5]
    )

    recent_assessments = list(
        filtered_qs.order_by("-session__date", "-session__index", "-id")[:10]
    )

    context = {
        "stats": stats,
        "score_distribution": score_distribution,
        "score_distribution_total": score_distribution_total,
        "center_stats": center_stats,
        "top_classes": top_classes,
        "recent_assessments": recent_assessments,
    }
    context.update(
        _build_filter_ui_context(
            request,
            filterset,
            model_name="AssessmentSummary",
        )
    )

    if is_htmx_request(request):
        return render(
            request,
            "assessments/_assessment_summary_filterable_content.html",
            context,
        )
    return render(request, "assessments/assessment_summary.html", context)

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