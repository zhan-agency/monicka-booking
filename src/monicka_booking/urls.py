from django.urls import path

from . import views

app_name = "monicka_booking"

urlpatterns = [
    path("", views.booking_page, name="booking"),
    path("availability/", views.availability, name="availability"),
    path("slots/", views.slots, name="slots"),
    path("submit/", views.submit_booking, name="submit"),
    path("complete/", views.complete, name="complete"),
    path("assessments/", views.assessments_access, name="assessments-access"),
    path("assessments/list/", views.assessments_list, name="assessments-list"),
    path("assessments/<slug:assessment_type>/", views.assessment_form, name="assessment-form"),
    path("assessments/<slug:assessment_type>/submit/", views.assessment_submit, name="assessment-submit"),
]
