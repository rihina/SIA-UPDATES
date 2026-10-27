from django.test import TestCase

from .forms import RegisterForm
from django.contrib.admin.models import LogEntry

from .models import Book, BookRequest, BorrowRecord, CustomUser, LibraryMessage


class RegisterFormTests(TestCase):
	def test_public_registration_offers_staff_role(self):
		role_choices = dict(RegisterForm().fields['role'].choices)

		self.assertEqual(set(role_choices), {
			CustomUser.ROLE_STUDENT,
			CustomUser.ROLE_TEACHER,
			CustomUser.ROLE_STAFF,
		})

	def test_public_registration_creates_staff_account(self):
		response = self.client.post('/register/', {
			'first_name': 'Jordan',
			'last_name': 'Lee',
			'username': 'newuser',
			'email': 'newuser@example.com',
			'role': CustomUser.ROLE_STAFF,
			'password1': 'ValidPass!987654',
			'password2': 'ValidPass!987654',
		})

		self.assertRedirects(response, '/dashboard/')
		user = CustomUser.objects.get(username='newuser')
		self.assertEqual(user.role, CustomUser.ROLE_STAFF)
		self.assertEqual(user.get_full_name(), 'Jordan Lee')


class PageRenderTests(TestCase):
	def test_login_page_renders(self):
		response = self.client.get('/login/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '<body class="lms-body auth-page">')
		self.assertContains(response, 'auth-wrap')
		self.assertContains(response, 'Welcome back')
		self.assertContains(response, 'name="remember_me"')
		self.assertContains(response, 'Library staff?')
		self.assertContains(response, 'href="/staff/login/"')

	def test_registration_page_renders(self):
		response = self.client.get('/register/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '<body class="lms-body auth-page">')
		self.assertContains(response, 'auth-wrap')
		self.assertContains(response, 'Create account')
		self.assertNotContains(response, 'Staff login')
		self.assertRegex(response.content.decode(), r'<input[^>]*name="password1"[^>]*class="pill-input"')
		self.assertRegex(response.content.decode(), r'<input[^>]*name="password2"[^>]*class="pill-input"')

	def test_staff_login_page_renders(self):
		response = self.client.get('/staff/login/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '<body class="lms-body auth-page">')
		self.assertContains(response, 'Staff sign in')
		self.assertContains(response, 'Create a staff account')
		self.assertContains(response, 'href="/login/"')


class StaffAuthTests(TestCase):
	def setUp(self):
		self.staff = CustomUser.objects.create_user(
			username='library_staff',
			password='ValidPass!987654',
			role=CustomUser.ROLE_STAFF,
		)
		self.teacher = CustomUser.objects.create_user(
			username='teacher_user',
			password='ValidPass!987654',
			role=CustomUser.ROLE_TEACHER,
		)

	def test_staff_can_sign_in_through_staff_page(self):
		response = self.client.post('/staff/login/', {
			'username': 'library_staff',
			'password': 'ValidPass!987654',
		})

		self.assertRedirects(response, '/dashboard/')
		self.assertEqual(str(self.client.session['_auth_user_id']), str(self.staff.pk))
		self.assertTrue(self.client.session.get_expire_at_browser_close())

	def test_remember_me_keeps_member_session_for_two_weeks(self):
		response = self.client.post('/login/', {
			'username': 'teacher_user',
			'password': 'ValidPass!987654',
			'remember_me': 'on',
		})

		self.assertRedirects(response, '/books/')
		self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 14)

	def test_remember_me_keeps_staff_session_for_two_weeks(self):
		response = self.client.post('/staff/login/', {
			'username': 'library_staff',
			'password': 'ValidPass!987654',
			'remember_me': 'on',
		})

		self.assertRedirects(response, '/dashboard/')
		self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 14)

	def test_member_cannot_sign_in_through_staff_page(self):
		response = self.client.post('/staff/login/', {
			'username': 'teacher_user',
			'password': 'ValidPass!987654',
		})

		self.assertRedirects(response, '/staff/login/')
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_staff_is_redirected_from_member_login(self):
		response = self.client.post('/login/', {
			'username': 'library_staff',
			'password': 'ValidPass!987654',
		})

		self.assertRedirects(response, '/staff/login/')
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_superuser_is_admin_in_library_app(self):
		admin = CustomUser.objects.create_superuser(
			username='library_admin',
			password='ValidPass!987654',
			email='library-admin@example.com',
		)
		self.client.force_login(admin)

		dashboard = self.client.get('/dashboard/')
		catalog = self.client.get('/books/')
		issue_page = self.client.get('/staff/issue/')

		self.assertEqual(dashboard.status_code, 200)
		self.assertEqual(catalog.status_code, 200)
		self.assertContains(catalog, 'Add book')
		self.assertNotContains(catalog, 'Borrow this book')
		self.assertEqual(dashboard.context['active_members'], 1)
		self.assertContains(issue_page, 'library_admin')
		self.assertNotIn(admin, issue_page.context['form'].fields['member'].queryset)

	def test_staff_catalog_uses_staff_logout_route(self):
		self.client.force_login(self.staff)

		response = self.client.get('/books/')

		self.assertContains(response, 'action="/staff/logout/"')

	def test_staff_dashboard_renders_database_overview(self):
		self.client.force_login(self.staff)

		response = self.client.get('/dashboard/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Staff dashboard')
		self.assertContains(response, 'Active members')
		self.assertContains(response, 'Books on loan')
		self.assertContains(response, 'Recent books')
		self.assertContains(response, 'href="/books/?add=1"')
		self.assertContains(response, 'class="nav-icon"')
		self.assertContains(response, 'href="/staff/profile/"')
		self.assertContains(response, 'All Student Information')
		self.assertContains(response, 'All Teacher Information')
		self.assertContains(response, 'Manage Book')
		self.assertContains(response, 'Manage Users')
		self.assertContains(response, 'href="/staff/requests/"')
		self.assertContains(response, 'href="/staff/messages/send/"')

	def test_staff_profile_and_filtered_member_lists_render(self):
		student = CustomUser.objects.create_user(
			username='student_member',
			password='ValidPass!987654',
			role=CustomUser.ROLE_STUDENT,
		)
		self.client.force_login(self.staff)

		profile = self.client.get('/staff/profile/')
		students = self.client.get('/staff/members/?role=student')
		teachers = self.client.get('/staff/members/?role=teacher')

		self.assertEqual(profile.status_code, 200)
		self.assertContains(profile, 'library_staff')
		self.assertContains(students, student.username)
		self.assertNotContains(students, self.teacher.username)
		self.assertContains(teachers, self.teacher.username)
		self.assertNotContains(teachers, student.username)


class AdminManagementTests(TestCase):
	def setUp(self):
		self.admin = CustomUser.objects.create_superuser(
			username='site_admin',
			password='ValidPass!987654',
			email='site-admin@example.com',
		)
		self.client.force_login(self.admin)

	def test_admin_can_add_book_and_write_admin_log(self):
		response = self.client.post('/admin/Rejean_App/book/add/', {
			'book_name': 'Admin Added Education Book',
			'author': 'Library Staff',
			'genre': 'Education',
			'availability': Book.AVAILABLE,
		})

		self.assertEqual(response.status_code, 302)
		book = Book.objects.get(book_name='Admin Added Education Book')
		self.assertTrue(LogEntry.objects.filter(
			user=self.admin,
			object_id=str(book.pk),
		).exists())

	def test_admin_can_add_staff_account_visible_in_users(self):
		response = self.client.post('/admin/Rejean_App/customuser/add/', {
			'username': 'new_staff',
			'password1': 'ValidPass!987654',
			'password2': 'ValidPass!987654',
			'role': CustomUser.ROLE_STAFF,
		})

		self.assertEqual(response.status_code, 302)
		staff = CustomUser.objects.get(username='new_staff')
		self.assertEqual(staff.role, CustomUser.ROLE_STAFF)
		self.assertFalse(staff.is_superuser)
		self.assertTrue(LogEntry.objects.filter(user=self.admin, object_id=str(staff.pk)).exists())
		users_page = self.client.get('/admin/Rejean_App/customuser/')
		self.assertContains(users_page, 'new_staff')

	def test_admin_can_add_admin_account_visible_in_users(self):
		response = self.client.post('/admin/Rejean_App/customuser/add/', {
			'username': 'new_admin',
			'password1': 'ValidPass!987654',
			'password2': 'ValidPass!987654',
			'role': CustomUser.ROLE_STUDENT,
			'is_staff': 'on',
			'is_superuser': 'on',
		})

		self.assertEqual(response.status_code, 302)
		new_admin = CustomUser.objects.get(username='new_admin')
		self.assertTrue(new_admin.is_staff)
		self.assertTrue(new_admin.is_superuser)
		self.assertTrue(LogEntry.objects.filter(user=self.admin, object_id=str(new_admin.pk)).exists())
		users_page = self.client.get('/admin/Rejean_App/customuser/')
		self.assertContains(users_page, 'new_admin')
		self.assertContains(users_page, 'Admin')

	def test_admin_user_list_shows_staff_role(self):
		CustomUser.objects.create_user(
			username='listed_staff',
			password='ValidPass!987654',
			role=CustomUser.ROLE_STAFF,
		)

		users_page = self.client.get('/admin/Rejean_App/customuser/')

		self.assertContains(users_page, 'listed_staff')
		self.assertContains(users_page, 'Staff')


class StaffOperationalTests(TestCase):
	def setUp(self):
		self.staff = CustomUser.objects.create_user(
			username='operations_staff',
			password='ValidPass!987654',
			role=CustomUser.ROLE_STAFF,
		)
		self.teacher = CustomUser.objects.create_user(
			username='operations_teacher',
			password='ValidPass!987654',
			role=CustomUser.ROLE_TEACHER,
		)

	def test_staff_uses_staff_logout(self):
		self.client.force_login(self.staff)

		response = self.client.post('/staff/logout/')

		self.assertRedirects(response, '/staff/login/')
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_staff_can_issue_available_book_to_member(self):
		book = Book.objects.create(
			book_name='Learning Design',
			author='A. Author',
			genre='Education',
		)
		self.client.force_login(self.staff)

		response = self.client.post('/staff/issue/', {
			'member': self.teacher.pk,
			'book': book.pk,
		})

		self.assertRedirects(response, '/dashboard/')
		record = BorrowRecord.objects.get(user=self.teacher, book=book)
		self.assertIsNone(record.returned_at)
		book.refresh_from_db()
		self.assertEqual(book.availability, Book.NOT_AVAILABLE)

	def test_member_cannot_open_staff_issue_page(self):
		self.client.force_login(self.teacher)

		response = self.client.get('/staff/issue/')

		self.assertEqual(response.status_code, 403)

class RequestAndMessageTests(TestCase):
	def setUp(self):
		self.staff = CustomUser.objects.create_user(
			username='request_staff',
			password='ValidPass!987654',
			role=CustomUser.ROLE_STAFF,
		)
		self.member = CustomUser.objects.create_user(
			username='request_member',
			password='ValidPass!987654',
			role=CustomUser.ROLE_STUDENT,
		)
		self.book = Book.objects.create(
			book_name='Requested Book',
			author='Library Author',
			genre='Education',
			availability=Book.NOT_AVAILABLE,
		)

	def test_member_can_request_unavailable_book_and_view_status(self):
		self.client.force_login(self.member)

		response = self.client.post('/books/request/', {'book_id': self.book.pk})

		self.assertRedirects(response, '/books/')
		request = BookRequest.objects.get(user=self.member, book=self.book)
		self.assertEqual(request.status, BookRequest.PENDING)
		requests_page = self.client.get('/my-requests/')
		self.assertContains(requests_page, 'Requested Book')
		self.assertContains(requests_page, 'Pending')

	def test_staff_can_approve_request_and_issue_book(self):
		book_request = BookRequest.objects.create(user=self.member, book=self.book)
		self.book.availability = Book.AVAILABLE
		self.book.save(update_fields=['availability'])
		self.client.force_login(self.staff)

		response = self.client.post(
			f'/staff/requests/{book_request.pk}/resolve/',
			{'decision': 'approve'},
		)

		self.assertRedirects(response, '/staff/requests/')
		book_request.refresh_from_db()
		self.book.refresh_from_db()
		self.assertEqual(book_request.status, BookRequest.APPROVED)
		self.assertEqual(BorrowRecord.objects.get(user=self.member, book=self.book).returned_at, None)
		self.assertEqual(self.book.availability, Book.NOT_AVAILABLE)

	def test_staff_can_reject_request(self):
		book_request = BookRequest.objects.create(user=self.member, book=self.book)
		self.client.force_login(self.staff)

		response = self.client.post(
			f'/staff/requests/{book_request.pk}/resolve/',
			{'decision': 'reject'},
		)

		self.assertRedirects(response, '/staff/requests/')
		book_request.refresh_from_db()
		self.assertEqual(book_request.status, BookRequest.REJECTED)

	def test_staff_message_appears_in_member_inbox_and_can_be_read(self):
		self.client.force_login(self.staff)

		response = self.client.post('/staff/messages/send/', {
			'recipient': self.member.pk,
			'subject': 'Book ready',
			'body': 'Your requested book is ready.',
		})

		self.assertRedirects(response, '/staff/messages/send/')
		message = LibraryMessage.objects.get(sender=self.staff, recipient=self.member)
		self.client.force_login(self.member)
		inbox = self.client.get('/messages/')
		self.assertContains(inbox, 'Book ready')
		self.assertContains(inbox, 'Your requested book is ready.')

		response = self.client.post(f'/messages/{message.pk}/read/')
		self.assertRedirects(response, '/messages/')
		message.refresh_from_db()
		self.assertIsNotNone(message.read_at)

	def test_member_cannot_access_staff_request_queue_or_message_form(self):
		self.client.force_login(self.member)

		self.assertEqual(self.client.get('/staff/requests/').status_code, 403)
		self.assertEqual(self.client.get('/staff/messages/send/').status_code, 403)

	def test_authenticated_catalog_renders(self):
		user = CustomUser.objects.create_user(
			username='cataloguser',
			password='ValidPass!987654',
			role=CustomUser.ROLE_STUDENT,
		)
		self.client.force_login(user)

		response = self.client.get('/books/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'href="/my-requests/"')
		self.assertContains(response, 'href="/messages/"')
