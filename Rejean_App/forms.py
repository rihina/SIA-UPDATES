from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Attendance, Book, CustomUser


class RegisterForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        widget=forms.Select(attrs={'class': 'pill-input'}),
    )

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'username', 'email', 'role', 'password1', 'password2']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'pill-input', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'pill-input', 'placeholder': 'Last name'}),
            'username': forms.TextInput(attrs={'class': 'pill-input', 'placeholder': 'Choose a username'}),
            'email': forms.EmailInput(attrs={'class': 'pill-input', 'placeholder': 'you@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'pill-input',
            'placeholder': 'Create a password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'pill-input',
            'placeholder': 'Confirm your password',
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['book_name', 'author', 'genre', 'availability']
        widgets = {
            'book_name': forms.TextInput(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter Book Name',
            }),
            'author': forms.TextInput(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter Author',
            }),
            'genre': forms.TextInput(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter Genre',
            }),
            'availability': forms.Select(
                choices=Book.AVAILABILITY_CHOICES,
                attrs={'class': 'pill-input'},
            ),
        }


class BorrowForm(forms.Form):
    book_id = forms.IntegerField(widget=forms.HiddenInput)


class StaffIssueForm(forms.Form):
    member = forms.ModelChoiceField(
        label='Student or Teacher',
        queryset=CustomUser.objects.none(),
        widget=forms.Select(attrs={'class': 'pill-input'}),
    )
    book = forms.ModelChoiceField(
        label='Available book',
        queryset=Book.objects.none(),
        widget=forms.Select(attrs={'class': 'pill-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = CustomUser.objects.filter(
            role__in=[CustomUser.ROLE_STUDENT, CustomUser.ROLE_TEACHER],
            is_active=True,
            is_superuser=False,
        ).order_by('username')
        self.fields['book'].queryset = Book.objects.filter(
            availability=Book.AVAILABLE,
        ).order_by('book_name')


class BookRequestForm(forms.Form):
    book_id = forms.ModelChoiceField(
        queryset=Book.objects.none(),
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['book_id'].queryset = Book.objects.filter(
            availability=Book.NOT_AVAILABLE,
        )


class StaffMessageForm(forms.Form):
    recipient = forms.ModelChoiceField(
        label='Member',
        queryset=CustomUser.objects.none(),
        widget=forms.Select(attrs={'class': 'pill-input'}),
    )
    subject = forms.CharField(
        max_length=140,
        widget=forms.TextInput(attrs={'class': 'pill-input', 'placeholder': 'Message subject'}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'pill-input', 'placeholder': 'Write your message', 'rows': 5}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recipient'].queryset = CustomUser.objects.filter(
            role__in=[CustomUser.ROLE_STUDENT, CustomUser.ROLE_TEACHER],
            is_active=True,
            is_superuser=False,
        ).order_by('username')


class ReturnForm(forms.Form):
    record_id = forms.IntegerField(widget=forms.HiddenInput)


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = [
            'student_id',
            'student_name',
            'course',
            'year_level',
            'date',
            'status',
            'remarks',
        ]
        widgets = {
            'student_id': forms.TextInput(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter Student ID',
            }),
            'student_name': forms.TextInput(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter Student Name',
            }),
            'course': forms.TextInput(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter Course',
            }),
            'year_level': forms.TextInput(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter Year Level',
            }),
            'date': forms.DateInput(attrs={
                'class': 'pill-input',
                'type': 'date',
            }),
            'status': forms.Select(
                choices=[
                    ('Present', 'Present'),
                    ('Absent', 'Absent'),
                    ('Late', 'Late'),
                ],
                attrs={'class': 'pill-input'},
            ),
            'remarks': forms.Textarea(attrs={
                'class': 'pill-input',
                'placeholder': 'Enter remarks',
                'rows': 3,
            }),
        }
