from django import forms
from django.forms.widgets import ClearableFileInput, Textarea, TextInput

from .models import StudentProduct
from .models import StudentExerciseSubmission


class StudentProductForm(forms.ModelForm):
    """
    Form để tạo/cập nhật sản phẩm của học viên (StudentProduct).
    Đảm bảo tiêu đề được nhập và phải có ít nhất một trong các trường: Ảnh, Video hoặc Mã nhúng.
    """
    class Meta:
        model = StudentProduct
        fields = ["title", "description", "image", "video", "embed_code"]
        widgets = {
            "title": TextInput(attrs={"class": "form-control", "placeholder": "Tiêu đề sản phẩm"}),
            "description": Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Mô tả ngắn về sản phẩm"}
            ),
            "embed_code": Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Mã nhúng (ví dụ iframe video)",
                }
            ),
            # Sửa các thuộc tính class cho input file để tương thích tốt hơn với Bootstrap
            "image": ClearableFileInput(attrs={"class": "form-control"}),
            "video": ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        title = cleaned.get("title")
        image = cleaned.get("image")
        video = cleaned.get("video")
        embed_code = (cleaned.get("embed_code") or "").strip()

        if not title:
            # Sửa thông báo lỗi
            self.add_error("title", "Vui lòng nhập tiêu đề.")

        if not (image or video or embed_code):
            # Sửa thông báo lỗi
            raise forms.ValidationError(
                "Vui lòng cung cấp ít nhất một nội dung: Ảnh, Video hoặc Mã nhúng."
            )
        return cleaned


class StudentExerciseSubmissionForm(forms.ModelForm):
    """
    Form để nộp bài tập của học viên (StudentExerciseSubmission).
    Đảm bảo tiêu đề được nhập và phải có ít nhất một trong hai trường: File hoặc Link URL.
    """
    class Meta:
        model = StudentExerciseSubmission
        fields = ["title", "description", "file", "link_url"]
        widgets = {
            # Sửa lỗi encoding
            "title": TextInput(attrs={"class": "form-control", "placeholder": "Tiêu đề bài nộp"}),
            # Sửa lỗi encoding
            "description": Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Mô tả ngắn"}),
            "file": ClearableFileInput(attrs={"class": "form-control"}),
            # Sửa lỗi encoding
            "link_url": TextInput(attrs={"class": "form-control", "placeholder": "Liên kết (nếu có)"}),
        }

    def clean(self):
        cleaned = super().clean()
        title = cleaned.get("title")
        file = cleaned.get("file")
        link_url = (cleaned.get("link_url") or "").strip()

        if not title:
            # Sửa lỗi encoding
            self.add_error("title", "Vui lòng nhập tiêu đề.")

        if not (file or link_url):
            # Sửa lỗi encoding
            raise forms.ValidationError("Vui lòng cung cấp ít nhất Tệp tin hoặc Liên kết.")
        return cleaned