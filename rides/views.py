from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.conf import settings
from datetime import datetime, timedelta
from django.utils.dateparse import parse_date
from django.core.exceptions import ValidationError
import requests
import json

from .models import (
    UserProfile, DriverProfile, City, Trip, 
    Booking, Message, Notification
)

# ===================================================================
# Главная страница и базовые представления
# ===================================================================

def index(request):
    """Главная страница"""
    context = {
        'recent_trips': Trip.objects.filter(
            is_active=True,
            departure_date__gte=datetime.now().date()
        )[:6],
        'cities': City.objects.all(),
        'today': datetime.now().date(),
    }
    return render(request, 'index.html', context)

def register(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        username = request.POST.get('username')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        email = request.POST.get('email', '')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return render(request, 'auth/register.html')
        
        user = User.objects.create_user(
            username=username, 
            password=password,
            email=email
        )
        
        UserProfile.objects.create(user=user, phone=phone)
        
        login(request, user)
        messages.success(request, 'Добро пожаловать в RahiSafed!')
        return redirect('dashboard')
    
    return render(request, 'auth/register.html')

@login_required
def dashboard(request):
    """Дашборд пользователя"""
    user = request.user
    is_driver = hasattr(user, 'driver_profile')
    
    context = {
        'is_driver': is_driver,
        'bookings': user.bookings.filter(status='confirmed')[:5],
        'notifications': user.notifications.filter(is_read=False)[:5],
        'today': datetime.now().date(),
        'tomorrow': datetime.now().date() + timedelta(days=1),
    }
    
    if is_driver:
        context['trips'] = user.trips.filter(is_active=True)[:5]
        context['total_trips'] = user.trips.count()
        context['total_passengers'] = Booking.objects.filter(
            trip__driver=user, 
            status='confirmed'
        ).aggregate(total=Sum('seats_count'))['total'] or 0
    
    return render(request, 'dashboard.html', context)

# ===================================================================
# Поездки - Поиск и детали
# ===================================================================

@login_required
def search_trips(request):
    """Поиск поездок"""
    trips = Trip.objects.filter(
        is_active=True, 
        departure_date__gte=datetime.now().date()
    )
    
    origin_id = request.GET.get('origin')
    destination_id = request.GET.get('destination')
    date = request.GET.get('date')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort', 'date')
    
    if origin_id:
        trips = trips.filter(origin_id=origin_id)
    if destination_id:
        trips = trips.filter(destination_id=destination_id)
    if date:
        try:
            parsed_date = parse_date(date)
            if parsed_date:
                trips = trips.filter(departure_date=parsed_date)
        except (ValueError, TypeError):
            pass
    if min_price:
        trips = trips.filter(price_per_seat__gte=min_price)
    if max_price:
        trips = trips.filter(price_per_seat__lte=max_price)
    
    if sort_by == 'price_asc':
        trips = trips.order_by('price_per_seat')
    elif sort_by == 'price_desc':
        trips = trips.order_by('-price_per_seat')
    else:
        trips = trips.order_by('departure_date', 'departure_time')
    
    context = {
        'trips': trips,
        'cities': City.objects.all(),
        'filters': request.GET,
        'today': datetime.now().date().isoformat(),
        'tomorrow': (datetime.now().date() + timedelta(days=1)).isoformat(),
        'next_week': (datetime.now().date() + timedelta(days=7)).isoformat(),
    }
    return render(request, 'trips/search.html', context)

@login_required
def trip_detail(request, trip_id):
    """Детали поездки"""
    trip = get_object_or_404(Trip, id=trip_id)
    
    weather_data = None
    try:
        weather_data = get_weather(trip.origin.latitude, trip.origin.longitude)
    except:
        pass
    
    route_info = calculate_distance(
        trip.origin.latitude, trip.origin.longitude,
        trip.destination.latitude, trip.destination.longitude
    )
    distance = route_info['distance']
    duration = route_info['duration']
    
    context = {
        'trip': trip,
        'weather': weather_data,
        'can_book': trip.free_seats > 0 and request.user != trip.driver,
        'distance': distance,
        'duration': duration,
    }
    return render(request, 'trips/detail.html', context)

# ===================================================================
# Бронирования
# ===================================================================

@login_required
def book_trip(request, trip_id):
    """Бронирование поездки"""
    trip = get_object_or_404(Trip, id=trip_id)
    
    if request.method == 'POST':
        seats_count = int(request.POST.get('seats_count', 1))
        luggage_weight = int(request.POST.get('luggage_weight', 0))
        
        if seats_count > trip.free_seats:
            messages.error(request, 'Недостаточно свободных мест')
            return redirect('trip_detail', trip_id=trip_id)
        
        if request.user == trip.driver:
            messages.error(request, 'Вы не можете забронировать свою поездку')
            return redirect('trip_detail', trip_id=trip_id)
        
        total_price = trip.price_per_seat * seats_count
        
        booking = Booking.objects.create(
            trip=trip,
            passenger=request.user,
            seats_count=seats_count,
            luggage_weight=luggage_weight,
            total_price=total_price,
            status='confirmed'
        )
        
        Notification.objects.create(
            user=trip.driver,
            notification_type='booking',
            title='Новое бронирование',
            message=f'{request.user.username} забронировал {seats_count} мест в вашей поездке',
            related_trip=trip,
            related_booking=booking,
        )
        
        messages.success(request, 'Поездка успешно забронирована!')
        return redirect('my_bookings')
    
    context = {'trip': trip}
    return render(request, 'bookings/book.html', context)

@login_required
def my_bookings(request):
    """Мои бронирования"""
    bookings = request.user.bookings.filter(status='confirmed').order_by('-created_at')
    context = {
        'bookings': bookings,
        'today': datetime.now().date(),
        'tomorrow': datetime.now().date() + timedelta(days=1),
    }
    return render(request, 'bookings/list.html', context)

@login_required
def cancel_booking(request, booking_id):
    """Отмена брони"""
    booking = get_object_or_404(Booking, id=booking_id, passenger=request.user)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Не указана')
        booking.status = 'cancelled'
        booking.cancellation_reason = reason
        booking.save()
        
        comments = request.POST.get('comments', '')
        message = f'{request.user.username} отменил бронирование {booking.seats_count} мест(а). Причина: {reason}'
        if comments:
            message += f'\nКомментарий: {comments}'
        
        Notification.objects.create(
            user=booking.trip.driver,
            notification_type='cancellation',
            title='Отмена бронирования',
            message=message,
            related_trip=booking.trip,
            related_booking=booking,
        )
        
        messages.success(request, 'Бронирование отменено')
        return redirect('my_bookings')
    
    context = {
        'booking': booking,
        'cancellation_reasons': [
            'Планы изменились',
            'Нашел другой вариант',
            'Поеду другим транспортом',
            'Личные обстоятельства',
            'Другое',
        ]
    }
    return render(request, 'bookings/cancel.html', context)

# ===================================================================
# Водитель - Регистрация и управление
# ===================================================================

@login_required
def become_driver(request):
    """Регистрация водителя"""
    if hasattr(request.user, 'driver_profile'):
        messages.info(request, 'Вы уже зарегистрированы как водитель')
        return redirect('dashboard')
    
    form_data = request.POST.dict() if request.method == 'POST' else {}
    
    if request.method == 'POST':
        try:
            driver_profile = DriverProfile(
                user=request.user,
                driving_experience=form_data.get('experience'),
                license_plate=form_data.get('license_plate', ''),
                car_brand=form_data.get('car_brand'),
                car_model=form_data.get('car_model'),
                car_year=form_data.get('car_year'),
                vin_number=form_data.get('vin_number'),
                car_photo=request.FILES.get('car_photo'),
            )
            driver_profile.full_clean()
            driver_profile.save()
            
            user_profile = request.user.profile
            user_profile.is_driver = True
            user_profile.save()
            
            messages.success(request, 'Поздравляем! Вы теперь водитель')
            return redirect('dashboard')
        except ValidationError as e:
            for field, errors in e.message_dict.items():
                for error in errors:
                    messages.error(request, error)
        except Exception as e:
            messages.error(request, f'Ошибка регистрации: {str(e)}')
    
    return render(request, 'drivers/register.html', {'form_data': form_data})

@login_required
def my_trips(request):
    """Поездки водителя"""
    if not hasattr(request.user, 'driver_profile'):
        messages.warning(request, 'Сначала зарегистрируйтесь как водитель')
        return redirect('become_driver')
    
    trips = request.user.trips.all().order_by('-departure_date', '-departure_time')

    total_passengers = Booking.objects.filter(
        trip__driver=request.user,
        status='confirmed'
    ).aggregate(total=Sum('seats_count'))['total'] or 0

    total_earnings = sum(
        booking.total_price for booking in Booking.objects.filter(
            trip__driver=request.user,
            status='confirmed'
        )
    )

    active_trips_count = trips.filter(is_active=True).count()
    # Предстоящие - только активные поездки с датой >= сегодня
    upcoming_trips_count = trips.filter(
        is_active=True,
        departure_date__gte=datetime.now().date()
    ).count()

    trips_list = []
    for trip in trips:
        confirmed_count = trip.bookings.filter(status='confirmed').count()
        booked_seats = trip.bookings.filter(status='confirmed').aggregate(total=Sum('seats_count'))['total'] or 0
        setattr(trip, 'computed_confirmed_count', confirmed_count)
        setattr(trip, 'computed_booked_seats', booked_seats)
        trips_list.append(trip)

    context = {
        'trips': trips_list,
        'today': datetime.now().date(),
        'total_passengers': total_passengers,
        'total_earnings': total_earnings,
        'active_trips_count': active_trips_count,
        'upcoming_trips_count': upcoming_trips_count,
    }
    return render(request, 'drivers/trips.html', context)

@login_required
def create_trip(request):
    """Создание поездки"""
    if not hasattr(request.user, 'driver_profile'):
        messages.warning(request, 'Сначала зарегистрируйтесь как водитель')
        return redirect('become_driver')
    
    if request.method == 'POST':
        try:
            trip = Trip.objects.create(
                driver=request.user,
                origin_id=request.POST.get('origin'),
                destination_id=request.POST.get('destination'),
                departure_date=request.POST.get('departure_date'),
                departure_time=request.POST.get('departure_time'),
                price_per_seat=request.POST.get('price'),
                available_seats=request.POST.get('seats'),
                luggage_capacity=request.POST.get('luggage_capacity', 0),
            )
            
            messages.success(request, 'Поездка успешно опубликована!')
            return redirect('trip_detail', trip_id=trip.id)
        except Exception as e:
            messages.error(request, f'Ошибка создания поездки: {str(e)}')
    
    context = {
        'cities': City.objects.all(),
        'today': datetime.now().date().isoformat(),
    }
    return render(request, 'drivers/create_trip.html', context)

@login_required
def edit_trip(request, trip_id):
    """Редактирование поездки"""
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
    
    if request.method == 'POST':
        try:
            trip.departure_time = request.POST.get('departure_time')
            trip.price_per_seat = request.POST.get('price')
            
            new_seats = int(request.POST.get('seats'))
            booked_seats = trip.bookings.filter(status='confirmed').aggregate(
                total=Sum('seats_count')
            )['total'] or 0
            if new_seats >= booked_seats:
                trip.available_seats = new_seats
            else:
                messages.error(request, f'Нельзя установить меньше {booked_seats} мест (уже забронировано)')
                return redirect('edit_trip', trip_id=trip_id)
            
            trip.luggage_capacity = request.POST.get('luggage_capacity', 0)
            trip.save()
            
            for booking in trip.bookings.filter(status='confirmed'):
                Notification.objects.create(
                    user=booking.passenger,
                    notification_type='trip_update',
                    title='Изменение в поездке',
                    message=f'Поездка {trip.origin.name_ru} - {trip.destination.name_ru} была обновлена',
                    related_trip=trip,
                )
            
            messages.success(request, 'Поездка обновлена')
            return redirect('trip_detail', trip_id=trip.id)
        except Exception as e:
            messages.error(request, f'Ошибка обновления: {str(e)}')
    
    booked_seats = trip.bookings.filter(status='confirmed').aggregate(
        total=Sum('seats_count')
    )['total'] or 0
    
    context = {
        'trip': trip,
        'booked_seats_count': booked_seats,
    }
    return render(request, 'drivers/edit_trip.html', context)

@login_required
def cancel_trip(request, trip_id):
    """Отмена поездки водителем"""
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
    
    if request.method == 'POST':
        try:
            # Отменяем все бронирования
            bookings = trip.bookings.filter(status='confirmed')
            for booking in bookings:
                booking.status = 'cancelled'
                booking.cancellation_reason = 'Поездка отменена водителем'
                booking.save()
                
                # Создаем уведомление для пассажира
                Notification.objects.create(
                    user=booking.passenger,
                    notification_type='cancellation',
                    title='Поездка отменена',
                    message=f'Поездка {trip.origin.name_ru} - {trip.destination.name_ru} от {trip.departure_date.strftime("%d.%m.%Y")} была отменена водителем',
                    related_trip=trip,
                    related_booking=booking,
                )
            
            # Деактивируем поездку
            trip.is_active = False
            trip.save()
            
            messages.success(request, 'Поездка отменена. Все пассажиры получили уведомления.')
            return redirect('my_trips')
        except Exception as e:
            messages.error(request, f'Ошибка отмены поездки: {str(e)}')
            return redirect('trip_detail', trip_id=trip_id)
    
    # GET запрос - показываем страницу подтверждения
    bookings_count = trip.bookings.filter(status='confirmed').count()
    context = {
        'trip': trip,
        'bookings_count': bookings_count,
    }
    return render(request, 'drivers/cancel_trip.html', context)

@login_required
def trip_passengers(request, trip_id):
    """Список пассажиров поездки"""
    trip = get_object_or_404(Trip, id=trip_id, driver=request.user)
    bookings = trip.bookings.filter(status='confirmed')
    
    total_luggage = bookings.aggregate(total=Sum('luggage_weight'))['total'] or 0
    total_revenue = bookings.aggregate(total=Sum('total_price'))['total'] or 0
    
    context = {
        'trip': trip,
        'bookings': bookings,
        'total_luggage': total_luggage,
        'total_revenue': total_revenue,
    }
    return render(request, 'drivers/passengers.html', context)

def calculate_route(request):
    """API endpoint для расчета расстояния и времени между двумя точками"""
    if request.method == 'GET':
        lat1 = request.GET.get('lat1')
        lon1 = request.GET.get('lon1')
        lat2 = request.GET.get('lat2')
        lon2 = request.GET.get('lon2')
        
        if not all([lat1, lon1, lat2, lon2]):
            return JsonResponse({'error': 'Необходимы все параметры: lat1, lon1, lat2, lon2'}, status=400)
        
        try:
            lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
            route_info = calculate_distance(lat1, lon1, lat2, lon2)
            return JsonResponse({
                'distance': round(route_info['distance'], 2),
                'duration': route_info['duration']
            })
        except ValueError:
            return JsonResponse({'error': 'Некорректные координаты'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Метод не разрешен'}, status=405)

# ===================================================================
# Вспомогательные функции
# ===================================================================

def get_weather(lat, lon):
    """Получение погоды через OpenWeatherMap API"""
    api_key = '22b275b87d04d66375784ecb4d5a3568'  
    url = f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric&lang=ru'
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Расчет расстояния и времени в пути через OpenRouteService API"""
    api_key = getattr(settings, 'ROUTING_API_KEY', None)
    
    if not api_key or api_key == "YOUR_OPENROUTE_API_KEY":
        return {'distance': 0, 'duration': 0}
    
    try:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        
        body = {
            "coordinates": [
                [lon1, lat1],  
                [lon2, lat2]
            ],
            "instructions": False,
            "geometry": False,
            "units": "km"
        }
        
        response = requests.post(url, json=body, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("routes") and len(data["routes"]) > 0:
                route = data["routes"][0]
                summary = route.get("summary", {})
                
                distance_km = summary.get("distance", 0) 
                duration_s = summary.get("duration", 0) 
                
                if distance_km > 0 and duration_s > 0:
                    duration_hours = duration_s / 3600.0  
                    return {'distance': round(distance_km, 2), 'duration': max(1, int(round(duration_hours)))}
    
    except Exception as e:
        import logging
        logging.error(f"OpenRouteService API Error: {str(e)}")
    
    return {'distance': 0, 'duration': 0}

@login_required
def mark_notification_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Уведомление не найдено'}, status=404)

@login_required
def mark_all_notifications_read(request):
    """Отметить все уведомления как прочитанные"""
    try:
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)