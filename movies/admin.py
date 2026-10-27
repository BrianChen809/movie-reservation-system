from django.contrib import admin

from .models import Auditorium, Genre, Movie, Showtime

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