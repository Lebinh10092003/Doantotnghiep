from faker import Faker
from apps.centers.models import Center
fake = Faker("vi_VN")

def seed_centers(n=3, start=0):
    centers = []
    for i in range(start, start + n):
        code = f"C{100+i}"
        center, _ = Center.objects.get_or_create(
            code=code,
            defaults={
                "name": f"{fake.city()} Center {i}",
                "address": fake.address(),
            },
        )
        centers.append(center)
    print(f"Seeded {len(centers)} centers")
    return centers

centers = seed_centers()
