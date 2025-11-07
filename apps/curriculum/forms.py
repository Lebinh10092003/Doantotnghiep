from django import forms
from .models import Subject, Module, Lesson, Lecture, Exercise


class SubjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = "Tên Môn học"
        self.fields['code'].label = "Mã Môn học"
        self.fields['description'].label = "Mô tả"
        if 'avatar' in self.fields:
            self.fields['avatar'].label = "Ảnh đại diện"

    class Meta:
        model = Subject
        fields = ["name", "code", "description", "avatar"]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class ModuleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].label = "Môn học"
        self.fields['order'].label = "Thứ tự"
        self.fields['title'].label = "Tiêu đề"
        self.fields['description'].label = "Mô tả"
        if 'image' in self.fields:
            self.fields['image'].label = "Ảnh minh họa"

    class Meta:
        model = Module
        fields = ["subject", "order", "title", "description", "image"]
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class LessonForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['module'].label = "Học phần"
        self.fields['order'].label = "Thứ tự"
        self.fields['title'].label = "Tiêu đề"
        self.fields['objectives'].label = "Mục tiêu"

    class Meta:
        model = Lesson
        fields = ["module", "order", "title", "objectives"]
        widgets = {
            'module': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'objectives': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class LectureForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].label = "Nội dung"
        self.fields['file'].label = "Tệp đính kèm"
        self.fields['video_url'].label = "Liên kết nội dung (Video/Slide/Tài liệu)"

    class Meta:
        model = Lecture
        fields = ["content", "file", "video_url"]
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control'}),
        }


class ExerciseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].label = "Mô tả / Yêu cầu"
        self.fields['file'].label = "Tệp đính kèm"
        if 'link_url' in self.fields:
            self.fields['link_url'].label = "Liên kết nội dung (fallback nếu không tải được)"
        self.fields['difficulty'].label = "Độ khó"

    class Meta:
        model = Exercise
        fields = ["lesson", "description", "file", "link_url", "difficulty"]
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'link_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'difficulty': forms.Select(attrs={'class': 'form-select'}),
        }


class ImportCurriculumForm(forms.Form):
    file = forms.FileField(label="Chọn file Excel (.xlsx)")
