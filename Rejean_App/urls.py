from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('staff/login/', views.staff_login, name='staff_login'),
    path('logout/', views.user_logout, name='logout'),
    path('staff/logout/', views.staff_logout, name='staff_logout'),

    path('books/', views.book_list, name='book_list'),
    path('books/borrow/', views.borrow_book, name='borrow_book'),
    path('books/request/', views.book_request, name='book_request'),
    path('books/add/', views.book_add, name='book_add'),
    path('books/<int:book_id>/edit/', views.book_edit, name='book_edit'),
    path('books/<int:book_id>/delete/', views.book_delete, name='book_delete'),

    path('my-books/', views.my_books, name='my_books'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('my-books/return/', views.return_book, name='return_book'),
    path('messages/', views.user_messages, name='user_messages'),
    path('messages/<int:message_id>/read/', views.mark_message_read, name='mark_message_read'),

    path('dashboard/', views.staff_dashboard, name='staff_dashboard'),
    path('staff/profile/', views.staff_profile, name='staff_profile'),
    path('staff/members/', views.staff_members, name='staff_members'),
    path('staff/requests/', views.staff_requests, name='staff_requests'),
    path('staff/requests/<int:request_id>/resolve/', views.resolve_book_request, name='resolve_book_request'),
    path('staff/messages/send/', views.staff_send_message, name='staff_send_message'),
    path('staff/issue/', views.staff_issue, name='staff_issue'),
]
