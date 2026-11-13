import logging

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext_lazy as _


# hack to fix bug in old version of django-registration
from django_registration.validators import CONFUSABLE_EMAIL
from confusable_homoglyphs import confusables
def validate_confusables_email(value):
    if '@' not in value:
        return
    parts = value.split('@')
    if len(parts) != 2:
        raise forms.ValidationError(CONFUSABLE_EMAIL, code='invalid')
    local_part, domain = value.split('@')
    if confusables.is_dangerous(local_part) or \
       confusables.is_dangerous(domain):
        raise forms.ValidationError(CONFUSABLE_EMAIL, code='invalid')

import django_registration
django_registration.validators.validate_confusables_email = validate_confusables_email
# end hack

from django_registration.forms import RegistrationFormUniqueEmail
from .emailcheck import is_disposable
from .models import Library

logger = logging.getLogger(__name__)

def encode_answer(answer):
    """ The hidden "tries" code for a not-a-robot answer.
    Derived from SECRET_KEY rather than a random table kept in the per-process cache,
    so the page can be rendered by one server process and checked by another.
    """
    return salted_hmac('regluit.libraryauth.notarobot', str(answer), algorithm='sha256').hexdigest()


class NoFourByteMixin:
    """ Refuse characters outside the Basic Multilingual Plane (emoji, decorative
    letters such as U+1D400). The auth_user columns are utf8mb3, which can't hold
    them, so a lookup like username__iexact raises MySQL error 1267 (a 500) instead
    of a form error. Checked in validate(), which runs before the field's validators,
    because django-registration's unique-email validator queries the database and
    Django runs every validator even after one fails. (Password reset needs no guard:
    Django's EmailValidator rejects these before its lookup runs.)
    """
    def validate(self, value):
        super().validate(value)
        if value and any(ord(c) > 0xFFFF for c in value):
            raise forms.ValidationError(
                _("Please remove emoji and decorative letters; they can't be stored here."),
                code='four_byte',
            )

class NoFourByteRegexField(NoFourByteMixin, forms.RegexField):
    pass

class NoFourByteEmailField(NoFourByteMixin, forms.EmailField):
    pass


class UserData(forms.Form):
    username = NoFourByteRegexField(
        label=_("New Username"),
        max_length=30,
        regex=r'^[\w.@+-]+$',
        help_text=_("30 characters or fewer."),
        error_messages={
            'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")
        }
    )
    oldusername = None
    allow_same = False


    def clean_username(self):
        username = self.data["username"]
        if username != self.oldusername:
            users = User.objects.filter(username__iexact=username)
            for user in users:
                raise forms.ValidationError(_("Another user with that username already exists."))
            return username
        if not self.allow_same:
            raise forms.ValidationError(_("Your username is already "+username))

class UserNamePass(UserData):
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    password2 = forms.CharField(
        label=_("Password confirmation"),
        widget=forms.PasswordInput,
        help_text=_("Enter the same password as above, for verification.")
    )
    allow_same = True
    notarobot = forms.IntegerField(
        label="Please show you're not a robot.",
        error_messages={
            'required': "",
        },   
        widget=forms.TextInput(attrs={'style': 'width: 2em'}),
    )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1", "")
        password2 = self.cleaned_data["password2"]
        if password1 != password2:
            raise forms.ValidationError(_("The two passwords don't match."))

        return password2

    def clean_notarobot(self):
        try:
            notarobot = int(self.data["notarobot"])
        except (ValueError, TypeError, KeyError):
            raise forms.ValidationError("(Hint: it's addition)")
        tries = self.data.get("tries", "")
        if not constant_time_compare(encode_answer(notarobot), tries):
            raise forms.ValidationError("(Hint: it's addition)")

        return notarobot

class RegistrationFormNoDisposableEmail(RegistrationFormUniqueEmail, UserNamePass):
    # Same as the model-generated field (label, max_length), plus the 4-byte check.
    email = NoFourByteEmailField(label=_("Email address"), max_length=254)

    def clean_email(self):
        """
        Check the supplied email address against a list of known disposable
        webmail domains.
        """
        # django-registration 3.x moved the unique-email check to a field validator
        # (RegistrationFormUniqueEmail.__init__), so there is no super().clean_email()
        # to call any more. By the time this per-field clean runs, the email field has
        # already been validated and stored in cleaned_data.
        cleaned_email = self.cleaned_data['email']
        logger.info('cleaning email')
        if is_disposable(cleaned_email):
            raise forms.ValidationError(_("Please supply a permanent email address."))
        return cleaned_email

class SocialAwarePasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        """
        Send the reset form even if the user password is not usable
        """
        active_users = get_user_model()._default_manager.filter(
            email__iexact=email, is_active=True)
        return active_users

    def clean_email(self):
        email = self.cleaned_data['email']
        if not get_user_model().objects.filter(email__iexact=email, is_active=True).exists():
            raise forms.ValidationError("There aren't ungluers with that email address!")
        return email


class NewLibraryForm(forms.ModelForm):
    username = NoFourByteRegexField(
        label=_("Library Username"),
        max_length=30,
        regex=r'^[\w.@+-]+$',
        help_text=_("30 characters or fewer."),
        error_messages={
            'invalid': _("This value may contain only letters, numbers and @/./+/-/_ characters.")
        },
        initial='',
    )
    email = forms.EmailField(
        label=_("notification email address for library"),
        max_length=100,
        error_messages={'required': 'Please enter an email address for the library.'},
        )

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            user = User.objects.get(username=username)
            raise forms.ValidationError(_(
                "That username is already in use, please choose another."
            ))
        except User.DoesNotExist:
            self.instance.user = User(username=username)
            return username


    class Meta:
        model = Library
        fields = 'name', 'backend', 'email', 'username'
        widgets = {'name':forms.TextInput(attrs={'size':'40'})}

class LibraryForm(forms.ModelForm):
    class Meta:
        model = Library
        fields = 'name', 'backend',
