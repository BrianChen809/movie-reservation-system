from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

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

class Auditorium(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Seat(models.Model):
    auditorium = models.ForeignKey(
        Auditorium,
        on_delete=models.PROTECT,
        related_name="seats",
    )
    row = models.CharField(max_length=5)
    number = models.PositiveIntegerField()

    class Meta:
        ordering = ("row", "number")
        constraints = [
            models.UniqueConstraint(
                fields=["auditorium", "row", "number"],
                name="unique_seat_per_auditorium",
            ),
            models.CheckConstraint(
                condition=models.Q(number__gte=1),
                name="seat_number_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.auditorium.name} — {self.row}{self.number}"

class Showtime(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.PROTECT,
        related_name="showtimes",
    )
    starts_at = models.DateTimeField()
    auditorium = models.ForeignKey(
        Auditorium,
        on_delete=models.PROTECT,
        related_name="showtimes",
    )

    def __str__(self):
        return f"{self.movie.title} — {self.starts_at}"

class Reservation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    showtime = models.ForeignKey(
        Showtime,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    seat = models.ForeignKey(
        Seat,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["showtime", "seat"],
                condition=models.Q(cancelled_at__isnull=True),
                name="unique_active_reservation_per_showtime_seat",
            ),
        ]

    def clean(self):
        super().clean()

        if self.showtime_id and self.seat_id:
            if self.seat.auditorium_id != self.showtime.auditorium_id:
                raise ValidationError({
                    "seat": "Choose a seat in the showtime's auditorium."
                })
        if self.showtime_id and self._state.adding:
            if self.showtime.starts_at <= timezone.now():
                raise ValidationError({
                    "showtime": "You cannot reserve a screening that has started."
                })
            
    def __str__(self):
        return f"{self.user} — {self.showtime} — {self.seat}"