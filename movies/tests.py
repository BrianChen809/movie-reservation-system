from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
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