# apps/common/management/commands/seed_db.py
import random
from collections import defaultdict
from datetime import date, time, timedelta, datetime

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.utils import IntegrityError
from faker import Faker

# Import các Factory từ app common
from apps.common.factories import (
    CenterFactory,
    SubjectFactory,
    UserFactory,
    KlassFactory,
)

# Import các Model từ tất cả các app
# Thứ tự import này chỉ để tham chiếu, thứ tự thực thi mới quan trọng
from apps.accounts.models import ParentStudentRelation, User, UserCodeCounter
from apps.centers.models import Center, Room
from apps.classes.models import Class as Klass, ClassSchedule
from apps.class_sessions.models import ClassSession
from apps.curriculum.models import Subject, Module, Lesson, Lecture, Exercise
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.attendance.models import Attendance
from apps.assessments.models import Assessment
from apps.rewards.models import PointAccount, RewardItem, RewardTransaction
from apps.notifications.models import Notification
from apps.students.models import StudentProduct

# Khởi tạo Faker
fake = Faker("vi_VN")


class Command(BaseCommand):
    help = (
        "Seed database with factories and default groups for all applications. "
        "Creates curriculum (12x12), users, classes, sessions (with absolute index), "
        "enrollments, attendance, assessments, rewards, and notifications."
    )

    def add_arguments(self, parser):
        parser.add_argument("--centers", type=int, default=3, help="Số lượng Trung tâm")
        parser.add_argument("--rooms_per_center", type=int, default=4, help="Số phòng học mỗi trung tâm")
        parser.add_argument("--subjects", type=int, default=4, help="Số lượng Môn học")
        parser.add_argument("--modules_per_subject", type=int, default=12, help="Số Module mỗi Môn học (12)")
        parser.add_argument("--lessons_per_module", type=int, default=12, help="Số Bài học mỗi Module (12)")
        parser.add_argument("--users", type=int, default=100, help="Tổng số Người dùng (sẽ được chia vai trò)")
        parser.add_argument("--classes", type=int, default=10, help="Số lượng Lớp học")
        parser.add_argument("--center_managers_per_center", type=int, default=None, help="Số quản lý mỗi trung tâm (nếu bỏ trống sẽ mặc định 1)")
        parser.add_argument("--teachers_per_center", type=int, default=None, help="Số giáo viên mỗi trung tâm (tùy chọn)")
        parser.add_argument("--assistants_per_center", type=int, default=None, help="Số trợ giảng mỗi trung tâm (tùy chọn)")
        parser.add_argument("--students_per_center", type=int, default=None, help="Số học sinh mỗi trung tâm (tùy chọn)")
        parser.add_argument("--parents_per_center", type=int, default=None, help="Số phụ huynh mỗi trung tâm (tùy chọn)")

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Starting Database Seeding ---"))
        today = date.today()

        # === 1. TẠO NHÓM (GROUP) VAI TRÒ (Cần cho User) ===
        ROLE_GROUPS = {
            "ADMIN": "Admin",
            "CENTER_MANAGER": "Center Manager",
            "TEACHER": "Teacher",
            "ASSISTANT": "Assistant",
            "PARENT": "Parent",
            "STUDENT": "Student",
        }
        ROLE_CODE_PREFIX = {
            "ADMIN": "ADM",
            "CENTER_MANAGER": "CTR",
            "TEACHER": "TEA",
            "ASSISTANT": "AST",
            "PARENT": "PAR",
            "STUDENT": "STD",
        }
        groups_by_name = {}
        for role_code, group_name in ROLE_GROUPS.items():
            group, _ = Group.objects.get_or_create(name=group_name)
            groups_by_name[role_code] = group
        self.stdout.write(self.style.SUCCESS(f"Ensured {len(ROLE_GROUPS)} Groups exist."))

        # === 2. TẠO TRUNG TÂM & PHÒNG HỌC (Cần cho User, Class) ===
        centers = [CenterFactory() for _ in range(options["centers"])]
        rooms = []
        for center in centers:
            for i in range(options["rooms_per_center"]):
                room_name = f"Phòng {i+1} ({center.code})"
                room, _ = Room.objects.get_or_create(center=center, name=room_name)
                rooms.append(room)
        self.stdout.write(self.style.SUCCESS(f"Created {len(centers)} Centers and {len(rooms)} Rooms (idempotent)."))

        # === 3. TẠO CHƯƠNG TRÌNH HỌC (Cần cho Class, ClassSession) ===
        subjects = [SubjectFactory() for _ in range(options["subjects"])]
        all_modules = []
        all_lessons = []
        all_lectures = []
        all_exercises = []
        
        # Tạo một bản đồ (map) các bài học theo môn học để gán cho ClassSession
        lessons_by_subject = defaultdict(list)
        lessons_per_module_count = options["lessons_per_module"] # = 12

        for subject in subjects:
            for i in range(options["modules_per_subject"]): # 12 modules
                module, _ = Module.objects.get_or_create(
                    subject=subject,
                    order=i + 1,
                    defaults={
                        "title": f"{subject.name} - Module {i+1}",
                        "description": fake.sentence(nb_words=15),
                    },
                )
                all_modules.append(module)
                for j in range(lessons_per_module_count): # 12 lessons
                    lesson, _ = Lesson.objects.get_or_create(
                        module=module,
                        order=j + 1,
                        defaults={
                            "title": f"Bài {j+1}: {fake.sentence(nb_words=6)}",
                            "objectives": fake.text(max_nb_chars=200),
                        },
                    )
                    all_lessons.append(lesson)
                    
                    if random.random() < 0.7:
                        lecture, _ = Lecture.objects.get_or_create(
                            lesson=lesson,
                            defaults={"content": fake.text(max_nb_chars=400)},
                        )
                        all_lectures.append(lecture)
                    if random.random() < 0.5:
                        exercise, _ = Exercise.objects.get_or_create(
                            lesson=lesson,
                            defaults={"description": fake.text(max_nb_chars=200)},
                        )
                        all_exercises.append(exercise)
            
            lessons_by_subject[subject.id] = list(
                Lesson.objects.filter(module__subject=subject).order_by("module__order", "order")
            )
        
        # Khử trùng lặp (trường hợp seed lại nhiều lần)
        all_modules = list({m.id: m for m in all_modules}.values())
        all_lessons = list({l.id: l for l in all_lessons}.values())
        all_lectures = list({lec.id: lec for lec in all_lectures}.values())
        all_exercises = list({ex.id: ex for ex in all_exercises}.values())

        self.stdout.write(self.style.SUCCESS(f"Ensured {len(subjects)} Subjects, {len(all_modules)} Modules, {len(all_lessons)} Lessons (Structure: {options['modules_per_subject']}x{lessons_per_module_count})."))

        # === 4. TẠO NGƯỜI DÙNG (Cần cho mọi thứ khác) ===
        total_users = options["users"]
        centers_count = options["centers"]
        subjects_count = options["subjects"]

        admins_count = 2
        center_managers_count = centers_count  # Mỗi trung tâm 1 quản lý
        teachers_count = max(10, subjects_count * 3)
        assistants_count = max(5, subjects_count * 2)
        parents_count = max(15, total_users // 4)
        assigned = admins_count + center_managers_count + teachers_count + assistants_count + parents_count
        students_count = max(20, total_users - assigned)

        if options["center_managers_per_center"] is not None:
            center_managers_count = centers_count * max(0, options["center_managers_per_center"])
        if options["teachers_per_center"] is not None:
            teachers_count = centers_count * max(0, options["teachers_per_center"])
        if options["assistants_per_center"] is not None:
            assistants_count = centers_count * max(0, options["assistants_per_center"])
        if options["parents_per_center"] is not None:
            parents_count = centers_count * max(0, options["parents_per_center"])
        if options["students_per_center"] is not None:
            students_count = centers_count * max(0, options["students_per_center"])

        created_users = []
        users_by_role = defaultdict(list)

        def _ensure_group(user, role_code):
            g = groups_by_name[role_code]
            if not user.groups.filter(pk=g.pk).exists():
                user.groups.add(g)

        def _unique_username(prefix: str) -> str:
            idx = 1
            while True:
                candidate = f"{prefix}{idx:04d}"
                if not User.objects.filter(username=candidate).exists():
                    return candidate
                idx += 1

        def _unique_national_id() -> str:
            while True:
                candidate = f"NID{random.randint(0, 999999999):09d}"
                if not User.objects.filter(national_id=candidate).exists():
                    return candidate

        def _random_phone() -> str:
            return f"09{random.randint(10000000, 99999999)}"

        def _clean_address(text: str) -> str:
            return text.replace("\n", ", ")

        def _ensure_user_profile(user: User, role_code: str, center_choices):
            updated = False
            prefix = ROLE_CODE_PREFIX.get(role_code, "USR")
            if role_code != "ADMIN" and not user.center and center_choices:
                user.center = random.choice(center_choices)
                updated = True
            if not user.user_code:
                user.user_code = UserCodeCounter.next_code(prefix)
                updated = True
            if not user.email:
                user.email = f"{user.username}@seed.local"
                updated = True
            if not user.phone:
                user.phone = _random_phone()
                updated = True
            if not user.address:
                user.address = _clean_address(fake.address())
                updated = True
            if not user.national_id:
                user.national_id = _unique_national_id()
                updated = True
            if not user.dob:
                user.dob = fake.date_of_birth(minimum_age=7, maximum_age=55)
                updated = True
            if not user.gender:
                user.gender = random.choice(["M", "F", "O"])
                updated = True
            if updated:
                user.save()

        # Nạp sẵn user đang có theo role để tránh trùng lặp khi seed lại
        for role_code in ROLE_GROUPS.keys():
            existing = list(User.objects.filter(role=role_code))
            for user in existing:
                _ensure_group(user, role_code)
            users_by_role[role_code].extend(existing)

        # Hàm helper để tạo user, gán role, group VÀ center (chỉ tạo thêm nếu thiếu)
        def _create_and_assign(role_code, count, center_pool):
            g = groups_by_name[role_code]
            existing_count = len(users_by_role[role_code])
            missing = max(0, count - existing_count)
            for i in range(missing):
                base_prefix = role_code.lower()
                username = _unique_username(base_prefix)
                national_id = _unique_national_id()
                assigned_center = None
                if role_code != "ADMIN" and center_pool:
                    assigned_center = center_pool[(existing_count + i) % len(center_pool)]
                user = UserFactory(
                    role=role_code,
                    username=username,
                    national_id=national_id,
                    center=assigned_center,
                )

                if role_code == "ADMIN":
                    user.is_superuser = True
                    user.is_staff = True

                user.save()
                user.groups.add(g)
                created_users.append(user)
                users_by_role[role_code].append(user)

        _create_and_assign("ADMIN", admins_count, center_pool=None)
        _create_and_assign("CENTER_MANAGER", center_managers_count, center_pool=centers) 
        _create_and_assign("TEACHER", teachers_count, center_pool=centers)
        _create_and_assign("ASSISTANT", assistants_count, center_pool=centers)
        _create_and_assign("PARENT", parents_count, center_pool=centers)
        _create_and_assign("STUDENT", students_count, center_pool=centers)

        for role_code, user_list in users_by_role.items():
            for user in user_list:
                _ensure_user_profile(user, role_code, centers)

        # Lưu lại các danh sách đã được tạo
        teachers = users_by_role["TEACHER"]
        assistants = users_by_role["ASSISTANT"]
        parents = users_by_role["PARENT"]
        students = users_by_role["STUDENT"]

        def _group_by_center(user_list):
            grouped = defaultdict(list)
            for user in user_list:
                if user.center_id:
                    grouped[user.center_id].append(user)
            return grouped

        teachers_by_center = _group_by_center(teachers)
        assistants_by_center = _group_by_center(assistants)
        parents_by_center = _group_by_center(parents)
        students_by_center = _group_by_center(students)
        
        total_user_count = sum(len(v) for v in users_by_role.values())
        self.stdout.write(self.style.SUCCESS(f"Prepared {total_user_count} Users (created {len(created_users)}) with roles and centers assigned."))

        # === 5. TẠO QUAN HỆ PHỤ HUYNH - HỌC SINH (Depends on User) ===
        parent_student_relations = []
        if parents and students:
            for center in centers:
                center_students = students_by_center.get(center.id, [])
                if not center_students:
                    continue
                center_parents = parents_by_center.get(center.id, [])
                fallback_parents = parents if parents else []
                for student in center_students:
                    source_parents = center_parents or fallback_parents
                    if not source_parents:
                        continue
                    max_parents = min(2, len(source_parents))
                    num_parents = random.randint(1, max_parents)
                    assigned_parents = random.sample(source_parents, num_parents)
                    for parent in assigned_parents:
                        relation, _ = ParentStudentRelation.objects.get_or_create(
                            parent=parent,
                            student=student,
                            defaults={"note": "Auto-generated"},
                        )
                        parent_student_relations.append(relation)
        self.stdout.write(self.style.SUCCESS(f"Created {len(parent_student_relations)} Parent-Student Relations."))

        # === 6. TẠO LỚP HỌC & LỊCH HỌC (Depends on C-R-S-U) ===
        def _unique_class_code():
            while True:
                candidate = f"CLS{random.randint(0, 999999):06d}"
                if not Klass.objects.filter(code=candidate).exists():
                    return candidate

        classes = []
        schedules = []
        if not teachers:
             self.stdout.write(self.style.WARNING("No teachers found. Classes will have no main teacher."))
        
        for c in range(options["classes"]):
            # CHỌN LOGIC: Lớp học phải thuộc 1 center, 1 subject, 1 giáo viên
            subject = random.choice(subjects)
            center = random.choice(centers)
            # Lọc giáo viên thuộc trung tâm đó (hoặc bất kỳ nếu không có)
            possible_teachers = [t for t in teachers if t.center == center] or teachers
            main_teacher = random.choice(possible_teachers) if possible_teachers else None
            # Lọc phòng học thuộc trung tâm đó
            possible_rooms = [r for r in rooms if r.center == center] or rooms
            
            start_date = date.today() - timedelta(days=random.randint(15, 45))
            end_date = start_date + timedelta(days=random.randint(90, 120)) 

            klass = KlassFactory(
                code=_unique_class_code(),
                main_teacher=main_teacher,
                subject=subject,
                center=center, # Gán center đã chọn
                room=random.choice(possible_rooms) if possible_rooms else None, # Gán phòng đã lọc
                start_date=start_date,
                end_date=end_date,
            )
            
            # Gán trợ giảng (có thể khác center với giáo viên chính)
            center_assistants = assistants_by_center.get(center.id, assistants)
            if center_assistants:
                num_assistants = random.randint(0, min(2, len(center_assistants)))
                if num_assistants > 0:
                    selected_assistants = random.sample(center_assistants, num_assistants)
                    klass.assistants.add(*selected_assistants)
            classes.append(klass)

            # Tạo lịch học hàng tuần cho lớp này
            days_of_week = random.sample(range(7), random.randint(1, 2))
            for day in days_of_week:
                start_hour = random.randint(8, 18)
                start_minute = random.choice([0, 30])
                start_time = time(start_hour, start_minute)
                end_time = (datetime.combine(date.today(), start_time) + timedelta(minutes=90)).time()
                
                schedule, _ = ClassSchedule.objects.get_or_create(
                    klass=klass, day_of_week=day, start_time=start_time, defaults={'end_time': end_time}
                )
                schedules.append(schedule)
        self.stdout.write(self.style.SUCCESS(f"Created {len(classes)} Classes and {len(schedules)} Weekly Schedules."))

        # === 7. TẠO BUỔI HỌC (Depends on Class, Lesson) ===
        sessions = []
        
        for klass in classes:
            klass_schedules = list(ClassSchedule.objects.filter(klass=klass).order_by('day_of_week', 'start_time'))
            if not klass_schedules or not klass.start_date or not klass.end_date:
                continue

            # Lấy 144 bài học (đã sắp xếp) CHO MÔN HỌC CỦA LỚP NÀY
            all_lessons_for_subject = lessons_by_subject.get(klass.subject_id, [])
            if not all_lessons_for_subject:
                continue

            sessions_to_create = []
            current_date = klass.start_date
            lesson_idx = 0 
            schedule_idx = 0
            
            while current_date <= klass.end_date and lesson_idx < len(all_lessons_for_subject):
                schedule = klass_schedules[schedule_idx % len(klass_schedules)]
                
                while current_date.weekday() != schedule.day_of_week:
                    current_date += timedelta(days=1)
                    if current_date > klass.end_date: break
                if current_date > klass.end_date: break
                
                lesson = all_lessons_for_subject[lesson_idx]
                
                # TÍNH TOÁN INDEX TUYỆT ĐỐI (1-144)
                absolute_index = ((lesson.module.order - 1) * lessons_per_module_count) + lesson.order
                
                sessions_to_create.append(
                    ClassSession(
                        klass=klass,
                        index=absolute_index, 
                        date=current_date,
                        start_time=schedule.start_time,
                        end_time=schedule.end_time,
                        lesson=lesson,
                        status="PLANNED"
                    )
                )
                
                lesson_idx += 1
                schedule_idx += 1
                current_date += timedelta(days=1) 

            # SỬA LỖI QUAN TRỌNG: KHÔNG dùng ignore_conflicts=True
            created = ClassSession.objects.bulk_create(sessions_to_create)
            sessions.extend(created) # 'created' bây giờ chứa các object CÓ PK
        
        self.stdout.write(self.style.SUCCESS(f"Generated {len(sessions)} Sessions with absolute curriculum indexing."))

        # === 8. GHI DANH (Depends on User, Class) ===
        enrollments = []
        cancelled_targets = set()
        class_session_stats = {}

        if students and classes:
            for klass in classes:
                possible_students = students_by_center.get(klass.center_id, []) or students

                upper = min(20, len(possible_students))
                lower = min(10, upper) if upper > 0 else 0
                if lower == 0:
                    continue

                num_students_to_enroll = random.randint(lower, upper)
                students_for_class = random.sample(possible_students, num_students_to_enroll)

                klass_sessions = list(
                    ClassSession.objects.filter(klass=klass).order_by("date", "index")
                )
                if not klass_sessions:
                    continue

                past_sessions = [s for s in klass_sessions if s.date and s.date < today]
                past_count = len(past_sessions)
                future_count = len(klass_sessions) - past_count

                class_session_stats[klass.id] = {
                    "total": len(klass_sessions),
                    "past": past_count,
                }

                cancelled_students = set()
                if (
                    future_count > 0
                    and past_count > 0
                    and num_students_to_enroll >= 6
                    and random.random() < 0.3
                ):
                    cancel_count = max(1, num_students_to_enroll // 8)
                    cancel_count = min(cancel_count, len(students_for_class))
                    if cancel_count > 0:
                        cancelled_students = set(random.sample(students_for_class, cancel_count))

                for student in students_for_class:
                    fee_per_session = random.choice([250000, 300000, 350000])
                    buffer_sessions = random.randint(1, max(1, future_count)) if future_count > 0 else 0
                    sessions_purchased = past_count + buffer_sessions
                    if sessions_purchased == 0:
                        sessions_purchased = max(8, len(klass_sessions))
                    else:
                        sessions_purchased = max(8, sessions_purchased)
                    amount_paid = sessions_purchased * fee_per_session
                    enrollment_status = (
                        EnrollmentStatus.ACTIVE if future_count > 0 else EnrollmentStatus.COMPLETED
                    )

                    enrollment, created = Enrollment.objects.get_or_create(
                        student=student,
                        klass=klass,
                        defaults={
                            "status": enrollment_status,
                            "fee_per_session": fee_per_session,
                            "sessions_purchased": sessions_purchased,
                            "amount_paid": amount_paid,
                            "start_date": klass.start_date,
                            "end_date": klass.end_date,
                            "active": True,
                        },
                    )
                    if not created:
                        enrollment.status = enrollment_status
                        enrollment.fee_per_session = fee_per_session
                        enrollment.sessions_purchased = sessions_purchased
                        enrollment.amount_paid = amount_paid
                        enrollment.start_date = klass.start_date
                        enrollment.end_date = klass.end_date
                        enrollment.save()

                    enrollments.append(enrollment)
                    if student in cancelled_students:
                        cancelled_targets.add((enrollment.student_id, enrollment.klass_id))

        self.stdout.write(self.style.SUCCESS(f"Created {len(enrollments)} Enrollments."))

        # === 9. TẠO ĐIỂM DANH & ĐÁNH GIÁ (Depends on Enrollment, Session) ===
        attendances = []
        assessments = []
        sessions_consumed_counter = defaultdict(int)
        attendance_history = defaultdict(list)  # student_id -> [session]
        
        for enrollment in enrollments:
            student = enrollment.student
            klass_sessions_past = ClassSession.objects.filter(
                klass=enrollment.klass, date__lt=today
            ).order_by("date", "index")
            
            for session in klass_sessions_past:
                if session.status == "PLANNED":
                    session.status = "DONE"
                    session.save(update_fields=["status"])

                status = random.choice(["P", "P", "P", "P", "L", "A"])
                attendance, _ = Attendance.objects.update_or_create(
                    session=session,
                    student=student,
                    defaults={"status": status},
                )
                attendances.append(attendance)
                if status in {"P", "L"}:
                    sessions_consumed_counter[enrollment.id] += 1
                    attendance_history[student.id].append(session)

                if status in {"P", "L"} and random.random() < 0.25:
                    assessment, _ = Assessment.objects.update_or_create(
                        session=session,
                        student=student,
                        defaults={
                            "score": round(random.uniform(5.0, 10.0), 1),
                            "remark": fake.sentence(nb_words=6),
                        },
                    )
                    assessments.append(assessment)

        # Đồng bộ số buổi đã học, học phí và trạng thái ghi danh dựa trên dữ liệu điểm danh
        for enrollment in enrollments:
            consumed = sessions_consumed_counter.get(enrollment.id, 0)
            if not enrollment.fee_per_session:
                enrollment.fee_per_session = random.choice([250000, 300000, 350000])

            enrollment.sessions_consumed = consumed
            stats = class_session_stats.get(enrollment.klass_id, {"total": 0, "past": 0})
            klass_finished = bool(enrollment.klass.end_date and enrollment.klass.end_date < today)
            future_sessions_remaining = max(stats["total"] - stats["past"], 0)
            dropout = (enrollment.student_id, enrollment.klass_id) in cancelled_targets

            if dropout:
                enrollment.sessions_purchased = consumed
                enrollment.status = EnrollmentStatus.CANCELLED
            elif klass_finished:
                if consumed == 0:
                    enrollment.sessions_purchased = 0
                    enrollment.status = EnrollmentStatus.CANCELLED
                else:
                    enrollment.sessions_purchased = consumed
                    enrollment.status = EnrollmentStatus.COMPLETED
            else:
                if enrollment.sessions_purchased <= consumed:
                    buffer = max(future_sessions_remaining, 2)
                    enrollment.sessions_purchased = consumed + buffer
                enrollment.sessions_purchased = max(enrollment.sessions_purchased, consumed + 1)
                enrollment.status = EnrollmentStatus.ACTIVE

            enrollment.amount_paid = enrollment.sessions_purchased * enrollment.fee_per_session
            enrollment.save()
        self.stdout.write(self.style.SUCCESS(f"Created {len(attendances)} Attendances and {len(assessments)} for past sessions."))

        # === 10. SẢN PHẨM HỌC SINH (Depends on Session, User) ===
        student_product_count = 0
        for session in sessions: # 'sessions' bây giờ đã CÓ PK (do sửa lỗi bulk_create)
            if not session.date or session.date > today:
                continue
            present_attendances = list(
                Attendance.objects.filter(session=session, status__in=["P", "L"])
            )
            if not present_attendances:
                continue

            if random.random() < 0.3:
                attendance = random.choice(present_attendances)
                student = attendance.student
                product, created = StudentProduct.objects.get_or_create(
                    session=session,
                    student=student,
                    title=f"Sản phẩm buổi {session.index}",
                    defaults={"description": fake.text(max_nb_chars=120)},
                )
                if created:
                    student_product_count += 1
        self.stdout.write(self.style.SUCCESS(f"Created {student_product_count} Student Products."))
        
        # === 11. ĐIỂM THƯỞNG (Depends on User) ===
        reward_items = []
        for name, cost in [("Bút chì 2B", 10), ("Vở ô ly", 20)]:
            item, _ = RewardItem.objects.get_or_create(name=name, defaults={"cost": cost})
            reward_items.append(item)

        point_accounts = []
        reward_transactions = []
        new_accounts = 0
        for student in students:
            account, created = PointAccount.objects.get_or_create(student=student, defaults={"balance": 0})
            point_accounts.append(account)
            if created:
                new_accounts += 1

            reward_events = random.randint(0, 2)
            attended_sessions = attendance_history.get(student.id, [])
            for _ in range(reward_events):
                delta = random.choice([10, 15, 20, 30])
                session_link = random.choice(attended_sessions) if attended_sessions else None
                transaction = RewardTransaction.objects.create(
                    student=student,
                    delta=delta,
                    reason="Thưởng thành tích học tập",
                    session=session_link,
                )
                reward_transactions.append(transaction)
                account.adjust_balance(delta)
        self.stdout.write(self.style.SUCCESS(f"Ensured {len(reward_items)} Reward Items, {len(point_accounts)} Point Accounts (new: {new_accounts}), {len(reward_transactions)} Reward Transactions."))

        # === 12. THÔNG BÁO (Depends on User) ===
        notifications = []
        managers_and_admins = users_by_role["ADMIN"] + users_by_role["CENTER_MANAGER"]
        for user in managers_and_admins:
            notifications.append(Notification.objects.create(
                user=user,
                title="Chào mừng bạn đến với hệ thống EDS",
                body=f"Xin chào {user.get_full_name()}, tài khoản của bạn đã sẵn sàng."
            ))
        self.stdout.write(self.style.SUCCESS(f"Created {len(notifications)} Notifications."))

        # === FINAL LOG ===
        self.stdout.write(self.style.SUCCESS(f"""
✅ SEEDING COMPLETED
-----------------------------
- Trung tâm: {len(centers)}
- Phòng học: {len(rooms)}
- Môn học: {len(subjects)}
- Học phần (Module): {len(all_modules)}
- Bài học (Lesson): {len(all_lessons)} (Lectures: {len(all_lectures)}, Exercises: {len(all_exercises)})
- Người dùng: {total_user_count} (mới tạo: {len(created_users)})
  (Admin: {len(users_by_role["ADMIN"])}, QLTT: {len(users_by_role["CENTER_MANAGER"])}, GV: {len(users_by_role["TEACHER"])}, TG: {len(users_by_role["ASSISTANT"])}, PH: {len(users_by_role["PARENT"])}, HS: {len(users_by_role["STUDENT"])})
- Quan hệ PH-HS: {len(parent_student_relations)}
- Lớp học: {len(classes)} (Yêu cầu: {options['classes']})
- Lịch học (Schedule): {len(schedules)}
- Buổi học (Session): {len(sessions)}
- Ghi danh (Enrollment): {len(enrollments)}
- Điểm danh (Attendance): {len(attendances)}
- Đánh giá (Assessment): {len(assessments)}
- Vật phẩm thưởng: {len(reward_items)}
- Tài khoản điểm: {len(point_accounts)}
- Giao dịch điểm: {len(reward_transactions)}
- Sản phẩm HS: {student_product_count}
- Thông báo: {len(notifications)}
-----------------------------
"""))
