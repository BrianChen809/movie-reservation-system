from django.contrib import admin
from django.utils import timezone

from .models import Auditorium, Genre, Movie, Reservation, Seat, Showtime

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("auditorium", "row", "number")
    list_filter = ("auditorium",)
    ordering = ("auditorium", "row", "number")

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ("name",)

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "duration_minutes")
    search_fields = ("title",)
    list_filter = ("genres",)
    filter_horizontal = ("genres",)

@admin.register(Showtime)
class ShowtimeAdmin(admin.ModelAdmin):
    list_display = ("movie", "starts_at")
    list_filter = ("movie", "starts_at")
    ordering = ("starts_at",)

@admin.register(Auditorium)
class AuditoriumAdmin(admin.ModelAdmin):
    search_fields = ("name",)

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "user", "showtime", "seat", "created_at", "cancelled_at",
    )
    list_filter = ("showtime",)
    readonly_fields = ("created_at", "cancelled_at")
    actions = ("cancel_reservations",)

    @admin.action(description="Cancel selected upcoming reservations")
    def cancel_reservations(self, request, queryset):
        now = timezone.now()

        count = queryset.filter(
            cancelled_at__isnull=True,
            showtime__starts_at__gt=now,
        ).update(cancelled_at=now)

        self.message_user(
            request,
            f"Cancelled {count} reservation(s). "
            "Already cancelled or started screenings were skipped.",
        )