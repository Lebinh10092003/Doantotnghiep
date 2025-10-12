# factories.py
import random
import factory
from faker import Faker
from django.contrib.auth import get_user_model
from apps.centers.models import Center, Room
from apps.curriculum.models import Subject, Module, Lesson, Lecture, Exercise
from apps.classes.models import Class, ClassAssistant, ClassSession
from apps.accounts.models import ParentStudentRelation

fake = Faker("vi_VN")
User = get_user_model()

# --- Centers ---
class CenterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Center

    name = factory.LazyAttribute(lambda _: fake.company())
    code = factory.LazyAttribute(lambda _: fake.bothify("CT-###"))
    address = factory.LazyAttribute(lambda _: fake.address())
    phone = factory.LazyAttribute(lambda _: fake.phone_number())


class RoomFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Room

    center = factory.SubFactory(CenterFactory)
    name = factory.LazyAttribute(lambda _: fake.word().capitalize())
    note = factory.LazyAttribute(lambda _: fake.sentence(nb_words=5))


# --- Curriculum ---
class SubjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subject

    name = factory.LazyAttribute(lambda _: fake.job())
    code = factory.LazyAttribute(lambda _: fake.bothify("SUB-###"))
    description = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100))


class ModuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Module

    subject = factory.SubFactory(SubjectFactory)
    order = factory.Sequence(lambda n: n + 1)
    title = factory.LazyAttribute(lambda _: fake.catch_phrase())
    description = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=80))


class LessonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Lesson

    module = factory.SubFactory(ModuleFactory)
    order = factory.Sequence(lambda n: n + 1)
    title = factory.LazyAttribute(lambda _: fake.sentence(nb_words=4))
    objectives = factory.LazyAttribute(lambda _: fake.sentence(nb_words=10))


class LectureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Lecture

    lesson = factory.SubFactory(LessonFactory)
    content = factory.LazyAttribute(lambda _: fake.text(300))
    video_url = factory.LazyAttribute(lambda _: fake.url())


class ExerciseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Exercise

    lesson = factory.SubFactory(LessonFactory)
    description = factory.LazyAttribute(lambda _: fake.text(200))
    difficulty = factory.LazyAttribute(lambda _: random.choice(["easy", "medium", "hard"]))


# --- Accounts ---
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@mail.com")
    role = factory.LazyAttribute(lambda _: random.choice([r[0] for r in User._meta.get_field('role').choices]))
    phone = factory.LazyAttribute(lambda _: fake.phone_number())
    address = factory.LazyAttribute(lambda _: fake.address())
    center = factory.SubFactory(CenterFactory)
    password = factory.PostGenerationMethodCall('set_password', '123456')


class ParentStudentRelationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ParentStudentRelation

    parent = factory.SubFactory(UserFactory, role="PARENT")
    student = factory.SubFactory(UserFactory, role="STUDENT")
    note = factory.LazyAttribute(lambda _: fake.sentence(nb_words=5))


# --- Classes ---
class ClassFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Class

    code = factory.LazyAttribute(lambda _: fake.bothify("CL-###"))
    name = factory.LazyAttribute(lambda _: fake.bs().capitalize())
    center = factory.SubFactory(CenterFactory)
    subject = factory.SubFactory(SubjectFactory)
    main_teacher = factory.SubFactory(UserFactory, role="TEACHER")
    status = factory.LazyAttribute(lambda _: random.choice(["PLANNED", "ONGOING", "COMPLETED"]))


class ClassAssistantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClassAssistant

    klass = factory.SubFactory(ClassFactory)
    assistant = factory.SubFactory(UserFactory, role="ASSISTANT")
    scope = factory.LazyAttribute(lambda _: random.choice(["COURSE", "SESSION"]))


class ClassSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClassSession

    klass = factory.SubFactory(ClassFactory)
    index = factory.Sequence(lambda n: n + 1)
    lesson = factory.SubFactory(LessonFactory)
    status = factory.LazyAttribute(lambda _: random.choice(["PLANNED", "DONE"]))
