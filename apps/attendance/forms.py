from django import forms
from .models import Attendance, ATTEND_CHOICES


class AttendanceForm(forms.ModelForm):
    status = forms.ChoiceField(
        choices=ATTEND_CHOICES,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Ghi chú điểm danh...",
            }
        ),
    )

    class Meta:
        model = Attendance
        fields = ["status", "note"]

