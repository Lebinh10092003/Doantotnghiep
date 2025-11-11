import factory
from factory import SubFactory, Sequence, post_generation
from faker import Faker
from django.contrib.auth import get_user_model
from apps.centers.models import Center, Room
from apps.curriculum.models import Subject, Module, Lesson # Keep Module and Lesson if they are used elsewhere in factories.py
from apps.classes.models import Class as Klass
from apps.class_sessions.models import ClassSession
from apps.students.models import StudentProduct
from django.utils import timezone

User = get_user_model()
fake = Faker()


def _safe_digits(s, max_len=20):
    digits = ''.join(ch for ch in str(s) if ch.isdigit())
    return digits[:max_len]


def _safe_text(s, max_len):
    return str(s)[:max_len]


class CenterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Center
        django_get_or_create = ("code",)

    name = factory.LazyAttribute(lambda o: _safe_text(fake.company(), 255))
    code = factory.Sequence(lambda n: f"CENTER{n:03d}")
    address = factory.LazyAttribute(lambda o: _safe_text(fake.address(), 255))
    phone = factory.LazyAttribute(lambda o: _safe_digits(fake.phone_number(), 20))
    avatar = ""
    description = factory.LazyAttribute(lambda o: _safe_text(fake.text(max_nb_chars=100), 100))
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class SubjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subject
        django_get_or_create = ("code",)

    name = factory.LazyAttribute(lambda o: _safe_text(fake.bs().title(), 255))
    code = factory.Sequence(lambda n: f"SUBJ{n:03d}")
    description = factory.LazyAttribute(lambda o: _safe_text(fake.text(max_nb_chars=100), 255))
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n:05d}")
    password = factory.PostGenerationMethodCall('set_password', 'password123')
    first_name = factory.LazyAttribute(lambda o: _safe_text(fake.first_name(), 150))
    last_name = factory.LazyAttribute(lambda o: _safe_text(fake.last_name(), 150))
    email = factory.LazyAttribute(lambda o: _safe_text(fake.unique.email(), 254))
    is_superuser = False
    is_staff = False
    is_active = True
    date_joined = factory.LazyFunction(timezone.now)
    role = factory.LazyAttribute(lambda o: _safe_text("STUDENT", 20))
    phone = factory.LazyAttribute(lambda o: _safe_digits(fake.phone_number(), 20))
    avatar = ""
    dob = factory.LazyAttribute(lambda o: fake.date_of_birth(minimum_age=7, maximum_age=60))
    gender = factory.LazyAttribute(lambda o: fake.random_element(elements=("M", "F")))
    national_id = factory.Sequence(lambda n: f"ID{n:08d}")
    address = factory.LazyAttribute(lambda o: _safe_text(fake.address(), 255))
    center = SubFactory(CenterFactory)

    @post_generation
    def groups(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for g in extracted:
                self.groups.add(g)


class KlassFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Klass

    code = factory.Sequence(lambda n: f"CLASS{n:04d}")
    name = factory.LazyAttribute(lambda o: _safe_text(f"{fake.word().title()} Class", 255))
    status = _safe_text("ACTIVE", 20)
    start_date = factory.LazyAttribute(lambda o: fake.date())
    end_date = factory.LazyAttribute(lambda o: fake.date())
    note = factory.LazyAttribute(lambda o: _safe_text(fake.sentence(), 255))
    center = SubFactory(CenterFactory)
    main_teacher = SubFactory(UserFactory, role="TEACHER")
    subject = SubFactory(SubjectFactory)
    room = None


class ClassSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClassSession

    index = Sequence(lambda n: n + 1)
    date = factory.LazyAttribute(lambda o: fake.date_between(start_date='-30d', end_date='+30d'))
    status = _safe_text("SCHEDULED", 20)
    klass = SubFactory(KlassFactory)
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    teacher_override = None
    room_override = None


class StudentProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = StudentProduct

    title = factory.LazyAttribute(lambda o: _safe_text(fake.sentence(nb_words=4), 255))
    description = factory.LazyAttribute(lambda o: _safe_text(fake.text(max_nb_chars=200), 200))
    image = ""
    video = ""
    embed_code = "<iframe></iframe>"
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    session = SubFactory(ClassSessionFactory)
    student = SubFactory(UserFactory, role="STUDENT")
