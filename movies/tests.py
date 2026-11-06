from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Auditorium, Movie, Reservation, Seat, Showtime


class BookingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.user = User.objects.create_user(username="first_user")
        cls.other_user = User.objects.create_user(username="second_user")

        cls.movie = Movie.objects.create(
            title="Test Movie",
            description="A movie used in automated tests.",
            duration_minutes=120,
        )
        cls.auditorium = Auditorium.objects.create(name="Test Screen")
        cls.seat = Seat.objects.create(
            auditorium=cls.auditorium,
            row="A",
            number=1,
        )
        cls.showtime = Showtime.objects.create(
            movie=cls.movie,
            auditorium=cls.auditorium,
            starts_at=timezone.now() + timedelta(days=7),
            ticket_price=Decimal("12.50"),
        )
        cls.booking_url = reverse(
            "movies:reserve_seat",
            args=[cls.showtime.pk, cls.seat.pk],
        )

    def test_user_can_book_seat_with_original_price(self):
        self.client.force_login(self.user)

        response = self.client.post(self.booking_url)

        self.assertRedirects(
            response,
            reverse(
                "movies:showtime_detail",
                args=[self.showtime.pk],
            ),
        )

        reservation = Reservation.objects.get()
        self.assertEqual(reservation.user_id, self.user.pk)
        self.assertEqual(reservation.showtime_id, self.showtime.pk)
        self.assertEqual(reservation.seat_id, self.seat.pk)
        self.assertEqual(reservation.price_at_booking, Decimal("12.50"))

        self.showtime.ticket_price = Decimal("15.00")
        self.showtime.save()

        reservation.refresh_from_db()
        self.assertEqual(reservation.price_at_booking, Decimal("12.50"))

    def test_another_user_cannot_book_reserved_seat(self):
        self.client.force_login(self.user)
        self.client.post(self.booking_url)

        self.client.force_login(self.other_user)
        response = self.client.post(self.booking_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Reservation.objects.filter(
                showtime=self.showtime,
                seat=self.seat,
                cancelled_at__isnull=True,
            ).count(),
            1,
        )
        self.assertEqual(Reservation.objects.get().user_id, self.user.pk)

    def test_cancellation_releases_seat_for_another_user(self):
        self.client.force_login(self.user)
        self.client.post(self.booking_url)
        reservation = Reservation.objects.get()

        response = self.client.post(
            reverse(
                "movies:cancel_reservation",
                args=[reservation.pk],
            ),
        )

        self.assertRedirects(
            response,
            reverse("movies:my_reservations"),
        )

        reservation.refresh_from_db()
        self.assertIsNotNone(reservation.cancelled_at)

        self.client.force_login(self.other_user)
        self.client.post(self.booking_url)

        active_reservation = Reservation.objects.get(
            showtime=self.showtime,
            seat=self.seat,
            cancelled_at__isnull=True,
        )
        self.assertEqual(active_reservation.user_id, self.other_user.pk)
        self.assertEqual(Reservation.objects.count(), 2)

    def test_user_cannot_cancel_someone_elses_reservation(self):
        self.client.force_login(self.user)
        self.client.post(self.booking_url)
        reservation = Reservation.objects.get()

        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse(
                "movies:cancel_reservation",
                args=[reservation.pk],
            ),
        )

        self.assertEqual(response.status_code, 404)

        reservation.refresh_from_db()
        self.assertIsNone(reservation.cancelled_at)

    def test_user_cannot_cancel_started_screening(self):
        self.client.force_login(self.user)
        self.client.post(self.booking_url)
        reservation = Reservation.objects.get()

        self.showtime.starts_at = timezone.now() - timedelta(minutes=1)
        self.showtime.save()

        response = self.client.post(
            reverse(
                "movies:cancel_reservation",
                args=[reservation.pk],
            ),
        )

        self.assertRedirects(
            response,
            reverse("movies:my_reservations"),
        )

        reservation.refresh_from_db()
        self.assertIsNone(reservation.cancelled_at)

    def test_booking_requires_login(self):
        response = self.client.post(self.booking_url)

        expected_url = (
            f"{reverse('login')}?next={self.booking_url}"
        )
        self.assertRedirects(response, expected_url)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_regular_user_cannot_access_screening_report(self):
        self.client.force_login(self.user)
        report_url = reverse("movies:screening_report")

        response = self.client.get(report_url)

        expected_url = (
            f"{reverse('admin:login')}?next={report_url}"
        )
        self.assertRedirects(response, expected_url)

    def test_staff_user_can_access_screening_report(self):
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("movies:screening_report"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "movies/screening_report.html",
        )

    def test_user_cannot_book_seat_in_another_auditorium(self):
        other_auditorium = Auditorium.objects.create(
            name="Other Screen",
        )
        other_seat = Seat.objects.create(
            auditorium=other_auditorium,
            row="A",
            number=1,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "movies:reserve_seat",
                args=[self.showtime.pk, other_seat.pk],
            ),
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_user_cannot_book_started_screening(self):
        self.showtime.starts_at = timezone.now() - timedelta(minutes=1)
        self.showtime.save()
        self.client.force_login(self.user)

        response = self.client.post(self.booking_url)

        self.assertRedirects(
            response,
            reverse(
                "movies:showtime_detail",
                args=[self.showtime.pk],
            ),
        )
        self.assertEqual(Reservation.objects.count(), 0)

    def test_overlapping_screening_in_same_room_is_rejected(self):
        overlapping = Showtime(
            movie=self.movie,
            auditorium=self.auditorium,
            starts_at=self.showtime.starts_at + timedelta(minutes=30),
            ticket_price=Decimal("12.50"),
        )

        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_screening_can_start_when_previous_one_ends(self):
        next_screening = Showtime(
            movie=self.movie,
            auditorium=self.auditorium,
            starts_at=self.showtime.starts_at + timedelta(
                minutes=self.movie.duration_minutes,
            ),
            ticket_price=Decimal("12.50"),
        )

        next_screening.full_clean()
        next_screening.save()

        self.assertTrue(
            Showtime.objects.filter(pk=next_screening.pk).exists(),
        )

    def test_different_rooms_can_screen_movies_at_same_time(self):
        other_auditorium = Auditorium.objects.create(
            name="Other Screen",
        )
        simultaneous_screening = Showtime(
            movie=self.movie,
            auditorium=other_auditorium,
            starts_at=self.showtime.starts_at,
            ticket_price=Decimal("12.50"),
        )

        simultaneous_screening.full_clean()
        simultaneous_screening.save()

        self.assertTrue(
            Showtime.objects.filter(
                pk=simultaneous_screening.pk,
            ).exists(),
        )

    def test_report_totals_exclude_cancelled_reservations(self):
        second_seat = Seat.objects.create(
            auditorium=self.auditorium,
            row="A",
            number=2,
        )
        third_seat = Seat.objects.create(
            auditorium=self.auditorium,
            row="A",
            number=3,
        )

        Reservation.objects.create(
            user=self.user,
            showtime=self.showtime,
            seat=self.seat,
            price_at_booking=Decimal("12.50"),
        )
        Reservation.objects.create(
            user=self.user,
            showtime=self.showtime,
            seat=second_seat,
            price_at_booking=Decimal("20.00"),
            cancelled_at=timezone.now(),
        )
        Reservation.objects.create(
            user=self.other_user,
            showtime=self.showtime,
            seat=third_seat,
            price_at_booking=None,
        )

        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("movies:screening_report"),
        )

        self.assertEqual(response.status_code, 200)

        rows = response.context["rows"]
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row["capacity"], 3)
        self.assertEqual(row["booked"], 2)
        self.assertEqual(row["available"], 1)
        self.assertEqual(row["booking_value"], Decimal("12.50"))
        self.assertEqual(row["missing_prices"], 1)

    def test_my_reservations_only_shows_current_users_bookings(self):
        second_seat = Seat.objects.create(
            auditorium=self.auditorium,
            row="A",
            number=2,
        )

        own_reservation = Reservation.objects.create(
            user=self.user,
            showtime=self.showtime,
            seat=self.seat,
            price_at_booking=Decimal("12.50"),
        )
        Reservation.objects.create(
            user=self.other_user,
            showtime=self.showtime,
            seat=second_seat,
            price_at_booking=Decimal("12.50"),
        )

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("movies:my_reservations"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "movies/my_reservations.html",
        )
        self.assertEqual(
            list(response.context["reservations"]),
            [own_reservation],
        )

    def test_database_rejects_duplicate_active_reservations(self):
        Reservation.objects.create(
            user=self.user,
            showtime=self.showtime,
            seat=self.seat,
            price_at_booking=Decimal("12.50"),
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Reservation.objects.create(
                user=self.other_user,
                showtime=self.showtime,
                seat=self.seat,
                price_at_booking=Decimal("12.50"),
            )

        self.assertEqual(
            Reservation.objects.filter(
                showtime=self.showtime,
                seat=self.seat,
                cancelled_at__isnull=True,
            ).count(),
            1,
        )

    def test_booked_screening_cannot_change_auditorium(self):
        Reservation.objects.create(
            user=self.user,
            showtime=self.showtime,
            seat=self.seat,
            price_at_booking=Decimal("12.50"),
        )
        other_auditorium = Auditorium.objects.create(
            name="Other Screen",
        )

        self.showtime.auditorium = other_auditorium

        with self.assertRaises(ValidationError) as error:
            self.showtime.full_clean()

        self.assertIn("auditorium", error.exception.message_dict)

        self.showtime.refresh_from_db()
        self.assertEqual(
            self.showtime.auditorium_id,
            self.auditorium.pk,
        )

    def test_unbooked_screening_can_change_auditorium(self):
        other_auditorium = Auditorium.objects.create(
            name="Other Screen",
        )

        self.showtime.auditorium = other_auditorium
        self.showtime.full_clean()
        self.showtime.save()

        self.showtime.refresh_from_db()
        self.assertEqual(
            self.showtime.auditorium_id,
            other_auditorium.pk,
        )

    def test_seat_with_reservation_history_cannot_change(self):
        Reservation.objects.create(
            user=self.user,
            showtime=self.showtime,
            seat=self.seat,
            price_at_booking=Decimal("12.50"),
            cancelled_at=timezone.now(),
        )
        other_auditorium = Auditorium.objects.create(
            name="Other Screen",
        )

        changes = {
            "auditorium": other_auditorium,
            "row": "B",
            "number": 2,
        }

        for field, value in changes.items():
            with self.subTest(field=field):
                seat = Seat.objects.get(pk=self.seat.pk)
                setattr(seat, field, value)

                with self.assertRaises(ValidationError):
                    seat.full_clean()

        self.seat.refresh_from_db()
        self.assertEqual(self.seat.auditorium_id, self.auditorium.pk)
        self.assertEqual(self.seat.row, "A")
        self.assertEqual(self.seat.number, 1)

    def test_unused_seat_can_change(self):
        other_auditorium = Auditorium.objects.create(
            name="Other Screen",
        )

        self.seat.auditorium = other_auditorium
        self.seat.row = "B"
        self.seat.number = 2
        self.seat.full_clean()
        self.seat.save()

        self.seat.refresh_from_db()
        self.assertEqual(
            self.seat.auditorium_id,
            other_auditorium.pk,
        )
        self.assertEqual(self.seat.row, "B")
        self.assertEqual(self.seat.number, 2)

    def test_movie_with_showtimes_cannot_change_duration(self):
        self.movie.duration_minutes = 150

        with self.assertRaises(ValidationError) as error:
            self.movie.full_clean()

        self.assertIn(
            "duration_minutes",
            error.exception.message_dict,
        )

        self.movie.refresh_from_db()
        self.assertEqual(self.movie.duration_minutes, 120)

    def test_movie_without_showtimes_can_change_duration(self):
        movie = Movie.objects.create(
            title="Unscheduled Movie",
            description="A movie without screenings.",
            duration_minutes=90,
        )

        movie.duration_minutes = 100
        movie.full_clean()
        movie.save()

        movie.refresh_from_db()
        self.assertEqual(movie.duration_minutes, 100)

class RoleSetupTests(TestCase):
    def test_setup_roles_assigns_expected_permissions(self):
        call_command("setup_roles", stdout=StringIO())

        group = Group.objects.get(name="Cinema admins")

        actual_permissions = set(
            group.permissions.values_list(
                "content_type__app_label",
                "codename",
            )
        )

        expected_permissions = {
            ("movies", f"{action}_{model}")
            for model in [
                "auditorium",
                "genre",
                "movie",
                "reservation",
                "seat",
                "showtime",
            ]
            for action in ["add", "change", "delete", "view"]
        }

        self.assertEqual(actual_permissions, expected_permissions)

    def test_repeated_setup_preserves_group_members(self):
        call_command("setup_roles", stdout=StringIO())

        group = Group.objects.get(name="Cinema admins")
        user = get_user_model().objects.create_user(
            username="cinema_admin",
            is_staff=True,
        )
        user.groups.add(group)

        call_command("setup_roles", stdout=StringIO())

        self.assertEqual(
            Group.objects.filter(name="Cinema admins").count(),
            1,
        )
        self.assertTrue(
            user.groups.filter(pk=group.pk).exists(),
        )
        self.assertEqual(group.permissions.count(), 24)

    def test_cinema_admin_can_manage_movies_but_not_users(self):
        call_command("setup_roles", stdout=StringIO())

        User = get_user_model()
        cinema_admin = User.objects.create_user(
            username="cinema_manager",
            is_staff=True,
        )
        cinema_admin.groups.add(
            Group.objects.get(name="Cinema admins"),
        )
        regular_user = User.objects.create_user(
            username="regular_customer",
        )

        self.client.force_login(cinema_admin)

        movie_list_response = self.client.get(
            reverse("admin:movies_movie_changelist"),
        )
        movie_add_response = self.client.get(
            reverse("admin:movies_movie_add"),
        )
        user_list_response = self.client.get(
            reverse("admin:auth_user_changelist"),
        )
        promotion_response = self.client.post(
            reverse(
                "admin:auth_user_change",
                args=[regular_user.pk],
            ),
            {
                "username": regular_user.username,
                "is_active": "on",
                "is_staff": "on",
                "is_superuser": "on",
                "_save": "Save",
            },
        )

        self.assertEqual(movie_list_response.status_code, 200)
        self.assertEqual(movie_add_response.status_code, 200)
        self.assertEqual(user_list_response.status_code, 403)
        self.assertEqual(promotion_response.status_code, 403)

        regular_user.refresh_from_db()
        self.assertFalse(regular_user.is_staff)
        self.assertFalse(regular_user.is_superuser)

class ConcurrentBookingTests(TransactionTestCase):
    def test_simultaneous_bookings_only_reserve_seat_once(self):
        User = get_user_model()
        first_user = User.objects.create_user(username="first_customer")
        second_user = User.objects.create_user(username="second_customer")

        movie = Movie.objects.create(
            title="Concurrent Booking Movie",
            description="A screening for simultaneous booking tests.",
            duration_minutes=120,
        )
        auditorium = Auditorium.objects.create(name="Concurrent Screen")
        seat = Seat.objects.create(
            auditorium=auditorium,
            row="A",
            number=1,
        )
        showtime = Showtime.objects.create(
            movie=movie,
            auditorium=auditorium,
            starts_at=timezone.now() + timedelta(days=7),
            ticket_price=Decimal("12.50"),
        )
        booking_url = reverse(
            "movies:reserve_seat",
            args=[showtime.pk, seat.pk],
        )

        first_client = Client()
        first_client.force_login(first_user)

        second_client = Client()
        second_client.force_login(second_user)

        barrier = Barrier(2)
        original_full_clean = Reservation.full_clean

        def synchronized_full_clean(reservation, *args, **kwargs):
            original_full_clean(reservation, *args, **kwargs)
            barrier.wait(timeout=30)

        def book(client):
            close_old_connections()

            try:
                return client.post(booking_url)
            finally:
                connections.close_all()

        with patch.object(
            Reservation,
            "full_clean",
            synchronized_full_clean,
        ), ThreadPoolExecutor(max_workers=2) as executor:
            first_attempt = executor.submit(book, first_client)
            second_attempt = executor.submit(book, second_client)

            first_response = first_attempt.result(timeout=30)
            second_response = second_attempt.result(timeout=30)

        expected_url = reverse(
            "movies:showtime_detail",
            args=[showtime.pk],
        )

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        self.assertEqual(first_response.url, expected_url)
        self.assertEqual(second_response.url, expected_url)

        reservations = Reservation.objects.filter(
            showtime=showtime,
            seat=seat,
            cancelled_at__isnull=True,
        )
        self.assertEqual(reservations.count(), 1)
        self.assertIn(
            reservations.get().user_id,
            [first_user.pk, second_user.pk],
        )