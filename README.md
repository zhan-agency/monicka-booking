# Monicka Booking

An accessible, Persian right-to-left booking app for Django clinic websites. It is a server-rendered Django app distributed as a pip package; it does not expose clinic API keys to the visitor's browser and uses no JavaScript framework or external font service.

## Install

```sh
pip install monicka-booking
```

Add the app, set its API key in the website process environment, and mount its URLs:

```python
# settings.py
INSTALLED_APPS += ["monicka_booking"]
MONICKA_API_KEY = "<the clinic API key>"  # Prefer an environment variable/secret manager.
```

```python
# urls.py
from django.urls import include, path

urlpatterns += [path("booking/", include("monicka_booking.urls"))]
```

Then run `python manage.py migrate`. A staff user can configure title, colors, text size, displayed currency label, and optional support phone in Django admin under **Booking page settings**. Set the API origin and home clinic ID there. The API key is intentionally configured outside admin and is never sent to the browser.

## API setup

Issue a clinic API key in Monicka and set the key's home clinic `website_url` to this site's HTTPS origin (including the same origin used by the plugin payment return URL). Set each clinic's `plugin_booking_days` in API admin. The default booking window is 20 future days. All clinics with the same owner are offered as branches in one catalog. Therapist profile fields (short bio and specialties) are maintained in API admin.

The package talks to the API over HTTPS using `X-Clinic-API-Key`. Website hosting must allow outbound HTTPS requests to the configured API. The payment callback returns to the plugin completion page, where the package verifies the confirmation code server-to-server before showing appointment status.

## Booking flow and accessibility

The initial therapist catalog is server-rendered. JavaScript progressively loads the Jalali calendar's available days and slots from same-origin Django views; dates and slots are always validated again by the API at booking time. The responsive UI uses semantic form labels, keyboard-operable buttons, visible focus rings, large controls, live status announcements, high-contrast light themes, adjustable type size, and reduced-motion support.

Theme choices are intentionally CSS-variable based so future themes can be added without introducing a UI framework. The calendar uses the browser's built-in Persian calendar formatter.

## Development

```sh
pip install -e '.[test]'
python -m django test --settings tests.settings
```

You can also run the source checkout as a standalone local Django site without installing `monicka-booking`. Use an existing Python environment with Django and Requests available:

```sh
export PYTHONPATH="$PWD/src"
DJANGO_PYTHON="/path/to/python-with-django"
"$DJANGO_PYTHON" -m django migrate --settings tests.dev_settings
"$DJANGO_PYTHON" -m django createsuperuser --settings tests.dev_settings
"$DJANGO_PYTHON" -m django runserver 127.0.0.1:8000 --settings tests.dev_settings
```

Open `http://localhost:8000/booking/` for the booking page or `/admin/` to configure its title and theme. This local setup uses a persistent SQLite database at `dev.sqlite3`; the test settings continue to use an in-memory database. Without `MONICKA_API_KEY` and a reachable API the page shows its friendly unavailable state. To try real slots and payment handoff, point it at a staging API and test gateway. A production project supplies its own Django settings, database, and admin configuration.
