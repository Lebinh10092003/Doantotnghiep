from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.common.factories import (
    CenterFactory, SubjectFactory, UserFactory,
    KlassFactory, ClassSessionFactory, StudentProductFactory
)
from django.db import transaction


class Command(BaseCommand):
    help = "Seed database with factories and default groups, fully linked data (center-subject-class-session-product)."

    def add_arguments(self, parser):
        parser.add_argument('--centers', type=int, default=5)
        parser.add_argument('--subjects', type=int, default=3)
        parser.add_argument('--users', type=int, default=50)
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
            parents_count = max(5, total_users // 10)
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
            students = [u for u in created_users if u.role == "STUDENT"]

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

            # === CREATE STUDENT PRODUCTS (1 product per session) ===
            if students and sessions:
                for i, session in enumerate(sessions):
                    student = students[i % len(students)]
                    StudentProductFactory(session=session, student=student)

        # === LOG RESULTS ===
        self.stdout.write(self.style.SUCCESS(
            f"""
✅ SEEDING COMPLETED
-----------------------------
Centers: {len(centers)}
Subjects: {len(subjects)}
Users: {len(created_users)} (Admins={admins_count}, Teachers={teachers_count}, Students={students_count})
Classes (Modules): {len(classes)}
Sessions: {len(sessions)}
Student Products: {len(sessions)} (1 per session)
-----------------------------
All data are fully linked: Center → Subject → Class → Session → StudentProduct.
"""
        ))
