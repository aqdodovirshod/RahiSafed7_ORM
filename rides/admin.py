from django.contrib import admin
from .models import (
    UserProfile, DriverProfile, City, Trip, 
    Booking, Message, Notification
)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'language', 'is_driver', 'created_at']
    list_filter = ['is_driver', 'language', 'created_at']
    search_fields = ['user__username', 'phone']
    readonly_fields = ['created_at']

@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'car_brand', 'car_model', 'car_year', 'verified', 'created_at']
    list_filter = ['verified', 'car_brand', 'created_at']
    search_fields = ['user__username', 'car_brand', 'car_model', 'license_plate']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Пользователь', {
            'fields': ('user', 'driving_experience', 'verified')
        }),
        ('Автомобиль', {
            'fields': ('car_brand', 'car_model', 'car_year', 'license_plate', 'vin_number', 'car_photo')
        }),
        ('Дополнительно', {
            'fields': ('created_at',)
        })
    )

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name_ru', 'name_en', 'name_tj', 'latitude', 'longitude']
    search_fields = ['name_ru', 'name_en', 'name_tj']

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ['id', 'driver', 'origin', 'destination', 'departure_date', 'departure_time', 'price_per_seat', 'free_seats', 'is_active']
    list_filter = ['is_active', 'departure_date', 'origin', 'destination']
    search_fields = ['driver__username', 'origin__name_ru', 'destination__name_ru']
    readonly_fields = ['created_at', 'updated_at', 'booked_seats']
    date_hierarchy = 'departure_date'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('driver', 'origin', 'destination', 'is_active')
        }),
        ('Дата и время', {
            'fields': ('departure_date', 'departure_time')
        }),
        ('Места и цены', {
            'fields': ('available_seats', 'price_per_seat', 'luggage_capacity')
        }),
        ('Статистика', {
            'fields': ('booked_seats', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def free_seats(self, obj):
        return obj.free_seats
    free_seats.short_description = 'Свободно мест'

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'passenger', 'trip', 'seats_count', 'total_price', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['passenger__username', 'trip__origin__name_ru', 'trip__destination__name_ru']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Бронирование', {
            'fields': ('trip', 'passenger', 'status')
        }),
        ('Детали', {
            'fields': ('seats_count', 'luggage_weight', 'total_price')
        }),
        ('Отмена', {
            'fields': ('cancellation_reason',),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('created_at',)
        })
    )

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'sender', 'recipient', 'trip', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['sender__username', 'recipient__username', 'text']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Уведомление', {
            'fields': ('user', 'notification_type', 'title', 'message', 'is_read')
        }),
        ('Связи', {
            'fields': ('related_trip', 'related_booking'),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('created_at',)
        })
    )

# Настройка заголовков админ-панели
admin.site.site_header = 'RideShare - Администрирование'
admin.site.site_title = 'RideShare Admin'
admin.site.index_title = 'Панель управления'