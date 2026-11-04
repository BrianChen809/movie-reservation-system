from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
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