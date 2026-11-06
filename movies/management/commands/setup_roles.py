from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create or update the Cinema admins group permissions."

    @transaction.atomic
    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(
            name="Cinema admins",
        )

        permissions = Permission.objects.filter(
            content_type__app_label="movies",
            content_type__model__in=[
                "auditorium",
                "genre",
                "movie",
                "reservation",
                "seat",
                "showtime",
            ],
            codename__in=[
                f"{action}_{model}"
                for model in [
                    "auditorium",
                    "genre",
                    "movie",
                    "reservation",
                    "seat",
                    "showtime",
                ]
                for action in ["add", "change", "delete", "view"]
            ],
        )

        if permissions.count() != 24:
            raise RuntimeError(
                "Expected 24 movie permissions. "
                "Run manage.py migrate before setup_roles."
            )

        group.permissions.set(permissions)

        result = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{result} Cinema admins with 24 permissions."
            )
        )