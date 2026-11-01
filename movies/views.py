from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm

from .models import Movie, Showtime


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