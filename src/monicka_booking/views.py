import uuid

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .client import MonickaAPIClient, MonickaAPIError
from .models import BookingWidgetConfig


def _client():
    config = BookingWidgetConfig.get_solo()
    return config, MonickaAPIClient(config)


def _error_response():
    return JsonResponse({"error": "سرویس رزرو موقتاً در دسترس نیست. کمی بعد دوباره تلاش کنید."}, status=503)


@require_GET
def booking_page(request):
    config, api = _client()
    try:
        catalog = api.catalog()
    except MonickaAPIError:
        catalog = {"branches": [], "therapists": []}
        unavailable = True
    else:
        unavailable = False
    return render(request, "monicka_booking/booking.html", {
        "config": config, "catalog": catalog, "unavailable": unavailable,
        "availability_url": reverse("monicka_booking:availability"),
        "slots_url": reverse("monicka_booking:slots"),
        "submit_url": reverse("monicka_booking:submit"),
        "idempotency_key": uuid.uuid4(),
    })


@require_GET
def availability(request):
    config, api = _client()
    try:
        data = api.availability(clinic=request.GET["clinic"], therapist=request.GET["therapist"],
            start=request.GET["start"], end=request.GET["end"])
    except (MonickaAPIError, KeyError, ValueError):
        return _error_response()
    return JsonResponse(data)


@require_GET
def slots(request):
    _, api = _client()
    try:
        data = api.slots(clinic=request.GET["clinic"], therapist=request.GET["therapist"], date=request.GET["date"])
    except (MonickaAPIError, KeyError, ValueError):
        return _error_response()
    return JsonResponse({"slots": data})


@require_POST
def submit_booking(request):
    _, api = _client()
    try:
        starts_at = request.POST["starts_at"]
        payload = {
            "clinic": int(request.POST["clinic"]), "therapist": int(request.POST["therapist"]),
            "patient_name": request.POST["patient_name"].strip(),
            "patient_phone": request.POST["patient_phone"].strip(),
            "duration_minutes": int(request.POST["duration_minutes"]), "starts_at": starts_at,
            "idempotency_key": request.POST.get("idempotency_key") or str(uuid.uuid4()),
            "session_type": request.POST.get("session_type", "in_person"),
            "return_url": request.build_absolute_uri(reverse("monicka_booking:complete")),
        }
        names = request.POST.getlist("participant_name")
        phones = request.POST.getlist("participant_phone")
        if len(names) != len(phones):
            return render(request, "monicka_booking/error.html", status=400)
        payload["participant_contacts"] = [{"patient_name": name.strip(), "patient_phone": phone.strip()}
            for name, phone in zip(names, phones) if name.strip() or phone.strip()]
        response = api.book(payload)
    except (MonickaAPIError, KeyError, ValueError):
        return render(request, "monicka_booking/error.html", status=503)
    gateway = response.get("gateway")
    if gateway and gateway.get("url"):
        return render(request, "monicka_booking/gateway.html", {"gateway": gateway, "confirmation_code": response.get("confirmation_code")})
    return redirect(f"{reverse('monicka_booking:complete')}?confirmation={response.get('confirmation_code', '')}")


@require_GET
def complete(request):
    code = request.GET.get("confirmation", "").strip().upper()
    if not code:
        return render(request, "monicka_booking/error.html", status=400)
    _, api = _client()
    try:
        booking = api.confirmation(code)
    except MonickaAPIError:
        return render(request, "monicka_booking/error.html", {"confirmation_code": code}, status=503)
    return render(request, "monicka_booking/complete.html", {"booking": booking})


@require_GET
def assessments_access(request):
    return render(request, "monicka_booking/assessment_access.html")


@require_POST
def assessments_list(request):
    code = request.POST.get("confirmation_code", "").strip().upper()
    phone = request.POST.get("phone", "").strip()
    if not code or not phone:
        return render(request, "monicka_booking/error.html", status=400)
    _, api = _client()
    try:
        data = api.assessment_assignments(code=code, phone=phone)
    except MonickaAPIError as exc:
        return render(request, "monicka_booking/assessment_access.html", {
            "error": "کد پیگیری یا شماره همراه درست نیست، یا آزمونی برای شما فعال نشده است."},
            status=403 if exc.status_code in (401, 403, 404) else 503)
    return render(request, "monicka_booking/assessments.html", {
        "assessments": data.get("assessments", []),
        "unavailable_assessments": data.get("unavailable_assessments", []),
        "confirmation_code": code, "phone": phone})


@require_POST
def assessment_form(request, assessment_type):
    code = request.POST.get("confirmation_code", "").strip().upper()
    phone = request.POST.get("phone", "").strip()
    if not code or not phone:
        return render(request, "monicka_booking/error.html", status=400)
    _, api = _client()
    try:
        form = api.assessment_questionnaire(code=code, phone=phone, assessment_type=assessment_type)
    except MonickaAPIError as exc:
        return render(request, "monicka_booking/error.html", status=403 if exc.status_code in (401, 403, 404) else 503)
    return render(request, "monicka_booking/assessment_form.html", {
        "form": form, "confirmation_code": code, "phone": phone})


@require_POST
def assessment_submit(request, assessment_type):
    code = request.POST.get("confirmation_code", "").strip().upper()
    phone = request.POST.get("phone", "").strip()
    try:
        count = int(request.POST.get("question_count", "0"))
        answers = [int(request.POST[f"q{number}"]) for number in range(1, count + 1)]
    except (ValueError, KeyError):
        return render(request, "monicka_booking/error.html", status=400)
    _, api = _client()
    try:
        result = api.submit_assessment(code=code, phone=phone,
            assessment_type=assessment_type, answers=answers)
    except MonickaAPIError as exc:
        return render(request, "monicka_booking/error.html", status=400 if exc.status_code == 400 else 503)
    return render(request, "monicka_booking/assessment_complete.html", {"result": result})
