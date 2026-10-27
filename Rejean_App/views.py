from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .decorators import member_required, staff_required
from .forms import BookForm, BookRequestForm, RegisterForm, ReturnForm, StaffIssueForm, StaffMessageForm
from .models import Book, BookRequest, BorrowRecord, CustomUser, LibraryMessage


def _set_login_session_expiry(request):
    if request.POST.get('remember_me') == 'on':
        request.session.set_expiry(60 * 60 * 24 * 14)
    else:
        request.session.set_expiry(0)


def home(request):
    if request.user.is_authenticated:
        return redirect('staff_dashboard' if request.user.is_staff_role else 'book_list')
    return redirect('login')


def register(request):
    if request.user.is_authenticated:
        return redirect('book_list')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Account created. Welcome, {user.get_full_name() or user.username}!')
            return redirect('staff_dashboard' if user.is_staff_role else 'book_list')
    else:
        form = RegisterForm()

    return render(request, 'InvApp/register.html', {'form': form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect('book_list')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_staff_role:
                messages.error(request, 'Staff accounts must use the staff sign-in page.')
                return redirect('staff_login')
            login(request, user)
            _set_login_session_expiry(request)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('book_list')
        messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()

    for field in form.fields.values():
        field.widget.attrs.update({'class': 'pill-input'})

    return render(request, 'InvApp/login.html', {
        'form': form,
        'remember_me': request.POST.get('remember_me') == 'on',
    })


def staff_login(request):
    if request.user.is_authenticated:
        return redirect('staff_dashboard' if request.user.is_staff_role else 'book_list')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_staff_role:
                messages.error(request, 'This sign-in is for staff accounts only.')
                return redirect('staff_login')
            login(request, user)
            _set_login_session_expiry(request)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('staff_dashboard')
    else:
        form = AuthenticationForm()

    for field in form.fields.values():
        field.widget.attrs.update({'class': 'pill-input'})

    return render(request, 'InvApp/login.html', {
        'form': form,
        'remember_me': request.POST.get('remember_me') == 'on',
        'staff_login': True,
    })


def user_logout(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'You have been logged out.')
    return redirect('login')


@staff_required
def staff_logout(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, 'Staff account logged out.')
    return redirect('staff_login')


@login_required
def book_list(request):
    books = Book.objects.all()
    edit_book = None

    if request.user.is_staff_role:
        if request.GET.get('edit'):
            edit_book = get_object_or_404(Book, pk=request.GET['edit'])

        form = BookForm(instance=edit_book) if edit_book else BookForm()
    else:
        form = None

    context = {
        'books': books,
        'genres': books.order_by().values_list('genre', flat=True).distinct(),
        'selected_book': books.first(),
        'available_count': books.filter(availability=Book.AVAILABLE).count(),
        'form': form,
        'edit_book': edit_book,
        'show_add_book': request.user.is_staff_role and request.GET.get('add') == '1',
        'pending_request_book_ids': set(
            BookRequest.objects.filter(user=request.user, status=BookRequest.PENDING)
            .values_list('book_id', flat=True)
        ) if not request.user.is_staff_role else set(),
        'is_staff': request.user.is_staff_role,
    }
    return render(request, 'InvApp/book_list.html', context)


@member_required
def book_request(request):
    if request.method != 'POST':
        return redirect('book_list')

    form = BookRequestForm(request.POST)
    if form.is_valid():
        book = form.cleaned_data['book_id']
        if BorrowRecord.objects.filter(
            user=request.user,
            book=book,
            returned_at__isnull=True,
        ).exists():
            messages.error(request, 'You already have this book on loan.')
        elif BookRequest.objects.filter(
            user=request.user,
            book=book,
            status=BookRequest.PENDING,
        ).exists():
            messages.info(request, 'Your request for this book is already pending.')
        else:
            BookRequest.objects.create(user=request.user, book=book)
            messages.success(request, f'Your request for "{book.book_name}" was sent to the library.')
    else:
        messages.error(request, 'This book can no longer be requested.')
    return redirect('book_list')


@login_required
def borrow_book(request):
    if request.method != 'POST':
        return redirect('book_list')

    if request.user.is_staff_role:
        messages.error(request, 'Staff accounts do not borrow books.')
        return redirect('book_list')

    form = BorrowForm(request.POST)
    if form.is_valid():
        book = get_object_or_404(Book, pk=form.cleaned_data['book_id'])

        active = BorrowRecord.objects.filter(
            user=request.user, book=book, returned_at__isnull=True
        ).exists()
        if active:
            messages.error(request, f'You already have "{book.book_name}" checked out.')
            return redirect('book_list')

        with transaction.atomic():
            book = Book.objects.select_for_update().get(pk=book.pk)
            if not book.is_available:
                messages.error(request, f'"{book.book_name}" is no longer available.')
            else:
                record = BorrowRecord(user=request.user, book=book)
                record.save()
                book.availability = Book.NOT_AVAILABLE
                book.save(update_fields=['availability'])
                messages.success(
                    request,
                    f'"{book.book_name}" borrowed. Due by {record.due_by:%b %d, %Y %I:%M %p}.',
                )
    else:
        messages.error(request, 'Invalid borrow request.')

    return redirect('book_list')


@login_required
def my_books(request):
    records = BorrowRecord.objects.filter(user=request.user)
    active = [r for r in records if not r.is_returned]
    history = [r for r in records if r.is_returned]

    context = {
        'active': active,
        'history': history,
        'return_form': ReturnForm(),
        'now': timezone.now(),
    }
    return render(request, 'InvApp/my_books.html', context)


@member_required
def my_requests(request):
    requests = BookRequest.objects.filter(user=request.user).select_related('book')
    return render(request, 'InvApp/my_requests.html', {'requests': requests})


@login_required
def user_messages(request):
    inbox = LibraryMessage.objects.filter(recipient=request.user).select_related('sender')
    return render(request, 'InvApp/messages.html', {'inbox': inbox})


@login_required
def mark_message_read(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(LibraryMessage, pk=message_id, recipient=request.user)
        if message.read_at is None:
            message.read_at = timezone.now()
            message.save(update_fields=['read_at'])
    return redirect('user_messages')


@login_required
def return_book(request):
    if request.method != 'POST':
        return redirect('my_books')

    form = ReturnForm(request.POST)
    if form.is_valid():
        record = get_object_or_404(
            BorrowRecord,
            pk=form.cleaned_data['record_id'],
            returned_at__isnull=True,
        )

        if record.user_id != request.user.id and not request.user.is_staff_role:
            messages.error(request, 'You can only return your own books.')
            return redirect('my_books')

        with transaction.atomic():
            record.returned_at = timezone.now()
            record.save(update_fields=['returned_at'])
            book = record.book
            book.availability = Book.AVAILABLE
            book.save(update_fields=['availability'])

        messages.success(request, f'"{record.book.book_name}" returned. Thank you!')
    else:
        messages.error(request, 'Invalid return request.')

    return redirect('staff_dashboard' if request.user.is_staff_role else 'my_books')


@staff_required
def staff_dashboard(request):
    now = timezone.now()
    records = BorrowRecord.objects.select_related('user', 'book')
    active = records.filter(returned_at__isnull=True)
    returned = records.filter(returned_at__isnull=False)
    members = CustomUser.objects.filter(
        role__in=[CustomUser.ROLE_STUDENT, CustomUser.ROLE_TEACHER],
        is_active=True,
        is_superuser=False,
    )

    context = {
        'active': active,
        'returned': returned,
        'total_books': Book.objects.count(),
        'available_books': Book.objects.filter(availability=Book.AVAILABLE).count(),
        'active_members': members.count(),
        'loan_count': active.count(),
        'overdue_count': active.filter(due_by__lt=now).count(),
        'members': members.order_by('-date_joined')[:6],
        'recent_books': Book.objects.order_by('-book_id')[:6],
    }
    return render(request, 'InvApp/staff_dashboard.html', context)


@staff_required
def staff_profile(request):
    return render(request, 'InvApp/staff_profile.html')


@staff_required
def staff_members(request):
    role = request.GET.get('role', CustomUser.ROLE_STUDENT)
    role_labels = {
        CustomUser.ROLE_STUDENT: 'Students',
        CustomUser.ROLE_TEACHER: 'Teachers',
        CustomUser.ROLE_STAFF: 'Staff accounts',
    }
    if role not in role_labels:
        role = CustomUser.ROLE_STUDENT

    members = CustomUser.objects.filter(role=role, is_superuser=False).annotate(
        active_loans=Count(
            'borrow_records',
            filter=Q(borrow_records__returned_at__isnull=True),
        ),
    ).order_by('username')
    return render(request, 'InvApp/staff_members.html', {
        'members': members,
        'selected_role': role,
        'page_title': role_labels[role],
    })


@staff_required
def staff_requests(request):
    selected_status = request.GET.get('status', BookRequest.PENDING)
    if selected_status not in dict(BookRequest.STATUS_CHOICES):
        selected_status = BookRequest.PENDING
    requests = BookRequest.objects.filter(status=selected_status).select_related('user', 'book')
    return render(request, 'InvApp/staff_requests.html', {
        'requests': requests,
        'selected_status': selected_status,
        'status_choices': BookRequest.STATUS_CHOICES,
    })


@staff_required
def resolve_book_request(request, request_id):
    if request.method != 'POST':
        return redirect('staff_requests')

    with transaction.atomic():
        book_request = get_object_or_404(
            BookRequest.objects.select_for_update().select_related('user', 'book'),
            pk=request_id,
            status=BookRequest.PENDING,
        )
        decision = request.POST.get('decision')
        if decision == 'approve':
            book = Book.objects.select_for_update().get(pk=book_request.book_id)
            if not book.is_available:
                messages.error(request, f'"{book.book_name}" must be available before this request can be approved.')
                return redirect('staff_requests')
            if BorrowRecord.objects.filter(
                user=book_request.user,
                book=book,
                returned_at__isnull=True,
            ).exists():
                messages.error(request, 'This member already has the book on loan.')
                return redirect('staff_requests')
            BorrowRecord.objects.create(user=book_request.user, book=book)
            book.availability = Book.NOT_AVAILABLE
            book.save(update_fields=['availability'])
            book_request.status = BookRequest.APPROVED
            messages.success(request, f'Approved request and issued "{book.book_name}" to {book_request.user.get_full_name() or book_request.user.username}.')
        elif decision == 'reject':
            book_request.status = BookRequest.REJECTED
            messages.info(request, f'Rejected the request for "{book_request.book.book_name}".')
        else:
            messages.error(request, 'Choose approve or reject for this request.')
            return redirect('staff_requests')

        book_request.resolved_at = timezone.now()
        book_request.save(update_fields=['status', 'resolved_at'])
    return redirect('staff_requests')


@staff_required
def staff_send_message(request):
    if request.method == 'POST':
        form = StaffMessageForm(request.POST)
        if form.is_valid():
            message = LibraryMessage.objects.create(
                sender=request.user,
                recipient=form.cleaned_data['recipient'],
                subject=form.cleaned_data['subject'],
                body=form.cleaned_data['body'],
            )
            messages.success(request, f'Message sent to {message.recipient.get_full_name() or message.recipient.username}.')
            return redirect('staff_send_message')
    else:
        form = StaffMessageForm()
    return render(request, 'InvApp/staff_message_form.html', {'form': form})


@staff_required
def staff_issue(request):
    if request.method == 'POST':
        form = StaffIssueForm(request.POST)
        if form.is_valid():
            member = form.cleaned_data['member']
            selected_book = form.cleaned_data['book']
            if BorrowRecord.objects.filter(
                user=member,
                book=selected_book,
                returned_at__isnull=True,
            ).exists():
                form.add_error('member', 'This member already has this book on loan.')
            else:
                with transaction.atomic():
                    book = Book.objects.select_for_update().get(pk=selected_book.pk)
                    if not book.is_available:
                        form.add_error('book', 'This book is no longer available.')
                    else:
                        BorrowRecord.objects.create(user=member, book=book)
                        book.availability = Book.NOT_AVAILABLE
                        book.save(update_fields=['availability'])
                        messages.success(request, f'"{book.book_name}" issued to {member.get_full_name() or member.username}.')
                        return redirect('staff_dashboard')
    else:
        form = StaffIssueForm()

    return render(request, 'InvApp/issue_book.html', {'form': form})


@staff_required
def book_add(request):
    if request.method != 'POST':
        return redirect('book_list')

    form = BookForm(request.POST)
    if form.is_valid():
        book = form.save()
        messages.success(request, f'"{book.book_name}" added to the catalog.')
    else:
        messages.error(request, 'Could not add the book. Please check the form.')

    return redirect('book_list')


@staff_required
def book_edit(request, book_id):
    book = get_object_or_404(Book, pk=book_id)

    if request.method != 'POST':
        return redirect(f"{reverse('book_list')}?edit={book_id}")

    form = BookForm(request.POST, instance=book)
    if form.is_valid():
        form.save()
        messages.success(request, f'"{book.book_name}" updated.')
    else:
        messages.error(request, 'Could not update the book. Please check the form.')

    return redirect('book_list')


@staff_required
def book_delete(request, book_id):
    if request.method != 'POST':
        return redirect('book_list')

    book = get_object_or_404(Book, pk=book_id)
    name = book.book_name

    active_loan = book.borrow_records.filter(returned_at__isnull=True).exists()
    if active_loan:
        messages.error(request, f'Cannot delete "{name}" while it is borrowed.')
        return redirect('book_list')

    book.delete()
    messages.success(request, f'"{name}" deleted from the catalog.')
    return redirect('book_list')
