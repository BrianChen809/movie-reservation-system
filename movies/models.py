from django.db import models

class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Movie(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    poster_url = models.URLField(blank=True)
    duration_minutes = models.PositiveIntegerField()
    genres = models.ManyToManyField(Genre, blank=True)

    def __str__(self):
        return self.title

class Showtime(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.PROTECT,
        related_name="showtimes",
    )
    starts_at = models.DateTimeField()

    def __str__(self):
        return f"{self.movie.title} — {self.starts_at}"