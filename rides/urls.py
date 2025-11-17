from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    path('register/', views.register, name='register'),
    
    path('trips/', views.search_trips, name='search_trips'),
    path('trips/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('trips/<int:trip_id>/book/', views.book_trip, name='book_trip'),
    
    path('bookings/', views.my_bookings, name='my_bookings'),
    path('bookings/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    
    path('become-driver/', views.become_driver, name='become_driver'),
    path('my-trips/', views.my_trips, name='my_trips'),
    path('trips/create/', views.create_trip, name='create_trip'),
    path('trips/<int:trip_id>/edit/', views.edit_trip, name='edit_trip'),
    path('trips/<int:trip_id>/cancel/', views.cancel_trip, name='cancel_trip'),
    path('trips/<int:trip_id>/passengers/', views.trip_passengers, name='trip_passengers'),
    
    path('api/calculate-route/', views.calculate_route, name='calculate_route'),
    path('api/notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]