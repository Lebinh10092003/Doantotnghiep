import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.common.factories import (
    CenterFactory, SubjectFactory, UserFactory,
    KlassFactory, ClassSessionFactory, StudentProductFactory
)
from apps.accounts.models import ParentStudentRelation, User
from apps.enrollments.models import Enrollment
from django.db import transaction
from django.db.utils import IntegrityError


class Command(BaseCommand):
    help = "Seed database with factories and default groups, fully linked data (center-subject-class-session-product)."

    def add_arguments(self, parser):
        parser.add_argument('--centers', type=int, default=5)
        parser.add_argument('--subjects', type=int, default=3)
        parser.add_argument('--users', type=int, default=100)
        parser.add_argument('--modules_per_subject', type=int, default=12)
        parser.add_argument('--sessions_per_module', type=int, default=12)

    def handle(self, *args, **options):
        # Mapping role code -> human-readable name
        ROLE_GROUPS = {
            "ADMIN": "Admin",
            "CENTER_MANAGER": "Center Manager",
            "TEACHER": "Teacher",
            "ASSISTANT": "Assistant",
            "PARENT": "Parent",
            "STUDENT": "Student",
        }

        # Create missing groups
        for group_name in ROLE_GROUPS.values():
            Group.objects.get_or_create(name=group_name)

        with transaction.atomic():
            # === CREATE CORE ENTITIES ===
            centers = [CenterFactory() for _ in range(options['centers'])]
            subjects = [SubjectFactory() for _ in range(options['subjects'])]

            total_users = options['users']
            admins_count = 2
            center_managers_count = options['centers']
            teachers_count = max(5, options['subjects'] * 2)
            assistants_count = max(3, options['subjects'])
            parents_count = max(10, total_users // 5)
            assigned = admins_count + center_managers_count + teachers_count + assistants_count + parents_count
            students_count = max(0, total_users - assigned)

            created_users = []

            # === HELPER FUNCTION TO CREATE USERS BY ROLE ===
            def _create_and_assign(role_code, count, extra_attrs=None):
                g = Group.objects.get(name=ROLE_GROUPS[role_code])
                for i in range(count):
                    attrs = dict(extra_attrs or {})
                    attrs['role'] = role_code
                    user = UserFactory(**attrs)
                    if role_code == "ADMIN":
                        user.is_superuser = True
                        user.is_staff = True
                        user.save()
                    elif role_code == "CENTER_MANAGER":
                        user.center = centers[i % len(centers)]
                        user.save()
                    elif role_code == "STUDENT":
                        user.center = random.choice(centers)
                        user.save()
                    user.groups.add(g)
                    created_users.append(user)

            # === CREATE USERS FOR ALL ROLES ===
            _create_and_assign("ADMIN", admins_count)
            _create_and_assign("CENTER_MANAGER", center_managers_count)
            _create_and_assign("TEACHER", teachers_count)
            _create_and_assign("ASSISTANT", assistants_count)
            _create_and_assign("PARENT", parents_count)
            _create_and_assign("STUDENT", students_count)

            # === BUILD RELATIONSHIPS ===
            teachers = [u for u in created_users if u.role == "TEACHER"]
            parents = [u for u in created_users if u.role == "PARENT"]
            students = [u for u in created_users if u.role == "STUDENT"]

            # --- Create Parent-Student relationships ---
            parent_student_relations = []
            if parents and students:
                for student in students:
                    # Each student gets 1 or 2 parents
                    num_parents = random.randint(1, 2)
                    assigned_parents = random.sample(parents, min(num_parents, len(parents)))
                    for parent in assigned_parents:
                        try:
                            relation, _ = ParentStudentRelation.objects.get_or_create(
                                parent=parent,
                                student=student,
                                defaults={'note': 'Auto-generated relation'}
                            )
                            parent_student_relations.append(relation)
                        except IntegrityError:
                            # This can happen if a parent is randomly selected twice for the same student
                            # Or if the relation already exists from a previous run.
                            # It's safe to ignore.
                            self.stdout.write(self.style.WARNING(f"Relation for {parent.username} and {student.username} already exists. Skipping."))
                            pass

            classes = []
            sessions = []

            # Create 12 modules per subject, 12 sessions per module
            for subject in subjects:
                for m in range(options['modules_per_subject']):
                    main_teacher = teachers[(m + subjects.index(subject)) % len(teachers)]
                    center = centers[(m + subjects.index(subject)) % len(centers)]

                    klass = KlassFactory(
                        main_teacher=main_teacher,
                        subject=subject,
                        center=center
                    )
                    classes.append(klass)

                    # === CREATE SESSIONS ===
                    for s in range(options['sessions_per_module']):
                        session = ClassSessionFactory(klass=klass)
                        sessions.append(session)

            # --- Enroll students in classes ---
            enrollments = []
            if students and classes:
                for klass in classes:
                    # Enroll 5 to 15 random students in each class
                    num_students_to_enroll = random.randint(5, min(15, len(students)))
                    students_for_this_class = random.sample(students, num_students_to_enroll)
                    for student in students_for_this_class:
                        enrollment, _ = Enrollment.objects.get_or_create(student=student, klass=klass)
                        enrollments.append(enrollment)

            # === CREATE STUDENT PRODUCTS (1 product per session) ===
            if students and sessions:
                for session in sessions:
                    student = random.choice(students)
                    StudentProductFactory(session=session, student=student)

        # === LOG RESULTS ===
        self.stdout.write(self.style.SUCCESS(
            f"""
✅ SEEDING COMPLETED
-----------------------------
Centers: {len(centers)}
Subjects: {len(subjects)}
Users: {len(created_users)} (Admins={admins_count}, Managers={center_managers_count}, Teachers={teachers_count}, Assistants={assistants_count}, Parents={parents_count}, Students={students_count})
Classes (Modules): {len(classes)}
Sessions: {len(sessions)}
Parent-Student Relations: {len(parent_student_relations)}
Enrollments: {len(enrollments)}
Student Products: {len(sessions)}
-----------------------------
All data are fully linked: Center → Subject → Class → Session → StudentProduct.
"""
        ))
