from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from apps.common.factories import (
    CenterFactory, SubjectFactory, UserFactory,
    KlassFactory, ClassSessionFactory, StudentProductFactory
)
from django.db import transaction

class Command(BaseCommand):
    help = "Seed database with factories and default groups"

    def add_arguments(self, parser):
        parser.add_argument('--centers', type=int, default=3)
        parser.add_argument('--subjects', type=int, default=5)
        parser.add_argument('--users', type=int, default=50)
        parser.add_argument('--classes', type=int, default=10)
        parser.add_argument('--sessions_per_class', type=int, default=5)
        parser.add_argument('--products', type=int, default=100)

    def handle(self, *args, **options):
        # mapping role code -> human group name
        ROLE_GROUPS = {
            "ADMIN": "Admin",
            "CENTER_MANAGER": "Center Manager",
            "TEACHER": "Teacher",
            "ASSISTANT": "Assistant",
            "PARENT": "Parent",
            "STUDENT": "Student",
        }

        # create groups if missing
        for group_name in ROLE_GROUPS.values():
            Group.objects.get_or_create(name=group_name)

        with transaction.atomic():
            # create centers and subjects
            centers = [CenterFactory() for _ in range(options['centers'])]
            subjects = [SubjectFactory() for _ in range(options['subjects'])]

            # decide counts per role
            total_users = options['users']
            admins_count = 2
            center_managers_count = max(1, options['centers'])
            teachers_count = max(5, options['classes'] // 2)
            assistants_count = max(3, options['classes'] // 3)
            parents_count = max(5, total_users // 10)
            # remaining -> students
            assigned = admins_count + center_managers_count + teachers_count + assistants_count + parents_count
            students_count = max(0, total_users - assigned)

            created_users = []

            # helpers
            def _create_and_assign(role_code, count, extra_attrs=None):
                g = Group.objects.get(name=ROLE_GROUPS[role_code])
                for _ in range(count):
                    attrs = dict(extra_attrs or {})
                    attrs['role'] = role_code
                    user = UserFactory(**attrs)
                    # ensure superuser/staff flags for ADMIN
                    if role_code == "ADMIN":
                        user.is_superuser = True
                        user.is_staff = True
                        user.save()
                    # center managers -> attach to a center
                    if role_code == "CENTER_MANAGER":
                        user.center = centers[_ % len(centers)]
                        user.save()
                    user.groups.add(g)
                    created_users.append(user)
                return

            _create_and_assign("ADMIN", admins_count)
            _create_and_assign("CENTER_MANAGER", center_managers_count)
            _create_and_assign("TEACHER", teachers_count)
            _create_and_assign("ASSISTANT", assistants_count)
            _create_and_assign("PARENT", parents_count)
            _create_and_assign("STUDENT", students_count)

            # create classes and sessions (reuse some created teachers)
            teachers = [u for u in created_users if u.role == "TEACHER"]
            if not teachers:
                teachers = [UserFactory(role="TEACHER") for _ in range(max(5, options['classes'] // 2))]

            classes = []
            for i in range(options['classes']):
                main_teacher = teachers[i % len(teachers)]
                classes.append(KlassFactory(main_teacher=main_teacher))

            # sessions
            sessions = []
            for klass in classes:
                for _ in range(options['sessions_per_class']):
                    sessions.append(ClassSessionFactory(klass=klass))

            # student products - pick from created students
            students = [u for u in created_users if u.role == "STUDENT"]
            if students:
                for i in range(options['products']):
                    StudentProductFactory(session=sessions[i % len(sessions)], student=students[i % len(students)])
        self.stdout.write(self.style.SUCCESS('Seeding finished.'))
