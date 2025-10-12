from faker import Faker
from apps.curriculum.models import Subject, Module, Lesson, Lecture, Exercise

fake = Faker("vi_VN")

def seed_subjects(n=3, start=0):
    subjects = []
    for i in range(start, start + n):
        code = f"S{100 + i}"
        subject, _ = Subject.objects.get_or_create(
            code=code,
            defaults={
                "name": f"{fake.word().capitalize()} Subject {i}",
                "description": fake.text(max_nb_chars=100),
            },
        )
        subjects.append(subject)
    print(f"✅ Seeded {len(subjects)} subjects")
    return subjects


def seed_modules(subjects, modules_per_subject=2):
    modules = []
    for subject in subjects:
        for order in range(1, modules_per_subject + 1):
            module, _ = Module.objects.get_or_create(
                subject=subject,
                order=order,
                defaults={
                    "title": f"Học phần {order} của {subject.name}",
                    "description": fake.text(max_nb_chars=150),
                },
            )
            modules.append(module)
    print(f"✅ Seeded {len(modules)} modules")
    return modules


def seed_lessons(modules, lessons_per_module=3):
    lessons = []
    for module in modules:
        for order in range(1, lessons_per_module + 1):
            lesson, _ = Lesson.objects.get_or_create(
                module=module,
                order=order,
                defaults={
                    "title": f"Bài {order} - {fake.sentence(nb_words=4)}",
                    "objectives": fake.text(max_nb_chars=120),
                },
            )
            lessons.append(lesson)
    print(f"✅ Seeded {len(lessons)} lessons")
    return lessons


def seed_lectures(lessons):
    lectures = []
    for lesson in lessons:
        lecture, created = Lecture.objects.get_or_create(
            lesson=lesson,
            defaults={
                "content": fake.paragraph(nb_sentences=5),
                "video_url": f"https://example.com/videos/{lesson.id}",
            },
        )
        if created:
            lectures.append(lecture)
    print(f"✅ Seeded {len(lectures)} lectures")
    return lectures


def seed_exercises(lessons):
    exercises = []
    for lesson in lessons:
        exercise, created = Exercise.objects.get_or_create(
            lesson=lesson,
            defaults={
                "description": fake.text(max_nb_chars=200),
                "difficulty": fake.random_element(["easy", "medium", "hard"]),
            },
        )
        if created:
            exercises.append(exercise)
    print(f"✅ Seeded {len(exercises)} exercises")
    return exercises


def seed_curriculum():
    subjects = seed_subjects(3)
    modules = seed_modules(subjects)
    lessons = seed_lessons(modules)
    seed_lectures(lessons)
    seed_exercises(lessons)
    print("🎯 Curriculum seeding completed!")
