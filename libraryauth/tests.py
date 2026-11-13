from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.urls import reverse
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User, AnonymousUser
from django.template.loader import render_to_string

from .forms import UserNamePass, encode_answer
from .templatetags import puzzle


class TestLibraryAuth(TestCase):
    fixtures = ['initial_data.json']
    def setUp(self):
        pass

    def test_login(self):
        resp = self.client.get(reverse('superlogin'), data={'next': '/'})
        self.assertEqual(200, resp.status_code)
        self.client.cookies['un'] = 'bob'
        resp = self.client.get(reverse('superlogin'), data={'next': '/'})
        self.assertEqual(200, resp.status_code)
        resp = self.client.post(reverse('superlogin'), data={'username': 'bob'})
        self.assertEqual(200, resp.status_code)

    def test_pages(self):
        resp = self.client.get(reverse('registration_register'))
        self.assertEqual(200, resp.status_code)

    def test_registration(self):
        """
        LibraryAuth Registration creates a new inactive account and a new profile
        with activation key, populates the correct account data and
        sends an activation email.

        """
        resp = self.client.post(reverse('registration_register'),
                                data={'username': 'bob',
                                      'email': 'bob@example.com',
                                      'password1': 'secret',
                                      'password2': 'secret',
                                      'notarobot': '11',
                                      'tries': encode_answer(11),
                                      })
        self.assertRedirects(resp, reverse('django_registration_complete'))

        new_user = User.objects.get(username='bob')

        self.assertTrue(new_user.check_password('secret'))
        self.assertEqual(new_user.email, 'bob@example.com')

        # New user must not be active.
        self.assertFalse(new_user.is_active)

    def test_bad_registration(self):
        """
        LibraryAuth Registration rejects.

        """
        resp = self.client.post(reverse('registration_register'),
                                data={'username': 'badbob',
                                      'email': 'bob@mailnesia.com',
                                      'password1': 'secret',
                                      'password2': 'secret'})
        self.assertTrue('Please supply a permanent email address' in str(resp.content, 'utf-8'))

        with self.assertRaises(User.DoesNotExist):
            User.objects.get(username='badbob')

    def _register(self, username, email):
        return self.client.post(reverse('registration_register'),
                                data={'username': username,
                                      'email': email,
                                      'password1': 'secret',
                                      'password2': 'secret',
                                      'notarobot': '11',
                                      'tries': encode_answer(11),
                                      })

    def test_four_byte_characters_get_a_form_error_not_a_500(self):
        # auth_user is utf8mb3 on MySQL, so these used to raise error 1267 in the
        # uniqueness lookups. U+1D400 is a decorative letter that \w accepts.
        for username, email in [('\U0001D400lice', 'alice@example.com'),
                                ('alice4', 'a\U0001F600@example.com'),
                                ('alice5', 'alice@\U0001D400example.com')]:
            resp = self._register(username, email)
            self.assertEqual(200, resp.status_code, (username, email))
            self.assertIn("decorative letters", str(resp.content, 'utf-8'))
            self.assertFalse(User.objects.filter(email__startswith='alice').exists())

    def test_change_username_form_with_four_byte_name_is_a_form_error(self):
        # /accounts/edit/ uses the same username field.
        form = UserNamePass(data={'username': '\U0001D400lice'})
        self.assertFalse(form.is_valid())
        self.assertIn("decorative letters", str(form.errors['username']))

    def test_accented_and_cjk_usernames_still_register(self):
        for username, email in [('josé', 'jose@example.com'),
                                ('李明', 'liming@example.com')]:
            resp = self._register(username, email)
            self.assertRedirects(resp, reverse('django_registration_complete'))
            self.assertTrue(User.objects.filter(username=username).exists())

    def test_is_disposable(self):
        from .emailcheck import is_disposable
        self.assertFalse(is_disposable('eric@hellman.net'))
        self.assertTrue(is_disposable('eric@mailnesia.com'))


class TestNotARobotPuzzle(TestCase):
    """The puzzle code must not depend on per-process state: on the servers the page is
    rendered by one mod_wsgi process and often checked by another."""

    def notarobot_errors(self, answer, tries):
        form = UserNamePass(data={'notarobot': str(answer), 'tries': tries})
        form.is_valid()
        return form.errors.get('notarobot')

    def test_rendered_puzzle_accepted(self):
        glyph_to_int = {glyph: n for n, glyph in puzzle.digits.items()}
        for _ in range(20):
            context = {}
            puzzle.puzz(context)
            answer = glyph_to_int[context['puzznum1']] + glyph_to_int[context['puzznum2']]
            self.assertIsNone(self.notarobot_errors(answer, context['puzzans']))

    def test_every_answer_has_its_own_code(self):
        self.assertEqual(len({encode_answer(n) for n in range(21)}), 21)

    def test_wrong_answer_rejected(self):
        self.assertIsNotNone(self.notarobot_errors(12, encode_answer(11)))

    def test_tampered_or_missing_code_rejected(self):
        self.assertIsNotNone(self.notarobot_errors(11, encode_answer(11)[:-1] + 'x'))
        self.assertIsNotNone(self.notarobot_errors(11, '11'))
        self.assertIsNotNone(self.notarobot_errors(11, ''))


class TestFailedActivation(TestCase):
    """An activation link that does not work shows a page saying so.

    django_registration renders django_registration/activation_failed.html
    when activation fails. The app had no template by that name, so the
    visitor got a 500. (#1289)
    """
    fixtures = ['initial_data.json']
    PROBLEM = 'your activation key is invalid'

    def activation_key(self, username):
        from django.core import signing
        from django_registration.backends.activation.views import REGISTRATION_SALT
        return signing.dumps(obj=username, salt=REGISTRATION_SALT)

    def activate(self, key):
        return self.client.get(
            reverse('django_registration_activate', kwargs={'activation_key': key}))

    def test_a_mangled_link_shows_the_problem_page(self):
        resp = self.activate('not-a-real-key')
        self.assertEqual(200, resp.status_code)
        self.assertContains(resp, self.PROBLEM)

    def test_an_already_used_link_shows_the_problem_page(self):
        User.objects.create_user('bob', 'bob@example.com', 'secret', is_active=True)
        resp = self.activate(self.activation_key('bob'))
        self.assertEqual(200, resp.status_code)
        self.assertContains(resp, self.PROBLEM)


class TestAppConfigSignalsWired(TestCase):
    """Regression guard for issue #1175.

    Django 4.1 removed `default_app_config`, and an AppConfig defined in an app's
    __init__.py is NOT auto-discovered (Django only scans <app>/apps.py). When that
    regression bit during the 4.2 cutover, LibraryAuthConfig.ready() stopped running
    and signals.py was never imported. These tests fail if the config ever moves back
    out of apps.py or otherwise stops being the active config.
    """

    def test_appconfig_is_discovered(self):
        from django.apps import apps
        from regluit.libraryauth.apps import LibraryAuthConfig
        self.assertIsInstance(apps.get_app_config('libraryauth'), LibraryAuthConfig)

    def test_user_activated_receiver_connected(self):
        # ready() must have imported signals.py and connected the dedup receiver.
        from django_registration.signals import user_activated
        names = []
        for entry in user_activated.receivers:
            # Django <5.0: (lookup_key, receiver); Django >=5.0: (lookup_key, receiver, is_async)
            ref = entry[1]
            fn = ref if getattr(ref, '__name__', None) else (ref() if callable(ref) else None)
            names.append(getattr(fn, '__name__', None))
        self.assertIn('handle_same_email_account', names)


class TestLogoutView(TestCase):
    """Regression guard for the logout-405 incident (2026-08-29).

    Django 5.0 removed GET support from django.contrib.auth.views.LogoutView
    (deprecated in 4.1, flagged as a known follow-up in PR #1145, never
    fixed). The 5.2 upgrade (PR #1203, live in prod 2026-08-26) exposed it:
    every "Sign Out" / "log out" link in the site was a plain GET <a>, so
    /accounts/logout/ started 405ing for real users. Fixed by turning those
    links into POST forms (base.html's nav, gift_user_error.html,
    pledge_user_error.html). These tests would have caught it.
    """
    fixtures = ['initial_data.json']

    # A bare TemplateView (no view-layer business logic / DB lookups) that
    # still extends base.html -- lets these tests exercise the real nav
    # markup without depending on unrelated data (e.g. the homepage's
    # featured-campaign query).
    NAV_PAGE = '/accounts/superlogin/welcome/'

    def setUp(self):
        self.user = User.objects.create_user('logouttester', 'logouttester@example.org', 'secret')

    def test_get_is_405(self):
        # Documents the Django 5.0 behavior change itself, independent of
        # any of this app's templates.
        resp = self.client.get(reverse('logout'))
        self.assertEqual(405, resp.status_code)
        self.assertIn('POST', resp['Allow'])

    def test_post_logs_out_and_redirects(self):
        self.client.login(username='logouttester', password='secret')
        resp = self.client.post(reverse('logout'))
        self.assertEqual(302, resp.status_code)
        # Session should no longer be authenticated.
        resp = self.client.get(self.NAV_PAGE)
        self.assertFalse(resp.wsgi_request.user.is_authenticated)

    def test_post_honors_next(self):
        self.client.login(username='logouttester', password='secret')
        resp = self.client.post(reverse('logout'), data={'next': '/some/safe/path/'})
        self.assertRedirects(resp, '/some/safe/path/', fetch_redirect_response=False)

    def test_post_rejects_external_next_as_open_redirect(self):
        # RedirectURLMixin validates 'next' against the request's own host
        # and scheme -- a POST logout must not become an open redirect via
        # a crafted next= pointing off-site. This is Django's own guard
        # (url_has_allowed_host_and_scheme), exercised here through this
        # app's actual settings/URLconf as a regression/documentation test.
        #
        # Assert equality with the exact safe fallback (LOGOUT_REDIRECT_URL
        # = '/'), not just "doesn't contain the evil hostname" -- a looser
        # substring check would miss a bypass that lands somewhere else
        # unsafe without literally containing that string (CC review,
        # 2026-08-29).
        self.client.login(username='logouttester', password='secret')
        resp = self.client.post(reverse('logout'), data={'next': 'https://evil.example.com/phish'})
        self.assertRedirects(resp, '/', fetch_redirect_response=False)

    def test_authenticated_nav_sign_out_is_a_post_form_not_a_get_link(self):
        # Renders base.html's authenticated nav and checks the "Sign Out"
        # control POSTs -- with a real method="post" and a CSRF token, not
        # just *some* form -- rather than being a plain
        # <a href="/accounts/logout/"> (the exact shape of the original bug).
        self.client.login(username='logouttester', password='secret')
        resp = self.client.get(self.NAV_PAGE)
        self.assertEqual(200, resp.status_code)
        content = resp.content.decode('utf-8')
        logout_url = reverse('logout')

        self.assertNotIn("href=\"{}\"".format(logout_url), content)
        self.assertNotIn("href='{}'".format(logout_url), content)

        soup = BeautifulSoup(content, 'html.parser')
        form = soup.find('form', action=logout_url)
        self.assertIsNotNone(form, "no <form action='{}'> found in the nav".format(logout_url))
        self.assertEqual('post', (form.get('method') or '').lower())
        csrf_input = form.find('input', attrs={'name': 'csrfmiddlewaretoken'})
        self.assertIsNotNone(csrf_input, "logout form is missing {% csrf_token %}")
        self.assertTrue(csrf_input.get('value'))
        submit = form.find('button', attrs={'type': 'submit'}) or form.find('input', attrs={'type': 'submit'})
        self.assertIsNotNone(submit, "logout form has no submit control")


class TestLogoutFormsInErrorTemplates(TestCase):
    """Markup-level regression guard for the two error-page 'log out' links
    (see TestLogoutView's docstring for the incident this is guarding
    against). These templates render inside a <p>, where a nested <form> is
    invalid HTML -- so the fix uses a hidden <form> placed outside the <p>
    plus an inline <button form="..."> instead. These tests render each
    template directly (bypassing the heavier pledge/gift view logic, which
    needs real Transaction/Envelope fixtures unrelated to this fix) and
    assert the button/form wiring is actually correct: matching ids, a real
    POST method, a CSRF token, and the expected 'next' value.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def _rendered(self, template_name, extra_context, path='/some/page/'):
        request = self.factory.get(path)
        request.user = AnonymousUser()
        html = render_to_string(template_name, extra_context, request=request)
        return BeautifulSoup(html, 'html.parser'), path

    def _assert_button_form_wired_correctly(self, soup, button_text, expected_next):
        button = soup.find('button', string=lambda s: s and button_text in s)
        self.assertIsNotNone(button, "no <button> containing {!r}".format(button_text))
        form_id = button.get('form')
        self.assertTrue(form_id, "log out button has no form= attribute")

        form = soup.find('form', id=form_id)
        self.assertIsNotNone(form, "no <form id='{}'> for the log out button".format(form_id))
        self.assertEqual('post', (form.get('method') or '').lower())
        self.assertEqual(reverse('logout'), form.get('action'))

        csrf_input = form.find('input', attrs={'name': 'csrfmiddlewaretoken'})
        self.assertIsNotNone(csrf_input, "log out form is missing {% csrf_token %}")

        next_input = form.find('input', attrs={'name': 'next'})
        self.assertIsNotNone(next_input, "log out form is missing the next= hidden input")
        self.assertEqual(expected_next, next_input.get('value'))

        # The button must live outside the <p> the form-in-<p> HTML bug
        # would have put it in -- confirm it is NOT a descendant of <form>
        # (that would mean we went back to nesting a <form> inside a <p>).
        self.assertIsNone(button.find_parent('form'))

    def test_gift_user_error_logout_form(self):
        soup, path = self._rendered(
            'gift_user_error.html',
            {'envelope': SimpleNamespace(amount=5, cents='00', username='otheruser')},
        )
        self._assert_button_form_wired_correctly(soup, 'log out', expected_next=path)

    def test_pledge_user_error_logout_form(self):
        soup, path = self._rendered(
            'pledge_user_error.html',
            {
                'action': 'pledge',
                'transaction': SimpleNamespace(user=SimpleNamespace(username='otheruser')),
            },
        )
        self._assert_button_form_wired_correctly(soup, 'log out', expected_next=path)
