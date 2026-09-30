from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name="BookingWidgetConfig", fields=[
        ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
        ("api_base_url", models.URLField(default="https://api.monicka.ir")),
        ("primary_clinic_id", models.PositiveIntegerField(blank=True, help_text="The clinic ID for the API key installed on this website.", null=True)),
        ("title", models.CharField(default="رزرو نوبت", max_length=120)),
        ("introduction", models.CharField(blank=True, default="درمانگر را انتخاب کنید و زمان مناسب را پیدا کنید.", max_length=240)),
        ("theme", models.CharField(choices=[("ivory", "Ivory"), ("sage", "Sage"), ("blue", "Blue")], default="ivory", max_length=12)),
        ("font_scale", models.PositiveSmallIntegerField(choices=[(100, "Normal"), (112, "Large"), (125, "Extra large")], default=100)),
        ("currency_label", models.CharField(default="ریال", max_length=16)),
        ("show_phone_support", models.BooleanField(default=False)),
        ("support_phone", models.CharField(blank=True, max_length=32)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ], options={"verbose_name": "booking page settings", "verbose_name_plural": "booking page settings"})]
