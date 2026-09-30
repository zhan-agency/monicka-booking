from django.urls import path

from . import views

app_name = "monicka_booking"

urlpatterns = [
    path("", views.booking_page, name="booking"),
    path("availability/", views.availability, name="availability"),
    path("slots/", views.slots, name="slots"),
    path("submit/", views.submit_booking, name="submit"),
    path("complete/", views.complete, name="complete"),
]
