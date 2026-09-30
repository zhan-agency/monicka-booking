from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlsplit


class BookingWidgetConfig(models.Model):
    class Theme(models.TextChoices):
        IVORY = "ivory", _("Ivory")
        SAGE = "sage", _("Sage")
        BLUE = "blue", _("Blue")

    class FontScale(models.IntegerChoices):
        NORMAL = 100, _("Normal")
        LARGE = 112, _("Large")
        EXTRA_LARGE = 125, _("Extra large")

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    api_base_url = models.URLField(default="https://api.monicka.ir")
    primary_clinic_id = models.PositiveIntegerField(null=True, blank=True,
        help_text=_("The clinic ID for the API key installed on this website."))
    title = models.CharField(max_length=120, default=_("رزرو نوبت"))
    introduction = models.CharField(max_length=240, blank=True,
        default=_("درمانگر را انتخاب کنید و زمان مناسب را پیدا کنید."))
    theme = models.CharField(max_length=12, choices=Theme.choices, default=Theme.IVORY)
    font_scale = models.PositiveSmallIntegerField(choices=FontScale.choices, default=FontScale.NORMAL)
    currency_label = models.CharField(max_length=16, default=_("ریال"),
        help_text=_("Label only. Keep this consistent with the API and gateway currency."))
    show_phone_support = models.BooleanField(default=False)
    support_phone = models.CharField(max_length=32, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("booking page settings")
        verbose_name_plural = _("booking page settings")

    def clean(self):
        parts = urlsplit(self.api_base_url)
        if parts.scheme != "https" and parts.hostname not in {"localhost", "127.0.0.1"}:
            raise ValidationError({"api_base_url": _("Use HTTPS for the Monicka API outside local development.")})
        if parts.query or parts.fragment or parts.path not in ("", "/"):
            raise ValidationError({"api_base_url": _("Enter the API origin, without a path, query, or fragment.")})

    def save(self, *args, **kwargs):
        self.pk = 1
        self.full_clean()
        return super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    def __str__(self):
        return str(_("Monicka booking page"))
