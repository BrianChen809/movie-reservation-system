from django.urls import path

from . import views

app_name = "movies"

urlpatterns = [
    path("", views.movie_list, name="movie_list"),
    path("<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path(
        "showtimes/<int:showtime_id>/",
        views.showtime_detail,
        name="showtime_detail",
    ),
    path("signup/", views.signup, name="signup"),
    path(
        "showtimes/<int:showtime_id>/seats/<int:seat_id>/reserve/",
        views.reserve_seat,
        name="reserve_seat",
    ),
    path(
        "my-reservations/",
        views.my_reservations,
        name="my_reservations",
    ),
    path(
        "reservations/<int:reservation_id>/cancel/",
        views.cancel_reservation,
        name="cancel_reservation",
    ),
    path(
        "reports/screenings/",
        views.screening_report,
        name="screening_report",
    ),
]