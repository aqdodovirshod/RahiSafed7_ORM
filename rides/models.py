import re

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, unique=True)
    language = models.CharField(
        max_length=2, 
        choices=[('ru', 'Русский'), ('en', 'English'), ('tj', 'Тоҷикӣ')], 
        default='ru'
    )
    is_driver = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.phone}"
    
    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'


class DriverProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    driving_experience = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(60)],
        verbose_name='Опыт вождения (лет)'
    )
    license_plate = models.CharField(max_length=20, verbose_name='Номерной знак')
    car_brand = models.CharField(max_length=50, verbose_name='Марка автомобиля')
    car_model = models.CharField(max_length=50, verbose_name='Модель автомобиля')
    car_year = models.IntegerField(
        validators=[MinValueValidator(1980), MaxValueValidator(datetime.now().year)],
        verbose_name='Год выпуска'
    )
    vin_number = models.CharField(max_length=17, verbose_name='VIN-номер')
    car_photo = models.ImageField(upload_to='cars/', blank=True, null=True, verbose_name='Фото автомобиля')
    verified = models.BooleanField(default=False, verbose_name='Проверен')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.car_brand} {self.car_model}"
    
    def clean(self):
        super().clean()
        if self.license_plate:
            # Нормализуем: убираем пробелы и дефисы, первые 6 символов в нижний регистр, последние 2 в верхний
            cleaned = re.sub(r'[\s-]', '', self.license_plate)
            if len(cleaned) == 8:
                normalized = cleaned[:6].lower() + cleaned[6:].upper()
            else:
                normalized = cleaned.lower()
            
            if not re.fullmatch(r'\d{4}[a-z]{2}[A-Z]{2}', normalized):
                raise ValidationError({
                    'license_plate': 'Номерной знак должен быть в формате 1234abAB: '
                                     '4 цифры, 2 строчные латинские буквы, 2 заглавные латинские буквы региона.'
                })
            self.license_plate = normalized
    
    class Meta:
        verbose_name = 'Профиль водителя'
        verbose_name_plural = 'Профили водителей'


class City(models.Model):
    name_ru = models.CharField(max_length=100, verbose_name='Название (рус)')
    name_en = models.CharField(max_length=100, verbose_name='Название (англ)')
    name_tj = models.CharField(max_length=100, verbose_name='Название (тадж)')
    latitude = models.FloatField(verbose_name='Широта')
    longitude = models.FloatField(verbose_name='Долгота')
    
    def __str__(self):
        return self.name_ru
    
    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'


class Trip(models.Model):
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips', verbose_name='Водитель')
    origin = models.ForeignKey(City, on_delete=models.CASCADE, related_name='trips_from', verbose_name='Откуда')
    destination = models.ForeignKey(City, on_delete=models.CASCADE, related_name='trips_to', verbose_name='Куда')
    departure_date = models.DateField(verbose_name='Дата отправления')
    departure_time = models.TimeField(verbose_name='Время отправления')
    price_per_seat = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена за место')
    available_seats = models.IntegerField(validators=[MinValueValidator(1)], verbose_name='Доступно мест')
    luggage_capacity = models.IntegerField(
        validators=[MinValueValidator(0)], 
        default=0, 
        verbose_name='Вместимость багажа'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['departure_date', 'departure_time']
        verbose_name = 'Поездка'
        verbose_name_plural = 'Поездки'
    
    def __str__(self):
        return f"{self.origin} → {self.destination} ({self.departure_date})"
    
    @property
    def booked_seats(self):
        """Количество забронированных мест"""
        total = self.bookings.filter(status='confirmed').aggregate(
            total=models.Sum('seats_count'))['total']
        return total or 0
    
    @property
    def free_seats(self):
        """Количество свободных мест"""
        return self.available_seats - self.booked_seats


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('confirmed', 'Подтверждено'),
        ('cancelled', 'Отменено'),
    ]
    
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='bookings', verbose_name='Поездка')
    passenger = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings', verbose_name='Пассажир')
    seats_count = models.IntegerField(validators=[MinValueValidator(1)], verbose_name='Количество мест')
    luggage_weight = models.IntegerField(
        validators=[MinValueValidator(0)], 
        default=0, 
        verbose_name='Вес багажа (кг)'
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость')
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='confirmed',
        verbose_name='Статус'
    )
    cancellation_reason = models.TextField(blank=True, null=True, verbose_name='Причина отмены')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.passenger.username} → {self.trip}"
    
    class Meta:
        verbose_name = 'Бронирование'
        verbose_name_plural = 'Бронирования'
        ordering = ['-created_at']


class Message(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='messages', verbose_name='Поездка')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name='Отправитель')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', verbose_name='Получатель')
    text = models.TextField(verbose_name='Текст сообщения')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
    
    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username}"


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('booking', 'Новое бронирование'),
        ('cancellation', 'Отмена брони'),
        ('trip_update', 'Изменение поездки'),
        ('message', 'Новое сообщение'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name='Пользователь')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name='Тип')
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    message = models.TextField(verbose_name='Сообщение')
    is_read = models.BooleanField(default=False, verbose_name='Прочитано')
    related_trip = models.ForeignKey(Trip, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Связанная поездка')
    related_booking = models.ForeignKey(Booking, on_delete=models.CASCADE, null=True, blank=True, verbose_name='Связанное бронирование')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"

