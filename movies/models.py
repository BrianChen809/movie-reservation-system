from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
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

    def clean(self):
        super().clean()

        if not self.pk:
            return

        original = Movie.objects.get(pk=self.pk)

        if (
            self.duration_minutes != original.duration_minutes
            and self.showtimes.exists()
        ):
            raise ValidationError({
                "duration_minutes": (
                    "You cannot change the duration of a movie "
                    "that has scheduled screenings."
                ),
            })

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
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["auditorium", "row", "number"],
                name="unique_seat_per_auditorium",
            ),
            models.CheckConstraint(
                condition=models.Q(number__gte=1),
                name="seat_number_at_least_one",
            ),
        ]

    def clean(self):
        super().clean()

        if not self.pk:
            return

        original = Seat.objects.get(pk=self.pk)

        seat_changed = (
            self.auditorium_id != original.auditorium_id
            or self.row != original.row
            or self.number != original.number
        )

        if seat_changed and self.reservations.exists():
            raise ValidationError(
                "You cannot move or rename a seat "
                "that has reservation history."
            )

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
    ticket_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    def clean(self):
        super().clean()

        if self.pk:
            original = Showtime.objects.get(pk=self.pk)

            if self.reservations.exists():
                errors = {}
                for field in ("movie", "auditorium", "starts_at"):
                    attribute = f"{field}_id" if field != "starts_at" else field
                    if getattr(self, attribute) != getattr(original, attribute):
                        errors[field] = (
                            "You cannot change this field for a screening "
                            "that has reservation history."
                        )

                if errors:
                    raise ValidationError(errors)

        if not (self.movie_id and self.auditorium_id and self.starts_at):
            return

        ends_at = self.starts_at + timedelta(
            minutes=self.movie.duration_minutes,
        )

        other_showtimes = (
            Showtime.objects
            .filter(
                auditorium_id=self.auditorium_id,
                starts_at__lt=ends_at,
            )
            .exclude(pk=self.pk)
            .select_related("movie")
        )

        for other in other_showtimes:
            other_ends_at = other.starts_at + timedelta(
                minutes=other.movie.duration_minutes,
            )

            if self.starts_at < other_ends_at:
                raise ValidationError(
                    "This screening overlaps another screening "
                    "in the same auditorium."
                )

    def __str__(self):
        starts_at = timezone.localtime(self.starts_at)
        return (
            f"{self.movie.title} — {self.auditorium.name} — "
            f"{starts_at:%Y-%m-%d %H:%M %Z}"
        )


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
    price_at_booking = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["showtime", "seat"],
                condition=models.Q(cancelled_at__isnull=True),
                name="unique_active_reservation_per_showtime_seat",
            ),
        ]

    def clean(self):
        super().clean()
        
        if self.showtime_id and self.seat_id:  # noqa: SIM102
            if self.seat.auditorium_id != self.showtime.auditorium_id:
                raise ValidationError({
                    "seat": "Choose a seat in the showtime's auditorium."
                })
        if self.showtime_id and self._state.adding:  # noqa: SIM102
            if self.showtime.starts_at <= timezone.now():
                raise ValidationError({
                    "showtime": "You cannot reserve a screening that has started."
                })
            
    def __str__(self):
        return f"{self.user} — {self.showtime} — {self.seat}"
