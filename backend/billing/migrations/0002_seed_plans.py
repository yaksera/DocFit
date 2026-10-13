from django.db import migrations

# Prices are a starting point; edit them any time in the admin (Billing > Plans).
PLANS = [
    dict(code="free", name="Free", price_npr=0, monthly_docs=25, max_upload_mb=100, max_pages=30,
         seats=1, retention_hours=1, api_access=False, is_public=True, sort=0),
    dict(code="starter", name="Starter", price_npr=999, monthly_docs=400, max_upload_mb=150,
         max_pages=150, seats=3, retention_hours=24, api_access=False, is_public=True, sort=1),
    dict(code="pro", name="Pro", price_npr=2499, monthly_docs=2000, max_upload_mb=300, max_pages=300,
         seats=10, retention_hours=72, api_access=True, is_public=True, sort=2),
    dict(code="business", name="Business", price_npr=0, monthly_docs=0, max_upload_mb=500,
         max_pages=1000, seats=50, retention_hours=168, api_access=True, is_public=False, sort=3),
]


def seed(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    for p in PLANS:
        Plan.objects.update_or_create(code=p["code"], defaults=p)


class Migration(migrations.Migration):
    dependencies = [("billing", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
