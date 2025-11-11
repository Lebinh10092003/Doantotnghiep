import random
from collections import defaultdict
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.utils import IntegrityError

from apps.common.factories import (
    CenterFactory,
    SubjectFactory,
    UserFactory,
    KlassFactory,
    ClassSessionFactory,
    StudentProductFactory,
)
from apps.accounts.models import ParentStudentRelation, User
from apps.classes.models import ClassSchedule
from apps.class_sessions.models import ClassSession
from apps.enrollments.models import Enrollment
from apps.curriculum.models import Lesson


class Command(BaseCommand):
    help = (
        "Seed database with factories and default groups. "
        "Creates 5 centers, 50 users (all assigned a center), 3 subjects, "
        "classes with schedules, and generates sessions accordingly."
    )

    def add_arguments(self, parser):
        parser.add_argument("--centers", type=int, default=5)
        parser.add_argument("--subjects", type=int, default=3)
        parser.add_argument("--users", type=int, default=50)
        parser.add_argument("--modules_per_subject", type=int, default=12)
        parser.add_argument("--classes", type=int, default=5)

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting Database Seeding ---"))

        ROLE_GROUPS = {
            "ADMIN": "Admin",
            "CENTER_MANAGER": "Center Manager",
            "TEACHER": "Teacher",
            "ASSISTANT": "Assistant",
            "PARENT": "Parent",
            "STUDENT": "Student",
        }

        # Ensure groups exist
        for group_name in ROLE_GROUPS.values():
            Group.objects.get_or_create(name=group_name)

        with transaction.atomic():
            # === CORE ENTITIES ===
            centers = [CenterFactory() for _ in range(options["centers"])]
            subjects = [SubjectFactory() for _ in range(options["subjects"])]

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {len(centers)} Centers and {len(subjects)} Subjects."
                )
            )

            # === USER COUNTS ===
            total_users = options["users"]
            admins_count = 2
            center_managers_count = options["centers"]
            teachers_count = max(5, options["subjects"] * 2)  # >=6 for 3 subjects
            assistants_count = max(3, options["subjects"])    # >=3
            parents_count = max(10, total_users // 5)         # >=10
            assigned = (
                admins_count
                + center_managers_count
                + teachers_count
                + assistants_count
                + parents_count
            )
            students_count = max(0, total_users - assigned)

            created_users = []

            # === USER CREATION HELPER ===
            def _create_and_assign(role_code, count, extra_attrs=None):
                g = Group.objects.get(name=ROLE_GROUPS[role_code])
                for i in range(count):
                    attrs = dict(extra_attrs or {})
                    attrs["role"] = role_code
                    user = UserFactory(**attrs)
                    # All users belong to a center
                    user.center = centers[i % len(centers)]
                    if role_code == "ADMIN":
                        user.is_superuser = True
                        user.is_staff = True
                    user.save()
                    user.groups.add(g)
                    created_users.append(user)

            # === CREATE USERS ===
            _create_and_assign("ADMIN", admins_count)
            _create_and_assign("CENTER_MANAGER", center_managers_count)
            _create_and_assign("TEACHER", teachers_count)
            _create_and_assign("ASSISTANT", assistants_count)
            _create_and_assign("PARENT", parents_count)
            _create_and_assign("STUDENT", students_count)

            # === ROLE LISTS ===
            teachers = [u for u in created_users if u.role == "TEACHER"]
            assistants = [u for u in created_users if u.role == "ASSISTANT"]
            parents = [u for u in created_users if u.role == "PARENT"]
            students = [u for u in created_users if u.role == "STUDENT"]

            # --- Parent-Student relationships ---
            parent_student_relations = []
            if parents and students:
                for student in students:
                    num_parents = random.randint(1, 2)
                    assigned_parents = random.sample(
                        parents, min(num_parents, len(parents))
                    )
                    for parent in assigned_parents:
                        try:
                            relation, _ = ParentStudentRelation.objects.get_or_create(
                                parent=parent,
                                student=student,
                                defaults={"note": "Auto-generated relation"},
                            )
                            parent_student_relations.append(relation)
                        except IntegrityError:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Relation for {parent.username} and {student.username} already exists. Skipping."
                                )
                            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {len(parent_student_relations)} Parent-Student Relations."
                )
            )

            # === CLASSES AND SESSIONS ===
            classes = []
            sessions = []
            schedules = []
            teacher_index = 0

            # Create exactly N classes, each bound to a subject
            for c in range(options["classes"]):
                subject = subjects[c % len(subjects)]
                main_teacher = teachers[teacher_index % len(teachers)]
                teacher_index += 1
                center = centers[c % len(centers)]

                start_date = date.today() - timedelta(days=random.randint(15, 45))
                end_date = start_date + timedelta(days=random.randint(60, 90))

                klass = KlassFactory(
                    main_teacher=main_teacher,
                    subject=subject,
                    center=center,
                    start_date=start_date,
                    end_date=end_date,
                )
                # Thêm 0 đến 2 trợ giảng ngẫu nhiên cho mỗi lớp
                if assistants:
                    num_assistants = random.randint(0, min(2, len(assistants)))
                    if num_assistants > 0:
                        # Lấy ngẫu nhiên các trợ giảng từ danh sách
                        selected_assistants = random.sample(assistants, num_assistants)
                        
                        # Thêm trợ giảng vào lớp học.
                        # Django sẽ tự động tạo các bản ghi ClassAssistant.
                        klass.assistants.add(*selected_assistants)
                classes.append(klass)

                # Tạo lịch học hàng tuần cho lớp
                days_of_week = random.sample(range(7), random.randint(1, 3))
                for day in days_of_week:
                    start_hour = random.randint(8, 18)
                    start_minute = random.choice([0, 30])
                    start_time = time(start_hour, start_minute)
                    end_time = (
                        (datetime.combine(date.today(), start_time) + timedelta(minutes=90))
                    ).time()
                    
                    schedule, _ = ClassSchedule.objects.get_or_create(
                        klass=klass,
                        day_of_week=day,
                        start_time=start_time,
                        defaults={'end_time': end_time}
                    )
                    schedules.append(schedule)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {len(classes)} Classes and {len(schedules)} Weekly Schedules."
                )
            )

            # Tạo các buổi học (ClassSession) từ lịch học (ClassSchedule)
            all_lessons = list(Lesson.objects.all())
            for klass in classes:
                klass_schedules = ClassSchedule.objects.filter(klass=klass)
                if not klass_schedules.exists() or not klass.start_date or not klass.end_date:
                    continue

                sessions_to_create = []
                current_date = klass.start_date
                while current_date <= klass.end_date:
                    day_schedules = klass_schedules.filter(day_of_week=current_date.weekday())
                    for schedule in day_schedules:
                        sessions_to_create.append(
                            ClassSession(
                                klass=klass,
                                date=current_date,
                                start_time=schedule.start_time,
                                end_time=schedule.end_time,
                                lesson=random.choice(all_lessons) if all_lessons else None,
                            )
                        )
                    current_date += timedelta(days=1)
                
                sessions_to_create.sort(key=lambda s: (s.date, s.start_time))
                for i, session in enumerate(sessions_to_create, 1):
                    session.index = i
                
                created = ClassSession.objects.bulk_create(sessions_to_create, ignore_conflicts=True)
                sessions.extend(created)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Generated {len(sessions)} Sessions from schedules."
                )
            )

            # --- Enroll students in classes ---
            enrollments = []
            if students and classes:
                for klass in classes:
                    # Enroll 10 to 20 random students per class, or up to available
                    upper = min(20, len(students))
                    lower = min(10, upper) if upper > 0 else 0
                    if lower == 0:
                        continue
                    num_students_to_enroll = random.randint(lower, upper)
                    students_for_class = random.sample(students, num_students_to_enroll)
                    for student in students_for_class:
                        enrollment, _ = Enrollment.objects.get_or_create(
                            student=student, klass=klass
                        )
                        enrollments.append(enrollment)

            self.stdout.write(
                self.style.SUCCESS(f"Created {len(enrollments)} Enrollments.")
            )

            # === STUDENT PRODUCTS only for enrolled students of the session's class ===
            enrolled_by_klass = defaultdict(list)
            student_by_id = {s.id: s for s in students}
            for e in enrollments:
                s_obj = student_by_id.get(e.student_id)
                if s_obj:
                    enrolled_by_klass[e.klass_id].append(s_obj)

            rr_counter_by_klass = defaultdict(int)
            student_product_count = 0
            for session in sessions:
                pool = enrolled_by_klass.get(session.klass_id, [])
                if not pool:
                    continue
                idx = rr_counter_by_klass[session.klass_id] % len(pool)
                rr_counter_by_klass[session.klass_id] += 1
                student = pool[idx]
                StudentProductFactory(session=session, student=student)
                student_product_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {student_product_count} Student Products."
                )
            )

        # === FINAL LOG ===
        self.stdout.write(
            self.style.SUCCESS(
                f"""
✅ SEEDING COMPLETED
-----------------------------
Centers: {len(centers)}
Subjects: {len(subjects)}
Users: {len(created_users)} (Admins={admins_count}, Managers={center_managers_count}, Teachers={teachers_count}, Assistants={assistants_count}, Parents={parents_count}, Students={students_count})
Classes: {len(classes)}  (requested={options['classes']})
Schedules: {len(schedules)}
Sessions: {len(sessions)}
Parent-Student Relations: {len(parent_student_relations)}
Enrollments: {len(enrollments)}
Student Products: {student_product_count}
-----------------------------
All data linked: Center → Subject → Class → Session → StudentProduct (enrollment-validated).
"""
            )
        )
