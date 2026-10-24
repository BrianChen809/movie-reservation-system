from django.db import models

class Movie(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    poster_url = models.URLField(blank=True)
    duration_minutes = models.PositiveIntegerField()

    def __str__(self):
        return self.title