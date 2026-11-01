from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_POST

from .models import Movie, Reservation, Seat, Showtime


def movie_list(request):
    movies = Movie.objects.order_by("title")

    return render(
        request,
        "movies/movie_list.html",
        {"movies": movies},
    )

def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    showtimes = movie.showtimes.filter(
        starts_at__gt=timezone.now(),
    ).order_by("starts_at")

    return render(
        request,
        "movies/movie_detail.html",
        {"movie": movie, "showtimes": showtimes},
    )

def showtime_detail(request, showtime_id):
    showtime = get_object_or_404(Showtime, pk=showtime_id)
    seats = showtime.auditorium.seats.all()

    reserved_seat_ids = set(
        showtime.reservations.filter(
            cancelled_at__isnull=True,
        ).values_list("seat_id", flat=True)
    )

    return render(
        request,
        "movies/showtime_detail.html",
        {
            "showtime": showtime,
            "seats": seats,
            "reserved_seat_ids": reserved_seat_ids,
        },
    )

def signup(request):
    if request.user.is_authenticated:
        return redirect("movies:movie_list")

    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserCreationForm()

    return render(request, "registration/signup.html", {"form": form})

@login_required
@require_POST
def reserve_seat(request, showtime_id, seat_id):
    showtime = get_object_or_404(Showtime, pk=showtime_id)
    seat = get_object_or_404(
        Seat,
        pk=seat_id,
        auditorium_id=showtime.auditorium_id,
    )

    reservation = Reservation(
        user=request.user,
        showtime=showtime,
        seat=seat,
    )

    try:
        reservation.full_clean()

        with transaction.atomic():
            reservation.save()

    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)

    except IntegrityError as error:
        constraint_name = getattr(
            getattr(error.__cause__, "diag", None),
            "constraint_name",
            None,
        )

        if constraint_name != "unique_active_reservation_per_showtime_seat":
            raise

        messages.error(
            request,
            "Someone just booked that seat. Please choose another.",
        )

    else:
        messages.success(request, "Your seat is booked!")

    return redirect("movies:showtime_detail", showtime_id=showtime.id)