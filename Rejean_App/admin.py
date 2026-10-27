from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Attendance, Book, BorrowRecord, CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'account_role', 'is_staff', 'is_superuser', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Library Role', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Account Access', {'fields': ('role', 'is_staff', 'is_superuser')}),
    )

    @admin.display(description='Account role', ordering='role')
    def account_role(self, user):
        if user.is_superuser:
            return 'Admin'
        return user.get_role_display()


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['book_id', 'book_name', 'author', 'genre', 'availability']
    list_filter = ['availability', 'genre']
    search_fields = ['book_name', 'author']


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'book', 'borrowed_at', 'due_by', 'returned_at']
    list_filter = ['returned_at']
    search_fields = ['user__username', 'book__book_name']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'student_name', 'course', 'year_level', 'date', 'status']
    list_filter = ['status', 'course']
