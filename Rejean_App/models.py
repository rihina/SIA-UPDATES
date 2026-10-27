from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    ROLE_STUDENT = 'student'
    ROLE_TEACHER = 'teacher'
    ROLE_STAFF = 'staff'

    ROLE_CHOICES = [
        (ROLE_STUDENT, 'Student'),
        (ROLE_TEACHER, 'Teacher'),
        (ROLE_STAFF, 'Staff'),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_STUDENT)

    @property
    def is_staff_role(self):
        return self.is_superuser or self.role == self.ROLE_STAFF

    @property
    def account_role_display(self):
        return 'Admin' if self.is_superuser else self.get_role_display()

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.account_role_display})"


class Book(models.Model):
    AVAILABLE = 'Available'
    NOT_AVAILABLE = 'Not Available'

    AVAILABILITY_CHOICES = [
        (AVAILABLE, 'Available'),
        (NOT_AVAILABLE, 'Not Available'),
    ]

    book_id = models.AutoField(primary_key=True)
    book_name = models.CharField(max_length=100)
    author = models.CharField(max_length=100)
    genre = models.CharField(max_length=50)
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default=AVAILABLE)

    def __str__(self):
        return self.book_name

    @property
    def is_available(self):
        return self.availability == self.AVAILABLE


LOAN_PERIOD_DAYS = 7


class BorrowRecord(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='borrow_records')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='borrow_records')
    borrowed_at = models.DateTimeField(auto_now_add=True)
    due_by = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-borrowed_at']

    def save(self, *args, **kwargs):
        if not self.due_by:
            base = self.borrowed_at or timezone.now()
            self.due_by = base + timedelta(days=LOAN_PERIOD_DAYS)
        super().save(*args, **kwargs)

    @property
    def is_returned(self):
        return self.returned_at is not None

    @property
    def is_overdue(self):
        return not self.is_returned and timezone.now() > self.due_by

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} borrowed {self.book.book_name}"


class BookRequest(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='book_requests')
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} requested {self.book.book_name} ({self.get_status_display()})"


class LibraryMessage(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_library_messages')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_library_messages')
    subject = models.CharField(max_length=140)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.subject} to {self.recipient.get_full_name() or self.recipient.username}"


# Added for compatibility if other parts expect Attendance
class Attendance(models.Model):
    student_id = models.CharField(max_length=50)
    student_name = models.CharField(max_length=100)
    course = models.CharField(max_length=100)
    year_level = models.CharField(max_length=50)
    date = models.DateField()
    status = models.CharField(max_length=20)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.student_name} - {self.date}"
