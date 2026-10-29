from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Movie


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