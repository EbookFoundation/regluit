#external library imports
import re
import mimetypes

#django imports
from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import Client

#regluit imports
from regluit.core.models import Work, RightsHolder, Claim, Subject

class WishlistTests(TestCase):
    fixtures = ['initial_data.json', 'neuromancer.json']
    def setUp(self):
        self.user = User.objects.create_user('test', 'test@example.org', 'test')
        self.client = Client()
        self.client.login(username='test', password='test')

    def test_add_remove(self):
        # add a book to the wishlist
        r = self.client.post("/wishlist/", {"googlebooks_id": "IDFfMPW32hQC"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.user.wishlist.works.all().count(), 1)
        wished = self.user.wishlist.works.first()
        # test the work page
        r = self.client.get("/work/%s/" % wished.id)
        self.assertEqual(r.status_code, 200)
        anon_client = Client()
        r = anon_client.get("/work/%s/" % wished.id)
        self.assertEqual(r.status_code, 200)

        # remove the book
        r = self.client.post("/wishlist/", {"remove_work_id": wished.id},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(self.user.wishlist.works.all().count(), 0)

class RhPageTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('test', 'test@example.org', 'test')
        self.rh_user =  User.objects.create_user('rh', 'rh@example.org', 'test')
        self.staff_user =  User.objects.create_superuser('staff', 'staff@example.org', 'test')
        self.work = Work.objects.create(title="test work", language='en')
        rh = RightsHolder.objects.create(rights_holder_name='test', owner=self.rh_user)
        Claim.objects.create(work=self.work, user=self.rh_user, status='active', rights_holder=rh)
        self.kw = Subject.objects.create(name="Fiction")

    def test_anonymous(self):
        anon_client = Client()
        r = anon_client.get("/work/{}/".format(self.work.id))
        r = anon_client.head("/work/{}/".format(self.work.id))
        self.assertEqual(r.status_code, 200)
        csrfmatch =  re.search("name='csrfmiddlewaretoken' value='([^']*)'", str(r.content, 'utf-8'))
        self.assertFalse(csrfmatch)
        r = anon_client.post("/work/{}/kw/".format(self.work.id))
        self.assertEqual(r.status_code, 302)

    def can_edit(self, client, can=True):
        r = client.get("/work/{}/".format(self.work.id))
        self.assertEqual(r.status_code, 200)
        csrfmatch =  re.search("name='csrfmiddlewaretoken' value='([^']*)'", str(r.content, 'utf-8'))
        self.assertTrue(csrfmatch)
        csrf = csrfmatch.group(1)
        r = client.post("/work/{}/kw/".format(self.work.id), {
                'csrfmiddlewaretoken': csrf,
                'kw_add':'true',
                'add_kw_0':'Fiction',
                'add_kw_1':self.kw.id
            })
        if can:
            self.assertEqual(r.content, b'Fiction')
        else:
            self.assertEqual(r.content, b'true')
        r = client.post("/work/{}/kw/".format(self.work.id), {
                'csrfmiddlewaretoken': csrf,
                'remove_kw' : 'Fiction'
            })
        if can:
            self.assertEqual(r.content, b'removed Fiction')
        else:
            self.assertEqual(r.content, b'False')

    def test_user(self):
        # test non-RightsHolder
        client = Client()
        client.login(username='test', password='test')
        self.can_edit(client, can=False)

    def test_rh(self):
        # test RightsHolder
        client = Client()
        client.login(username='rh', password='test')
        self.can_edit(client)

    def test_staff(self):
        client = Client()
        client.login(username='staff', password='test')
        self.can_edit(client)


class PageTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('test', 'test@example.org', 'test')
        User.objects.create_user('test_other', 'test@example.org', 'test_other')
        self.client = Client()
        self.client.login(username='test', password='test')
        w = Work.objects.create(title="test work", language='en')

    def test_setttings(self):
        self.assertEqual(mimetypes.guess_type('/whatever/my_file.epub')[0], 'application/epub+zip')

    def test_view_by_self(self):
        # logged in
        r = self.client.get("/supporter/test/")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/search/?q=sverige")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/search/?q=sverige&page=2")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/notification/settings/")
        self.assertEqual(r.status_code, 200)

    def test_view_by_other(self):
        # someone else's supporter page
        r = self.client.get("/supporter/test_other/")
        self.assertEqual(r.status_code, 200)

    def test_view_by_anonymous(self):
        # not logged in
        anon_client = Client()
        r = anon_client.get("/supporter/test/")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/search/?q=sverige")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/search/?q=sverige&page=2")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/info/metrics.html")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/marc/")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/creativecommons/?order_by=popular")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/creativecommons/by")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/free/by-nc/?order_by=title")
        self.assertEqual(r.status_code, 200)
        r = anon_client.get("/free/epub/gfdl/")
        self.assertEqual(r.status_code, 200)

class AllFacetAliasTests(TestCase):
    fixtures = ['initial_data.json', 'neuromancer.json']

    def test_all_keyword_alias_matches_keyword_path(self):
        plain = self.client.get("/free/kw.Fiction/?order_by=newest")
        alias = self.client.get("/free/all/kw.Fiction/?order_by=newest")
        self.assertEqual(plain.status_code, 200)
        self.assertEqual(alias.status_code, 200)

    def test_all_non_keyword_alias_matches_compound_path(self):
        plain = self.client.get("/free/epub/doab/?order_by=newest")
        alias = self.client.get("/free/all/epub/doab/?order_by=newest")
        self.assertEqual(plain.status_code, 200)
        self.assertEqual(alias.status_code, 200)

class FacetIsolationTests(TestCase):
    """Tests for #1110: keyword/subject facets cannot combine with other facets."""
    fixtures = ['initial_data.json', 'neuromancer.json']

    def test_base_free_page_offers_keywords(self):
        """The base /free/ page should offer keyword facets in the sidebar."""
        r = self.client.get("/free/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Keyword")

    def test_keyword_page_no_refine_sidebar(self):
        """A keyword facet page should NOT offer further facet refinement."""
        r = self.client.get("/free/kw.Fiction/")
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Show me only")

    def test_non_keyword_page_excludes_keywords(self):
        """A non-keyword facet page should offer refinement but NOT keywords."""
        r = self.client.get("/free/epub/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Show me only")
        self.assertNotContains(r, "Keyword")

    def test_single_keyword_still_works(self):
        r = self.client.get("/free/kw.Fiction/")
        self.assertEqual(r.status_code, 200)

    def test_keyword_compound_returns_404(self):
        r = self.client.get("/free/kw.Fiction/epub/")
        self.assertEqual(r.status_code, 404)

    def test_keyword_compound_reversed_returns_404(self):
        r = self.client.get("/free/epub/kw.Fiction/")
        self.assertEqual(r.status_code, 404)

    def test_keyword_with_all_prefix_still_works(self):
        r = self.client.get("/free/all/kw.Fiction/")
        self.assertEqual(r.status_code, 200)

    def test_non_keyword_compound_still_works(self):
        r = self.client.get("/free/epub/doab/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "EPUB format")
        self.assertContains(r, "Directory of Open Access Books")

class GoogleBooksTest(TestCase):
    fixtures = ['initial_data.json', 'neuromancer.json']
    def test_googlebooks_id(self):
        r = self.client.get("/googlebooks/IDFfMPW32hQC/")
        self.assertEqual(r.status_code, 302)
        work_url = r['location']
        self.assertTrue(re.match(r'.*/work/\d+/$', work_url))



from django.test import SimpleTestCase
from django.template import Template, Context
from regluit.utils.html import sanitize_html


class SanitizeRichTextTests(SimpleTestCase):
    """Server-side sanitization of CKEditor rich text (security-private#26)."""

    def test_strips_script(self):
        self.assertEqual(sanitize_html('<script>alert(1)</script>hi'), 'hi')

    def test_strips_event_handlers(self):
        self.assertNotIn('onerror', sanitize_html(
            '<img src="https://s3/c.jpg" alt="c" onerror="alert(1)">'))

    def test_strips_javascript_url(self):
        self.assertNotIn('javascript:', sanitize_html(
            '<a href="javascript:alert(1)">x</a>'))

    def test_keeps_allowed_formatting(self):
        out = sanitize_html('<p>Hello <strong>world</strong> <em>ok</em></p>'
                            '<blockquote>q</blockquote><ul><li>a</li></ul>')
        for frag in ('<strong>world</strong>', '<em>ok</em>',
                     '<blockquote>q</blockquote>', '<li>a</li>'):
            self.assertIn(frag, out)

    def test_keeps_safe_links_and_images(self):
        out = sanitize_html('<a href="https://x.com">l</a>'
                            '<img src="https://s3/c.jpg" alt="c">')
        self.assertIn('href="https://x.com"', out)
        self.assertIn('src="https://s3/c.jpg"', out)

    def test_none_passthrough(self):
        self.assertIsNone(sanitize_html(None))

    def test_template_filter_strips_and_marks_safe(self):
        rendered = Template(
            '{% load sanitizer %}{{ body|sanitize }}'
        ).render(Context({'body': '<b>ok</b><script>alert(1)</script>'}))
        self.assertIn('<b>ok</b>', rendered)
        self.assertNotIn('<script>', rendered)  # not escaped, actually removed
        self.assertNotIn('&lt;script&gt;', rendered)
class FeedbackSelfLinkTests(TestCase):
    """Regression: the feedback page must not link back to itself with a
    ?page=<current-url> parameter. That self-reference (emitted by the base
    template's footer/nav on every page, including /feedback/ itself) created
    an infinite, self-encoding URL space that crawler fleets walked at tens of
    thousands of requests per hour on 2026-07-10, saturating the web workers.
    See INCIDENT_2026-07-10_crawler_trap_flood.md."""

    def test_feedback_page_has_no_self_referencing_link(self):
        r = Client().get("/feedback/")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("/feedback/?page=", str(r.content, 'utf-8'))

    def test_feedback_page_with_page_param_has_no_self_referencing_link(self):
        # Even a crawler-style request that already carries an encoded
        # feedback URL must not be handed a deeper level of nesting.
        # Since #1261 that request is redirected to the bare URL rather than
        # rendered; follow it and check the page it lands on, which is where a
        # deeper level of nesting would have to appear.
        r = Client().get("/feedback/", {"page": "https://testserver/feedback/?page=x"},
                         follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.redirect_chain, [("/feedback/", 301)])
        # Assert on hrefs specifically: the form legitimately echoes the
        # recovered page in a hidden field / subject line, but no LINK
        # (the crawlable surface) may carry a parameterized feedback URL.
        self.assertNotIn('href="/feedback/?page=', str(r.content, 'utf-8'))

    def test_feedback_login_chain_reaches_fixed_point(self):
        # Codex round-2 finding: on /feedback/ the Sign In link's ?next=
        # embedded the full feedback URL, so a crawler alternating
        # feedback -> superlogin -> feedback -> superlogin got ever-growing
        # URLs. With auth_next using the bare path on the feedback route,
        # the chain must reach a fixed point instead.
        #
        # Since #1261 the sign-in link's href no longer carries ?next= at all
        # (the value moved to data-next, promoted into the href by JS), so the
        # crawler-visible chain is bounded twice over. The assertion below is
        # now on data-next: the value a *JS browser* would walk must still
        # reach a fixed point, which is what the July fix guarantees.
        import re
        c = Client()

        def signin_next(html):
            m = re.search(r'<a [^>]*class="[^"]*js-auth-next[^"]*"[^>]*'
                          r'href="(/accounts/superlogin/[^"]*)"[^>]*'
                          r'data-next="([^"]*)"', html)
            self.assertIsNotNone(m, "no sign-in link found")
            # The href itself must be the bare, constant login URL.
            self.assertEqual(m.group(1), "/accounts/superlogin/")
            return m.group(2)

        def feedback_href(html):
            m = re.search(r'href="(/feedback/[^"]*)"', html)
            self.assertIsNotNone(m, "no feedback link found")
            return m.group(1)

        # Start from a crawled old-style URL; it now redirects to the bare
        # one, so follow redirects throughout the chain.
        url = "/feedback/?page=https%3A%2F%2Ftestserver%2Fwork%2F1%2F"
        seen = set()
        for _ in range(4):
            r = c.get(url, follow=True)
            self.assertEqual(r.status_code, 200)
            html = str(r.content, 'utf-8')
            # next must be the bare feedback path, never a growing URL
            self.assertEqual(signin_next(html), "%2Ffeedback%2F")
            login = "/accounts/superlogin/?next=%2Ffeedback%2F"
            r2 = c.get(login)
            self.assertEqual(r2.status_code, 200)
            url = feedback_href(str(r2.content, 'utf-8'))
            self.assertLess(len(url), 300, "chain URL should not grow")
            if url in seen:
                break
            seen.add(url)
        else:
            self.fail("feedback/login chain did not reach a fixed point in 4 rounds")

    def test_feedback_url_tag_ignores_its_context(self):
        # The tag used to read the request, which is precisely how every page
        # got its own feedback URL. It must now render one constant string
        # whatever context it is handed -- including none at all, as on the
        # error pages. Asserting only the no-context case would pass even if
        # the per-page parameter came back.
        from django.template import Context, Template
        from django.test import RequestFactory
        template = Template("{% load feedback_link %}{% feedback_url %}")
        factory = RequestFactory()
        rendered = {
            template.render(Context({})),
            template.render(Context({'request': factory.get('/work/1/?tab=2')})),
            template.render(Context({'request': factory.get('/feedback/')})),
        }
        self.assertEqual(rendered, {"/feedback/"})


class FeedbackUrlSpaceTests(TestCase):
    """Every page used to mint its own /feedback/?page=<this page> URL. On
    2026-09-17 production served 702,435 requests to /feedback/ across 693,968
    distinct URLs -- uncacheable by construction, and a direct cause of four
    outages. The link is now one constant URL site-wide and the originating
    page is recovered from the Referer header. See issue #1261."""

    FEEDBACK_HREF = re.compile(r'href="(/feedback/[^"]*)"')
    HIDDEN_PAGE = re.compile(r'name="page"[^>]*value="([^"]*)"')

    # Pages that carry a feedback link, sampled across query-string shapes.
    SAMPLE_PAGES = (
        ("/privacy/", {}),
        ("/faq/", {}),
        ("/search/", {"q": "sverige"}),
        ("/search/", {"q": "sverige", "page": "2"}),
        ("/feedback/", {}),
    )

    def page_field(self, response):
        m = self.HIDDEN_PAGE.search(str(response.content, 'utf-8'))
        self.assertIsNotNone(m, "no hidden page field in the feedback form")
        return m.group(1)

    def test_every_page_emits_exactly_one_feedback_url(self):
        # The whole point of #1261: one URL site-wide, so the space does not
        # grow with the ~2M crawlable pages.
        emitted = set()
        for path, query in self.SAMPLE_PAGES:
            r = Client().get(path, query)
            self.assertEqual(r.status_code, 200, path)
            hrefs = set(self.FEEDBACK_HREF.findall(str(r.content, 'utf-8')))
            self.assertIn("/feedback/", hrefs, "no bare feedback link on %s" % path)
            emitted |= hrefs
        self.assertEqual(emitted, {"/feedback/"})

    def test_no_feedback_link_embeds_a_page_url(self):
        # The failure mode being fixed: a feedback link carrying the current
        # page's URL. Nothing url-shaped may appear in a feedback href.
        for path, query in self.SAMPLE_PAGES:
            r = Client().get(path, query)
            for href in self.FEEDBACK_HREF.findall(str(r.content, 'utf-8')):
                self.assertNotIn("%3A", href, path)   # encoded ':' -- a scheme
                self.assertNotIn("%2F", href, path)   # encoded '/' -- a path
                self.assertNotIn("http", href, path)

    # A feedback URL with a query string, built by hand in a template.
    # Matches {% feedback_url %}?..., {% url 'feedback' %}?... and a literal
    # /feedback/?..., either quoting style. Nothing may do this any more: the
    # view redirects it away. {% feedback_url %} is first because it is now the
    # idiomatic spelling, and so the shape a future edit would most likely take.
    HAND_WRITTEN_QUERY = re.compile(
        r"""(?:\{%\s*feedback_url\s*%\}"""
        r"""|\{%\s*url\s+['"]feedback['"]\s*%\}"""
        r"""|/feedback/)\?"""
    )

    # Every feedback link needs referrerpolicy="same-origin" or the site-wide
    # "origin" policy truncates the Referer to the bare origin -- and the
    # same-host check accepts that, so staff would be told the user was on the
    # home page when they were on a 404 or a 500. A wrong attribution is worse
    # than the honest '/' a missing Referer gives. Four templates were missed
    # on the first pass, which is why this is a test and not a convention.
    FEEDBACK_ANCHOR = re.compile(
        r"""<a\b[^>]*\bhref\s*=\s*["']"""
        r"""(?:\{%\s*feedback_url\s*%\}"""
        r"""|\{%\s*url\s+['"]feedback['"]\s*%\}"""
        r"""|/feedback/)[^>]*>""",
        re.IGNORECASE,
    )
    REFERRER_POLICY = re.compile(r"""referrerpolicy\s*=\s*["']same-origin["']""",
                                 re.IGNORECASE)

    def test_no_frontend_template_hand_writes_a_feedback_url_with_a_query(self):
        # Structural guard. The tag is safe by construction now, so the way
        # the space comes back is a template building a feedback URL by hand
        # -- which six notification templates and three FAQ/privacy links were
        # still doing when #1261 was written. This catches that shape in the
        # source rather than in the access log.
        #
        # A tripwire for the known pattern, not a proof, and the name says
        # "frontend" for a reason: it walks frontend/templates only. api/,
        # libraryauth/ and payment/ have their own template directories (none
        # references feedback today). An attribute split across lines, or a URL
        # assembled some other way, would also slip past.
        import os
        templates = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'templates')
        offenders = []
        for dirpath, _, filenames in os.walk(templates):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                # a couple of templates are not valid utf-8, and only the
                # ascii of a template tag matters here
                with open(path, encoding='utf-8', errors='replace') as f:
                    for n, line in enumerate(f, 1):
                        if self.HAND_WRITTEN_QUERY.search(line):
                            offenders.append("%s:%d" % (path, n))
        self.assertEqual(offenders, [], "feedback URLs with a query string")

    def test_every_frontend_feedback_link_sets_a_referrer_policy(self):
        # Companion tripwire. A feedback link without referrerpolicy degrades
        # silently rather than visibly: the site-wide "origin" policy truncates
        # the Referer to https://unglue.it/, the same-host check accepts it,
        # and staff are told the user was on the home page when they were on a
        # 404 or a 500. Four templates were missed on the first sweep.
        import os
        templates = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'templates')
        offenders = []
        for dirpath, _, filenames in os.walk(templates):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                with open(path, encoding='utf-8', errors='replace') as f:
                    for n, line in enumerate(f, 1):
                        for anchor in self.FEEDBACK_ANCHOR.findall(line):
                            if not self.REFERRER_POLICY.search(anchor):
                                offenders.append("%s:%d" % (path, n))
        self.assertEqual(offenders, [], "feedback links without referrerpolicy")

    def test_methods_other_than_post_do_not_render_a_query_url(self):
        # OPTIONS and TRACE are CSRF-exempt, so before this they reached a
        # full render for every distinct URL, exactly like GET did.
        c = Client()
        for method in ('get', 'head', 'options', 'delete', 'put'):
            r = getattr(c, method)("/feedback/?page=http%3A%2F%2Ftestserver%2Fx")
            self.assertEqual(r.status_code, 301, method)
            self.assertEqual(r["Location"], "/feedback/", method)

    def test_feedback_links_carry_nofollow_and_a_referrer_policy(self):
        # referrerpolicy is what makes the Referer usable at all. The site has
        # sent <meta name="referrer" content="origin"> since 2015, which
        # truncates even a same-origin Referer to "https://unglue.it/" -- so
        # without a per-link override every feedback report would name the
        # same useless page. The override is scoped to these links: nothing
        # else about what the site sends to third parties changes.
        r = Client().get("/privacy/")
        content = str(r.content, 'utf-8')
        self.assertIn('<meta name="referrer" content="origin" />', content)
        self.assertIn(
            'href="/feedback/" rel="nofollow" referrerpolicy="same-origin"',
            content,
        )

    def test_pagination_state_reaches_the_form_via_the_referer(self):
        # Pagination state used to ride in the feedback URL (and a July 2026
        # regression guard checked it survived there). It now reaches the form
        # through the Referer instead.
        came_from = "http://testserver/search/?q=sverige&page=2"
        r = Client().get("/feedback/", HTTP_REFERER=came_from)
        self.assertEqual(self.page_field(r), came_from.replace("&", "&amp;"))

    def test_referer_supplies_the_originating_page(self):
        came_from = "http://testserver/work/9/"
        r = Client().get("/feedback/", HTTP_REFERER=came_from)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.page_field(r), came_from)
        self.assertIn("Feedback on page " + came_from, str(r.content, 'utf-8'))

    def test_no_referer_degrades_to_slash(self):
        r = Client().get("/feedback/")
        self.assertEqual(self.page_field(r), "/")

    def test_foreign_referer_is_ignored(self):
        for referer in ("http://evil.example.com/x",
                        "http://testserver.evil.example.com/x",
                        "http://evil@evil.example.com/x",
                        "https://testserver:8443/x",
                        "javascript:alert(1)",
                        "not a url at all",
                        "//testserver/x"):
            r = Client().get("/feedback/", HTTP_REFERER=referer)
            self.assertEqual(r.status_code, 200, referer)
            self.assertEqual(self.page_field(r), "/", referer)

    def test_malformed_referer_does_not_error(self):
        # urlsplit raises ValueError on a bad IPv6 literal
        r = Client().get("/feedback/", HTTP_REFERER="http://[::1/x")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.page_field(r), "/")

    def test_any_query_string_redirects_to_the_canonical_url(self):
        # The 693,968 URLs that caused the outage are in crawler queues
        # already. Not emitting them any more does nothing about that, so
        # every one of them is answered with a cheap permanent redirect
        # instead of a full render.
        for query in ("page=http%3A%2F%2Ftestserver%2Fwork%2F9%2F",
                      "page=need+support",
                      "page=",
                      "utm_source=whatever",
                      "tab=2&page=3",
                      # these parse to an EMPTY QueryDict but are still
                      # distinct URLs to a crawler (Codex round-3 finding)
                      "&",
                      "&&"):
            r = Client().get("/feedback/?" + query)
            self.assertEqual(r.status_code, 301, query)
            self.assertEqual(r["Location"], "/feedback/", query)
            self.assertNotIn(b"<form", r.content, query)

    def test_a_referer_on_an_old_link_survives_the_redirect(self):
        # Django's test client re-sends the header through the redirect. A
        # browser may do the same for a same-origin 301, but that depends on
        # the applicable referrer policy and the test client is not evidence
        # about browsers. It is a corner case either way: nothing emits ?page=
        # links any more, so the expected arrival at these URLs is a crawler
        # with no Referer, which lands on '/'.
        r = Client().get("/feedback/?page=http%3A%2F%2Ftestserver%2Fold%2F",
                         HTTP_REFERER="http://testserver/work/9/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.redirect_chain, [("/feedback/", 301)])
        self.assertEqual(self.page_field(r), "http://testserver/work/9/")

    def test_ask_rh_is_not_caught_by_the_redirect(self):
        # ask_rh shares this view but lives at /feedback/campaign/<id>/. A
        # query string there must reach ask_rh, not be redirected to the
        # feedback form -- so a missing campaign 404s, as it always did.
        r = Client().get("/feedback/campaign/999999/?anything=1")
        self.assertEqual(r.status_code, 404)

    def test_the_form_is_not_cacheable(self):
        # One URL for everyone is exactly what invites a cache in front, and
        # the response carries a CSRF token, a one-time captcha and a page
        # derived from this request's Referer.
        r = Client().get("/feedback/", HTTP_REFERER="http://testserver/work/9/")
        self.assertIn("no-store", r["Cache-Control"])
        self.assertIn("no-cache", r["Cache-Control"])

    def test_referer_value_cannot_inject_a_mail_header(self):
        r = Client().get(
            "/feedback/",
            HTTP_REFERER="http://testserver/x\r\nBcc: someone@example.org")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.page_field(r),
                         "http://testserver/x Bcc: someone@example.org")

    def test_referer_value_is_bounded_and_marked(self):
        # Truncation has to be visible: staff clicking a silently-cut URL get
        # a 404 and no way to tell that the link was incomplete.
        r = Client().get("/feedback/",
                         HTTP_REFERER="http://testserver/" + "u" * 500)
        page = self.page_field(r)
        self.assertEqual(len(page), 200)
        self.assertTrue(page.endswith("..."), page[-10:])

    def test_a_short_referer_is_not_marked(self):
        r = Client().get("/feedback/", HTTP_REFERER="http://testserver/work/9/")
        self.assertEqual(self.page_field(r), "http://testserver/work/9/")

    def test_post_keeps_the_submitted_page_not_the_referer(self):
        # On POST the Referer is /feedback/ itself; the page the user came
        # from rides along in the hidden field and must survive a form error.
        r = Client().post("/feedback/", {
            'sender': 'someone@example.org',
            'subject': 'Feedback on page http://testserver/work/9/',
            'message': 'hi',
            'page': 'http://testserver/work/9/',
            'num1': '1', 'num2': '2', 'answer': '3',
            'notarobot': '4',  # wrong sum: re-renders the form
        }, HTTP_REFERER="http://testserver/feedback/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.page_field(r), "http://testserver/work/9/")

    def test_post_without_the_captcha_fields_rerenders_the_form(self):
        # Form-spam bots post without the hidden num1/num2 fields; that used to
        # raise MultiValueDictKeyError (a 500 and an error email).
        import re
        for missing, blank in ((['num2'], []), (['num1'], []),
                               (['num1', 'num2', 'answer'], []), ([], ['num2'])):
            data = {
                'sender': 'someone@example.org',
                'subject': 'hi',
                'message': 'hi',
                'page': 'http://testserver/work/9/',
                'num1': '1', 'num2': '2', 'answer': '3', 'notarobot': '3',
            }
            for field in missing:
                del data[field]
            for field in blank:
                data[field] = ''
            r = Client().post("/feedback/", data)
            self.assertEqual(r.status_code, 200, (missing, blank))
            html = r.content.decode()
            # The puzzle shown and the hidden answer it is checked against agree.
            shown = re.search(r"not a robot\. (\d+) \+ (\d+) =", html)
            hidden = re.search(r'name="answer" value="(\d+)"|value="(\d+)" name="answer"', html)
            self.assertIsNotNone(shown, (missing, blank))
            self.assertIsNotNone(hidden, (missing, blank))
            self.assertEqual(int(shown.group(1)) + int(shown.group(2)),
                             int(hidden.group(1) or hidden.group(2)), (missing, blank))

    def test_form_collapses_newlines_in_the_subject(self):
        # A newline here would raise BadHeaderError inside the celery task,
        # long after the user has been shown a thank-you page.
        from regluit.frontend.forms import FeedbackForm
        form = FeedbackForm(data={
            'sender': 'someone@example.org',
            'subject': 'hello\r\nBcc: someone@example.org',
            'message': 'hi',
            'page': '/',
            'num1': '1', 'num2': '2', 'answer': '3', 'notarobot': '3',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['subject'],
                         'hello Bcc: someone@example.org')

AUTH_LINK_RE = re.compile(r'<a [^>]*class="[^"]*js-auth-next[^"]*"[^>]*>')
GOOGLE_LINK_RE = re.compile(r'<a [^>]*href="(/socialauth/login/google-oauth2/[^"]*)"')


def auth_link_hrefs(html):
    """Every href on a site-wide Sign In / Sign Up link, in document order."""
    return [re.search(r'href="([^"]*)"', tag).group(1)
            for tag in AUTH_LINK_RE.findall(html)]


def auth_link_nexts(html):
    """Every data-next value on a site-wide Sign In / Sign Up link."""
    return [re.search(r'data-next="([^"]*)"', tag).group(1)
            for tag in AUTH_LINK_RE.findall(html)]


class SignInUrlSpaceTests(TestCase):
    """Regression: the site-wide Sign In / Sign Up links must be the SAME URL on
    every crawlable page.

    They used to carry ?next=<current page>, so each of the site's ~2M crawlable
    pages minted its own sign-in URL, and the login page propagated that value
    into the Google sign-in link -- the expensive endpoint, since serving it
    holds a web worker while it waits on an outbound call to Google. Production
    saw 184,125 requests to it on 2026-09-17 across 175,983 *distinct* URLs, a
    repeat rate no cache can absorb. See issue #1261.

    The per-page value now rides in data-next and is promoted into the href by
    sitewide1.js, so a real browser behaves exactly as before while the
    server-rendered link graph holds one sign-in URL instead of two million.

    Scope, stated precisely: this is about the *site-wide* Sign In / Sign Up
    links, the only ones rendered on every page. Google sign-in links on
    home.html, from_pledge.html and gift_login.html still carry ?next= in the
    href, and those are NOT strictly bounded -- home.html passes through
    request.GET.next, so /?next=<anything> mints a distinct Google URL. What
    is true, and is the point, is narrower: those templates are reached from
    four routes rather than from every crawlable page, and nothing on the site
    links to them with a varying ?next=, so they are not a self-minting
    surface the way the header links were. A crawler inventing query strings
    can still produce variants; closing that would mean dropping destinations
    the gift and pledge flows depend on.
    """

    def test_signin_and_signup_hrefs_are_identical_across_pages(self):
        first = str(Client().get("/privacy/").content, 'utf-8')
        second = str(Client().get("/about/").content, 'utf-8')
        hrefs = auth_link_hrefs(first)
        self.assertEqual(hrefs, ["/accounts/superlogin/", "/accounts/register/"])
        self.assertEqual(hrefs, auth_link_hrefs(second))

    def test_signin_hrefs_do_not_vary_with_the_query_string(self):
        # A crawler appending junk (or legitimate pagination) to a page must
        # not be handed a different sign-in URL for each variant.
        plain = auth_link_hrefs(str(Client().get("/privacy/").content, 'utf-8'))
        with_query = auth_link_hrefs(str(
            Client().get("/privacy/", {"q": "sverige", "page": "2"}).content, 'utf-8'))
        self.assertEqual(plain, with_query)
        for href in plain:
            self.assertNotIn("next=", href)

    def test_current_page_is_still_carried_for_the_browser(self):
        # The "sign in and come back here" value is not lost, only moved: JS
        # promotes it into the href. Pagination state must survive, as it did
        # before (regression guard from the July #1204 work).
        from urllib.parse import quote
        r = Client().get("/privacy/", {"q": "sverige", "page": "2"})
        nexts = auth_link_nexts(str(r.content, 'utf-8'))
        self.assertEqual(len(nexts), 2)
        for value in nexts:
            self.assertEqual(value, quote("/privacy/?q=sverige&page=2", safe=''))

    def test_no_template_uses_a_multiline_hash_comment(self):
        # Django's {# ... #} syntax is single-line only: a multi-line one is not
        # a comment at all, it renders as literal text into the page. I shipped
        # that bug twice in this branch, so it is asserted structurally over the
        # template sources rather than by listing phrases to look for -- a
        # phrase list only catches the instances someone remembered to add.
        import os
        offenders = []
        roots = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'frontend', 'templates')]
        for root in roots:
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    if not name.endswith('.html'):
                        continue
                    path = os.path.join(dirpath, name)
                    with open(path, encoding='utf-8') as handle:
                        text = handle.read()
                    idx = 0
                    while True:
                        start = text.find('{#', idx)
                        if start == -1:
                            break
                        end = text.find('#}', start)
                        if end == -1:
                            offenders.append('%s: unterminated {#' % path)
                            break
                        if '\n' in text[start:end]:
                            offenders.append('%s: multi-line {# ... #} at offset %d'
                                             % (path, start))
                        idx = end + 2
        self.assertEqual(offenders, [], 'multi-line {# #} renders as visible text:\n' +
                         '\n'.join(offenders))

    def test_login_required_redirect_still_carries_next(self):
        # Django's own @login_required redirect is a flow that explicitly
        # supplies next; it is untouched and must keep working.
        r = Client().get("/accounts/password/change/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'],
                         "/accounts/superlogin/?next=/accounts/password/change/")

    def test_login_page_google_link_honours_an_incoming_next(self):
        # Landing on the login page with an explicit destination (a pledge, a
        # purchase, an @login_required bounce) must still send that
        # destination through Google sign-in.
        r = Client().get("/accounts/superlogin/", {"next": "/pledge/complete/"})
        self.assertEqual(r.status_code, 200)
        m = GOOGLE_LINK_RE.search(str(r.content, 'utf-8'))
        self.assertIsNotNone(m, "no Google sign-in link on the login page")
        # Django's urlencode filter leaves "/" unescaped, so this is the same
        # value the login page emitted before this change.
        self.assertEqual(m.group(1),
                         "/socialauth/login/google-oauth2/?next=/pledge/complete/")

    def test_login_page_google_link_is_constant_without_a_next(self):
        # With no destination the link used to echo the login page's own URL,
        # so any query string appended to the login page minted a fresh Google
        # sign-in URL. It now falls back to the constant /next/ view.
        bare = GOOGLE_LINK_RE.search(
            str(Client().get("/accounts/superlogin/").content, 'utf-8')).group(1)
        junk = GOOGLE_LINK_RE.search(str(
            Client().get("/accounts/superlogin/", {"utm": "x"}).content, 'utf-8')).group(1)
        self.assertEqual(bare, "/socialauth/login/google-oauth2/?next=/next/")
        self.assertEqual(bare, junk)

    def test_login_page_secondary_links_do_not_fan_out(self):
        # code-review finding: the "Forgot your password" / "Need an account"
        # links on the login page echoed request.get_full_path, so junk appended
        # to /accounts/superlogin/ produced a distinct registration URL, whose
        # page then fed that value into ITS Google button -- a fresh URL on the
        # expensive endpoint, two hops away. They use the constant /next/ too.
        def secondary(html):
            return re.findall(r'href="(/accounts/(?:register|password/reset)/[^"]*)"', html)
        plain = secondary(str(Client().get("/accounts/superlogin/").content, 'utf-8'))
        junk = secondary(str(
            Client().get("/accounts/superlogin/", {"utm": "1"}).content, 'utf-8'))
        self.assertTrue(plain, "no secondary links found on the login page")
        self.assertEqual(plain, junk)
        # ... while an explicit destination still propagates.
        with_next = secondary(str(
            Client().get("/accounts/superlogin/", {"next": "/pledge/x/"}).content, 'utf-8'))
        self.assertTrue(any("next=/pledge/x/" in href for href in with_next))

    def test_login_page_secondary_links_are_nofollow(self):
        html = str(Client().get("/accounts/superlogin/").content, 'utf-8')
        for tag in re.findall(r'<a [^>]*href="/accounts/(?:register|password/reset)/[^"]*"[^>]*>', html):
            self.assertIn('rel="nofollow"', tag)

    def test_sitewide_js_is_cache_busted(self):
        # The "come back here" behaviour now lives in sitewide1.js, and static
        # files are served by plain StaticFilesStorage (no content hash), so a
        # returning visitor with a cached copy would get new HTML with old JS.
        html = str(Client().get("/privacy/").content, 'utf-8')
        self.assertNotIn('src="/static/js/sitewide1.js"', html)
        self.assertRegex(html, r'src="/static/js/sitewide1\.js\?v=[^"]+"')

    def test_pledge_login_page_keeps_its_destination(self):
        # /accounts/login/pledge/ renders from_pledge.html, which passes the
        # login view's own `next` straight to Google. Unchanged by #1261.
        r = Client().get("/accounts/login/pledge/", {"next": "/pledge/complete/"})
        self.assertEqual(r.status_code, 200)
        m = GOOGLE_LINK_RE.search(str(r.content, 'utf-8'))
        self.assertIsNotNone(m, "no Google sign-in link on the pledge login page")
        self.assertIn("next=/pledge/complete/", m.group(1))


class NextCookieRedirectTests(TestCase):
    """The /next/ view redirects to a destination held in a client-writable
    cookie, so it must not become an open redirect.

    The cookie is written by JavaScript -- registration_base.html takes the
    value straight off the current URL's query string and strips only quotes
    and angle brackets -- so a crafted same-site link is enough to put an
    off-site destination in it. #1261 made /next/ the default post-auth hop
    from the login page, which turns a dormant problem into a load-bearing
    one, so the guard lands here.

    Asserted against the exact safe fallback rather than "does not contain
    the evil host", matching the style of the logout open-redirect test in
    libraryauth/tests.py: a looser check would miss a bypass that lands
    somewhere else unsafe without literally containing that string.
    """

    def _next_with_cookie(self, value):
        c = Client()
        c.cookies['next'] = value
        return c.get("/next/")

    def test_same_site_path_is_honoured(self):
        r = self._next_with_cookie("%2Fwork%2F1%2F")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], "/work/1/")

    def test_no_cookie_goes_home(self):
        r = Client().get("/next/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], "/")

    def test_absolute_offsite_url_is_rejected(self):
        r = self._next_with_cookie("https%3A%2F%2Fevil.example%2Fphish")
        self.assertEqual(r['Location'], "/")

    def test_protocol_relative_url_is_rejected(self):
        # The one the reviewer called out: registration_base.html's strip of
        # "'<> lets //evil.example through untouched.
        r = self._next_with_cookie("%2F%2Fevil.example")
        self.assertEqual(r['Location'], "/")

    def test_double_encoded_offsite_url_is_rejected(self):
        # The view unquotes twice, so validation has to happen on the fully
        # decoded value, not the raw cookie.
        r = self._next_with_cookie("%252F%252Fevil.example")
        self.assertEqual(r['Location'], "/")

    def test_double_encoded_same_site_path_still_works(self):
        # The two unquotes are not paranoia: jquery.cookie re-encodes a value
        # auth_next had already encoded, so a legitimate destination arrives
        # double-encoded. This is the test that fails if someone removes one.
        r = self._next_with_cookie("%252Fwork%252F1%252F")
        self.assertEqual(r['Location'], "/work/1/")

    def test_same_host_absolute_url_is_rejected(self):
        # Stricter than "not off-site": the cookie should only ever hold a
        # path, so an absolute URL is refused even pointing at our own host.
        # This is what makes the guard independent of request.is_secure(),
        # which is always False in production behind the TLS proxy because
        # SECURE_PROXY_SSL_HEADER is unset -- so a require_https= flag would
        # have been inert and http://testserver/work/1/ would have validated,
        # bouncing the user off TLS for that hop.
        r = self._next_with_cookie("http%3A%2F%2Ftestserver%2Fwork%2F1%2F")
        self.assertEqual(r['Location'], "/")
        r = self._next_with_cookie("https%3A%2F%2Ftestserver%2Fwork%2F1%2F")
        self.assertEqual(r['Location'], "/")

    def test_control_characters_are_rejected(self):
        # Browsers strip tabs and newlines before resolving a URL, so a value
        # that parses as a path here can resolve to something else there.
        for raw in ("%2F%09%2Fevil.example", "%2F%0A%2Fevil.example",
                    "%20%2F%2Fevil.example"):
            self.assertEqual(self._next_with_cookie(raw)['Location'], "/")

    def test_backslash_variant_is_rejected(self):
        self.assertEqual(self._next_with_cookie("%2F%5Cevil.example")['Location'], "/")

    def test_a_path_with_spaces_still_works(self):
        # Regression, and the sharpest kind: behaviour that worked BEFORE this
        # PR and that an earlier version of my own guard broke. This site has
        # free-text path routes -- /free/<path>/ for keyword facets,
        # /bypub/all/<pubname> for publisher names -- so these are real pages a
        # real user can be sitting on when they sign in. The value arrives here
        # with literal spaces, because the two unquotes decode the %20 that
        # auth_next put in. Rejecting the space sent those visitors to the home
        # page. HttpResponseRedirect re-encodes it via iri_to_uri on the way
        # out, which is what already happened before any of this.
        r = self._next_with_cookie("%252Fbypub%252Fall%252FOxford%2520University%2520Press")
        self.assertEqual(r['Location'], "/bypub/all/Oxford%20University%20Press")
        r = self._next_with_cookie("%252Ffree%252Fkw.science%2520fiction%252F")
        self.assertEqual(r['Location'], "/free/kw.science%20fiction/")

    def test_next_never_redirects_to_itself(self):
        # This view reads the cookie and redirects to it, so a cookie pointing
        # back here redirected to itself. It terminated only because the same
        # response clears the cookie, which made termination depend on the
        # delete landing -- a cookie scoped to a narrower path would loop.
        # Not hypothetical: the login page's fallback links carry ?next=/next/,
        # so this value really does reach the cookie writers.
        self.assertEqual(self._next_with_cookie("%2Fnext%2F")['Location'], "/")
        self.assertEqual(self._next_with_cookie("%2Fnext%2F%3Fx%3D1")['Location'], "/")

    def test_rejected_cookie_is_cleared_not_left_to_retry(self):
        r = self._next_with_cookie("%2F%2Fevil.example")
        self.assertEqual(r.cookies['next'].value, "")


class WelcomePageRedirectTests(TestCase):
    """The other door onto the same open redirect, closed alongside the
    server-side one.

    registration_base.html used to end the registration flow with
    `window.location.replace(saved_next)` -- navigating to the raw `next`
    cookie. The same script writes that cookie from the current URL's query
    string, stripping only "'<>, so a lure like
    /accounts/register/?next=//evil.example survives intact, and the welcome
    page (the only template carrying #link-to-next) would then carry a
    freshly-registered user off the site. Guarding frontend.views.next() did
    nothing about this path, because it never reached the server.

    The fix removes the sink: navigate to the constant, same-origin /next/ and
    let the guarded view do the redirect. These tests assert the contract of
    the served JavaScript, which is the artifact that actually runs -- a
    Django test client cannot execute it.
    """

    WELCOME_URLS = ("/accounts/superlogin/welcome/", "/accounts/login/welcome/")

    def test_welcome_page_does_not_navigate_to_the_raw_cookie(self):
        for url in self.WELCOME_URLS:
            html = str(Client().get(url).content, 'utf-8')
            self.assertNotIn("window.location.replace(saved_next)", html,
                             "%s still navigates to the unvalidated cookie" % url)

    def test_welcome_page_routes_through_the_guarded_view(self):
        for url in self.WELCOME_URLS:
            html = str(Client().get(url).content, 'utf-8')
            self.assertIn("window.location.replace('/next/')", html)

    def test_registration_complete_link_never_renders_the_cookie_value(self):
        # The third sink, found by Codex: registration_complete.html rendered
        # <a href="{{ request.COOKIES.next|urldecode }}">, a clickable off-site
        # hop fed straight from the client-writable cookie. It now points at the
        # guarded /next/ view. Behavioural, not source-level: poison the cookie
        # and assert the host cannot appear in the page at all.
        #
        # The live route is django_registration_complete, whose template
        # django_registration/registration_complete.html is a one-line
        # {% extends "registration/registration_complete.html" %} -- so the sink
        # is reachable, and this test goes through the real URL rather than
        # rendering the parent template directly.
        from django.urls import reverse
        c = Client()
        c.cookies['next'] = "https%3A%2F%2Fevil.example%2Fphish"
        html = str(c.get(reverse('django_registration_complete')).content, 'utf-8')
        self.assertNotIn("evil.example", html)
        self.assertIn('href="/next/"', html)

    def test_write_side_only_stores_a_same_site_path(self):
        # Defence in depth at the one point where a value out of the URL bar
        # becomes a stored redirect destination. Not the authoritative boundary
        # -- anyone can set a cookie without running this script -- so the three
        # read sinks stay guarded regardless. Asserted on the served JavaScript,
        # which is the artifact that runs; the guard's own behaviour over
        # encoded, plain, protocol-relative, backslash and malformed values was
        # exercised separately with node.
        for url in ("/accounts/superlogin/", "/accounts/register/"):
            html = str(Client().get(url).content, 'utf-8')
            self.assertIn("function isSameSitePath(", html)
            self.assertIn("if (isSameSitePath(next)) {", html)

    def test_hijax_writer_also_refuses_to_store_the_next_view(self):
        # The registration_base.html writer got this check; the hijax writer in
        # sitewide1.js did not, so a second Sign In click from a page whose
        # links carry ?next=/next/ overwrote a real saved destination. The read
        # guard makes that safe, not harmless -- the destination is gone.
        import os
        js = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'js', 'sitewide1.js')
        with open(js, encoding='utf-8') as handle:
            source = handle.read()
        self.assertIn("decodeNextSafely(next).indexOf('/next/') !== 0", source)

    def test_write_side_refuses_to_store_the_next_view_itself(self):
        # Mirror of test_next_never_redirects_to_itself on the write side: a
        # visitor with a real destination saved must not have it overwritten
        # by /next/ when they pass through a page whose fallback link carries
        # ?next=/next/. Asserted on the served JavaScript.
        html = str(Client().get("/accounts/superlogin/").content, 'utf-8')
        self.assertIn("decoded.indexOf('/next/') !== 0", html)

    def test_no_javascript_navigates_to_a_cookie_value_anywhere(self):
        # Broader guard: no template served to a visitor may hand a cookie
        # value straight to a navigation sink. Catches a reintroduction
        # somewhere other than the welcome page.
        import re as _re
        sink = _re.compile(r"window\.location(?:\.replace| *=)[^;]*(?:saved_next|cookie\()")
        for url in self.WELCOME_URLS + ("/accounts/superlogin/", "/accounts/register/"):
            html = str(Client().get(url).content, 'utf-8')
            self.assertIsNone(sink.search(html),
                              "a navigation sink fed from a cookie appears on %s" % url)


class GiftLoginNextTests(TestCase):
    """The gift redemption flow supplies its own ?next= (the redemption URL) and
    must be unaffected by the #1261 sign-in URL work."""

    def setUp(self):
        from datetime import timedelta
        from django.utils.timezone import now
        from regluit.core import models as core_models
        giver = User.objects.create_user('giver', 'giver@example.org', 'pass')
        giftee = User.objects.create_user('giftee', 'giftee@example.org', 'pass')
        # receive_gift only renders the login page when the giftee is an
        # established user -- i.e. joined well before the acq was created.
        User.objects.filter(pk=giftee.pk).update(date_joined=now() - timedelta(days=30))
        work = Work.objects.create(title="A Gifted Work")
        acq = core_models.Acq.objects.create(
            user=giftee, work=work, license=core_models.INDIVIDUAL,
        )
        core_models.Gift.objects.create(acq=acq, giver=giver, to='giftee@example.org')
        # a post_save hook computes the nonce, so read it back
        acq.refresh_from_db()
        self.nonce = acq.nonce

    def test_gift_google_link_points_at_the_redemption_url(self):
        r = Client().get("/receive_gift/%s/" % self.nonce)
        self.assertEqual(r.status_code, 200)
        m = GOOGLE_LINK_RE.search(str(r.content, 'utf-8'))
        self.assertIsNotNone(m, "no Google sign-in link on the gift login page")
        self.assertEqual(
            m.group(1),
            "/socialauth/login/google-oauth2/?next=/receive_gift/%s/" % self.nonce)



class CampaignRetirementTests(TestCase):
    """Pledge (REWARDS) and Buy-to-unglue campaigns are retired (#1195):
    the rights-holder UI must no longer offer them for new campaigns, while
    existing legacy campaigns must keep rendering."""

    def setUp(self):
        from regluit.core.models import RightsHolder, Claim
        self.user = User.objects.create_user('rhuser', 'rhuser@example.org', 'test')
        self.rh = RightsHolder.objects.create(
            rights_holder_name='retirement test rh', owner=self.user, approved=True
        )
        self.work = Work.objects.create(title="legacy pledge work", language='en')
        self.b2u_work = Work.objects.create(title="legacy b2u work", language='en')
        Claim.objects.create(
            work=self.work, user=self.user, status='active', rights_holder=self.rh
        )
        Claim.objects.create(
            work=self.b2u_work, user=self.user, status='active', rights_holder=self.rh
        )

    def test_open_campaign_form_offers_only_thanks(self):
        from regluit.frontend.forms import OpenCampaignForm
        from regluit.core.parameters import REWARDS, BUY2UNGLUE, THANKS
        form = OpenCampaignForm()
        self.assertEqual(
            [int(value) for value, label in form.fields['type'].choices],
            [THANKS],
        )
        # POSTs that try to force a retired type are rejected with a clean
        # form error on 'type'
        for retired_type in (REWARDS, BUY2UNGLUE):
            form = OpenCampaignForm(data={
                'name': self.work.title,
                'work': self.work.id,
                'userid': self.user.id,
                'type': retired_type,
            })
            self.assertFalse(form.is_valid())
            self.assertIn('type', form.errors)
        # a complete THANKS submission is fully valid (django-selectable's
        # multiple field takes a list of pks)
        form = OpenCampaignForm(data={
            'name': self.work.title,
            'work': self.work.id,
            'userid': self.user.id,
            'managers': [str(self.user.id)],
            'type': THANKS,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_legacy_campaigns_still_render(self):
        from datetime import datetime, timedelta
        from decimal import Decimal as D
        from django.utils.timezone import now
        from regluit.core import parameters
        from regluit.core.models import Campaign
        pledge = Campaign.objects.create(
            work=self.work,
            type=parameters.REWARDS,
            name='legacy pledge campaign',
            description='legacy pledge campaign',
            target=D('1000.00'),
            deadline=now() + timedelta(days=30),
        )
        b2u = Campaign.objects.create(
            work=self.b2u_work,
            type=parameters.BUY2UNGLUE,
            name='legacy b2u campaign',
            description='legacy b2u campaign',
            target=D('1000.00'),
            deadline=datetime(2030, 1, 1),
            cc_date_initial=datetime(2030, 1, 1),
        )
        # legacy campaigns launched before retirement carry ACTIVE status in
        # the db; retirement must not break their read-only display
        for campaign in (pledge, b2u):
            campaign.status = 'ACTIVE'
            campaign.activated = now()
            campaign.left = campaign.target
            campaign.save()
        anon_client = Client()
        for work in (self.work, self.b2u_work):
            r = anon_client.get("/work/{}/".format(work.id))
            self.assertEqual(r.status_code, 200)


class LoginDoubleSubmitGuardTests(TestCase):
    """Tests pinning the #1240 double-submit guard in place.

    The guard itself is client-side JS (static/js/sitewide1.js). Its behavior
    is exercised by a dependency-free Node test (run here when node is
    available); the Django-side tests assert the wiring that makes the guard
    effective: the login form posts to the URL the guard watches, and every
    page loads the script that carries it.
    """

    def test_login_page_wires_up_guard(self):
        r = Client().get("/accounts/superlogin/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        # base.html loads the sitewide script that contains the guard
        self.assertIn("/static/js/sitewide1.js", content)
        # the login form still posts to the action the guard is scoped to
        self.assertIn('action="/accounts/superlogin/"', content)

    def test_guard_behavior_via_node(self):
        import os
        import shutil
        import subprocess
        import unittest
        if not shutil.which("node"):
            raise unittest.SkipTest("node not available")
        test_js = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "js", "tests", "login_guard_test.js",
        )
        result = subprocess.run(
            ["node", test_js], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(
            result.returncode, 0,
            "guard behavioral tests failed:\n%s\n%s" % (result.stdout, result.stderr),
        )



from unittest import mock
from django.core.cache import cache
from regluit.frontend import views as frontend_views


class SubjectsTopListTests(TestCase):
    """/subjects/ lists only the most-used subjects, and caches the rendered list."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _subject(self, name, n_works, n_free=0):
        subject = Subject.objects.create(name=name)
        for i in range(n_works):
            work = Work.objects.create(title="%s %s" % (name, i), is_free=i < n_free)
            subject.works.add(work)
        return subject

    def _names(self, url):
        cache.clear()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # the view hands the template a callable, evaluated on a cache miss
        return [subject.name for subject in response.context['subjects']()]

    def test_limits_to_top_subjects_by_count(self):
        self._subject("Big", 3)
        self._subject("Middle", 2)
        self._subject("Small", 1)
        with mock.patch.object(frontend_views, 'SUBJECTS_LIMIT', 2):
            # the top two by count, shown alphabetically by default
            self.assertEqual(self._names("/subjects/"), ["Big", "Middle"])
            self.assertEqual(self._names("/subjects/?order=count"), ["Big", "Middle"])
            response = self.client.get("/subjects/")
        self.assertContains(response, "Only the 2 most-used keywords")
        self.assertContains(response, "Middle")
        self.assertNotContains(response, "Small")

    def test_count_order_and_name_order(self):
        self._subject("Apple", 1)
        self._subject("banana", 3)
        self._subject("Cherry", 2)
        self.assertEqual(self._names("/subjects/"), ["Apple", "banana", "Cherry"])
        self.assertEqual(self._names("/subjects/?order=count"), ["banana", "Cherry", "Apple"])

    def test_default_limit_is_100(self):
        self.assertEqual(frontend_views.SUBJECTS_LIMIT, 100)
        for i in range(101):
            Subject.objects.create(name="Subject %03d" % i).works.add(
                Work.objects.create(title="Work %03d" % i))
        self.assertEqual(len(self._names("/subjects/")), 100)
        self.assertContains(self.client.get("/subjects/"), "Only the 100 most-used keywords")

    def test_free_subset_ranks_by_free_works(self):
        self._subject("Many works, one free", 4, n_free=1)
        self._subject("Two free", 2, n_free=2)
        self._subject("None free", 5, n_free=0)
        self.assertEqual(self._names("/subjects/?subset=free&order=count"),
                         ["Two free", "Many works, one free"])
        self.assertEqual(self._names("/subjects/?subset=free"),
                         ["Many works, one free", "Two free"])
        cache.clear()
        response = self.client.get("/subjects/?subset=free")
        self.assertContains(response, "1 free out of 4")
        self.assertNotContains(response, "None free")

    def test_rendered_list_is_cached(self):
        self._subject("Cached", 1)
        with mock.patch.object(frontend_views, 'top_subjects',
                               wraps=frontend_views.top_subjects) as top:
            self.assertContains(self.client.get("/subjects/"), "Cached")
            self.assertEqual(top.call_count, 1)
            self._subject("Added later", 5)
            # a cache hit runs no subject queries and shows the cached list
            response = self.client.get("/subjects/")
            self.assertEqual(top.call_count, 1)
            self.assertNotContains(response, "Added later")
            # each subset/order combination has its own cache entry
            self.assertContains(self.client.get("/subjects/?order=count"), "Added later")
            self.assertEqual(top.call_count, 2)
            # junk parameter values share the default entry
            self.client.get("/subjects/?order=junk&subset=junk")
            self.assertEqual(top.call_count, 2)


from django.test import override_settings


@override_settings(
    ALLOWED_HOSTS=["unglue.it", "test.unglue.it", "localhost", "127.0.0.1"]
)
class RobotsTxtTests(TestCase):
    """/robots.txt is rendered from a template gated on the request host.

    The AI-crawler rules only apply on production; every other host (staging,
    dev, an IP address) must keep serving a blanket disallow so non-canonical
    copies of the site never get indexed.

    This is a ``TestCase`` rather than a ``SimpleTestCase`` even though the
    view itself touches no models: issuing the request loads the root URLconf,
    which imports a module that runs a query at import time. Under
    ``SimpleTestCase`` Django creates no test database, so that query would
    hit whatever database the settings actually point at. ``TestCase`` gets an
    isolated test database instead.
    """

    BASELINE_DISALLOWS = [
        "/accounts/",
        "/feedback/",
        "/socialauth/",
        "/search/",
        "/googlebooks/",
    ]

    # The load-shedding rules this change exists for: the expensive listing
    # and feed endpoints from #1189, excluded for the throttled crawler on
    # top of the baseline.
    CLAUDEBOT_EXTRA_DISALLOWS = [
        "/free/",
        "/bypub/",
        "/pid/",
        "/unglued/",
        "/campaigns/",
        "/api/",
    ]

    # Crawlers that collect model-training data, disallowed outright. This is
    # a content-usage decision, not a claim about their capabilities: several
    # of them do honor Crawl-delay and could be throttled instead.
    BLOCKED_AGENTS = [
        "GPTBot",
        "CCBot",
        "Bytespider",
        "Amazonbot",
        "meta-externalagent",
        "Diffbot",
    ]

    def _get(self, host):
        response = self.client.get("/robots.txt", HTTP_HOST=host)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        return response.content.decode("utf-8")

    @staticmethod
    def _parse_groups(body):
        """Return {user-agent: {"disallow": [...], "other": [...]}}.

        Consecutive ``User-agent`` lines share one group (RFC 9309 2.2.1).
        Only ``Allow``/``Disallow`` close the run of user-agent lines: an
        extension record such as ``Crawl-delay`` or ``Sitemap`` must not end
        a group (2.2.4), so it is recorded without moving the boundary.
        """
        groups = {}
        current = []
        started = False
        for raw in body.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field, value = (part.strip() for part in line.split(":", 1))
            field = field.lower()
            if field == "user-agent":
                if started:
                    current = []
                    started = False
                groups.setdefault(
                    value, {"disallow": [], "allow": [], "other": []}
                )
                current.append(value)
            elif current:
                for agent in current:
                    if field in ("disallow", "allow"):
                        groups[agent][field].append(value)
                        started = True
                    else:
                        groups[agent]["other"].append((field, value))
        return groups

    def test_parser_keeps_consecutive_user_agents_in_one_group(self):
        """The parser must not let an extension record split a group.

        Guards the guard: if Crawl-delay ended a user-agent run, two agents
        sharing one stanza would be read as separate groups and the
        precedence check below would silently stop covering the second.
        """
        groups = self._parse_groups(
            "User-agent: A\n"
            "Crawl-delay: 5\n"
            "User-agent: B\n"
            "Disallow: /x/\n"
            "\n"
            "User-agent: C\n"
            "Disallow: /\n"
        )
        self.assertEqual(set(groups), {"A", "B", "C"})
        # The load-bearing property: the Crawl-delay between the two
        # User-agent lines did not split them, so both still receive the
        # group's Disallow rule.
        self.assertEqual(groups["A"]["disallow"], ["/x/"])
        self.assertEqual(groups["B"]["disallow"], ["/x/"])
        # The extension record itself is still captured, not discarded.
        self.assertIn(("crawl-delay", "5"), groups["A"]["other"])
        # C opens a new group: a rule line has been seen since the last
        # User-agent, which is what closes the previous group.
        self.assertEqual(groups["C"]["disallow"], ["/"])

    def test_production_host_serves_baseline_and_ai_rules(self):
        body = self._get("unglue.it")
        groups = self._parse_groups(body)

        self.assertIn("*", groups)
        for path in self.BASELINE_DISALLOWS:
            self.assertIn(path, groups["*"]["disallow"])
        self.assertNotIn("/", groups["*"]["disallow"])

        # ClaudeBot is throttled, not blocked, so work pages stay crawlable --
        # but every expensive path must be excluded, since those exclusions
        # are the actual load-shedding this change delivers.
        self.assertIn("ClaudeBot", groups)
        self.assertIn(("crawl-delay", "30"), groups["ClaudeBot"]["other"])
        self.assertNotIn("/", groups["ClaudeBot"]["disallow"])
        for path in self.BASELINE_DISALLOWS + self.CLAUDEBOT_EXTRA_DISALLOWS:
            self.assertIn(
                path, groups["ClaudeBot"]["disallow"],
                "ClaudeBot no longer excludes %s" % path,
            )

        # meta-webindexer indexes for Meta AI search, so it is not blocked
        # outright, but it was the largest single source of /free/ load
        # (#1253). It gets exactly the baseline plus ClaudeBot's listing
        # exclusions -- nothing broader (work pages stay crawlable) and no
        # Allow that could re-open a path. Exact equality also catches a
        # duplicated copy of these rules.
        self.assertIn("meta-webindexer", groups)
        self.assertEqual(
            sorted(groups["meta-webindexer"]["disallow"]),
            sorted(self.BASELINE_DISALLOWS + self.CLAUDEBOT_EXTRA_DISALLOWS),
        )
        self.assertEqual(groups["meta-webindexer"]["allow"], [])
        # Exactly one Crawl-delay, of 10 seconds: the 2026-09-10 experiment
        # (see the comment in robots.txt). Check Crawl-delay specifically, so
        # other extension records (such as a Sitemap line) don't fail this.
        self.assertEqual(
            [value for field, value in groups["meta-webindexer"]["other"]
             if field == "crawl-delay"],
            ["10"],
        )

        # Every crawler selected for blocking is fully disallowed. (Not
        # every training crawler: ClaudeBot trains too and is deliberately
        # throttled instead, and content-usage opt-out tokens are out of
        # scope for this change.)
        for agent in self.BLOCKED_AGENTS:
            self.assertIn(agent, groups)
            self.assertIn(
                "/", groups[agent]["disallow"],
                "%s is named but not actually blocked" % agent,
            )

        # Exhaustive: adding or removing a group has to be a deliberate edit
        # here too, so a stanza cannot be dropped or slipped in unnoticed.
        self.assertEqual(
            set(groups),
            {"*", "ClaudeBot", "meta-webindexer"} | set(self.BLOCKED_AGENTS),
        )

        # Search-indexing and user-triggered agents must NOT have their own
        # groups, so they keep falling through to the permissive "*" group.
        # Their publishers document them as not collecting training data, so
        # blocking one outright costs discoverability. When one does cause
        # real load, exclude the expensive paths instead (see meta-webindexer).
        for agent in (
            "Googlebot",
            "PerplexityBot",
            "Perplexity-User",
            "Amzn-SearchBot",
            "OAI-SearchBot",
            "ChatGPT-User",
            "Claude-SearchBot",
            "Claude-User",
        ):
            self.assertNotIn(agent, groups)

    def test_named_groups_do_not_widen_access(self):
        """Regression guard for robots.txt group precedence.

        The ``User-agent: *`` group applies only to crawlers that match no
        named group, so a named group that is not a blanket disallow has to
        restate the baseline rules -- otherwise adding a group *grants* that
        crawler access to paths it was previously excluded from.
        """
        groups = self._parse_groups(self._get("unglue.it"))
        for agent, rules in groups.items():
            if agent == "*" or "/" in rules["disallow"]:
                continue
            for path in self.BASELINE_DISALLOWS:
                self.assertIn(
                    path, rules["disallow"],
                    "User-agent %s omits baseline rule %s; a named group that "
                    "does not restate the baseline widens that crawler's "
                    "access instead of narrowing it." % (agent, path),
                )
            # Restating a Disallow is not enough on its own: RFC 9309 gives
            # the longest match precedence, so a more specific Allow beneath
            # one of these prefixes would quietly re-open it.
            for allowed in rules["allow"]:
                for path in self.BASELINE_DISALLOWS:
                    self.assertFalse(
                        allowed.startswith(path),
                        "User-agent %s allows %s, which overrides the longer-"
                        "matching baseline rule %s and widens access."
                        % (agent, allowed, path),
                    )

    def test_non_production_hosts_disallow_everything(self):
        for host in ("test.unglue.it", "localhost", "127.0.0.1"):
            with self.subTest(host=host):
                body = self._get(host)
                groups = self._parse_groups(body)
                self.assertEqual(list(groups), ["*"])
                self.assertEqual(groups["*"]["disallow"], ["/"])
                self.assertNotIn("ClaudeBot", body)

from unittest import mock
from regluit.frontend.views import FacetedView

class FacetedDeepPageCapTests(TestCase):
    """FacetedView (/free/, /creativecommons/) 404s ?work_list= pages past its cap
    before looking up the facet or building the queryset (#1253, #1265)."""
    fixtures = ['initial_data.json', 'neuromancer.json']

    def setUp(self):
        # The fixtures have no free works, and faceted_list.html only runs
        # lazy_paginate when the list is non-empty.
        Work.objects.update(is_free=True)

    def test_pagination_still_runs(self):
        r = self.client.get("/free/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "work_list=2")
        self.assertEqual(self.client.get("/free/?work_list=2").status_code, 200)

    def test_cap_is_page_10(self):
        self.assertEqual(FacetedView.max_page, 10)

    def test_page_at_cap_is_served(self):
        for url in ("/free/", "/free/epub/", "/creativecommons/"):
            with self.subTest(url=url):
                r = self.client.get(url, {"work_list": 10})
                self.assertEqual(r.status_code, 200)

    def test_page_past_cap_is_404(self):
        for url in ("/free/", "/free/epub/", "/creativecommons/"):
            with self.subTest(url=url):
                r = self.client.get(url, {"work_list": 11})
                self.assertEqual(r.status_code, 404)

    def test_no_page_links_past_cap(self):
        # enough free works that page 10 has results and a page 11 exists
        for i in range(11 * 20):
            Work.objects.create(title="Deep work %03d" % i, language='en', is_free=True)
        r = self.client.get("/free/", {"work_list": 9})
        self.assertContains(r, "work_list=10")
        r = self.client.get("/free/", {"work_list": 10})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Deep work")
        self.assertNotContains(r, "work_list=11")

    def test_past_cap_refused_before_facet_lookup(self):
        with mock.patch("regluit.frontend.views.get_facet_object",
                        side_effect=AssertionError("facet lookup ran")):
            for url in ("/free/", "/free/epub/", "/creativecommons/"):
                with self.subTest(url=url):
                    r = self.client.get(url, {"work_list": FacetedView.max_page + 1})
                    self.assertEqual(r.status_code, 404)

    def test_junk_values_do_not_500(self):
        # Non-numbers fall back to page 1, as the paginator itself does;
        # zero and negatives are left to the paginator's own fallback.
        for value in ("abc", "", "1.5", "0", "-3", "-99999"):
            with self.subTest(value=value):
                r = self.client.get("/free/", {"work_list": value})
                self.assertEqual(r.status_code, 200)
        r = self.client.get("/free/", {"work_list": "9" * 30})
        self.assertEqual(r.status_code, 404)


class WorkPageKeywordLinkTests(TestCase):
    """A book page lists the book's subjects in the Explore box, each linked to
    that subject's list of free books. The full keyword list in the More... tab
    is the editing tool and is shown only to people who can edit. (#1278)"""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        self.work = Work.objects.create(title="Keyworded work", language='en', is_free=True)
        other = Work.objects.create(title="Another free work", language='en', is_free=True)
        # num_free is precomputed on the site; set it here as the nightly count would
        for name in ("Fiction", "Science Fiction", "What next? 100% #1", "Art/Design"):
            subject = Subject.objects.create(name=name, num_free=2)
            subject.works.add(self.work, other)
        Subject.objects.create(name="Only here", num_free=1).works.add(self.work)
        Subject.objects.create(name="Hidden topic", num_free=5, is_visible=False).works.add(self.work)

    def test_subjects_link_to_their_lists_with_counts(self):
        response = self.client.get("/work/%s/" % self.work.id)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            '<li itemprop="keywords"><a href="/free/kw.Fiction/"><span>Fiction</span></a> (2)</li>')
        self.assertContains(
            response, '<a href="/free/kw.Science%20Fiction/"><span>Science Fiction</span></a> (2)')
        # characters that would otherwise end or corrupt the URL are escaped
        self.assertContains(response, '<a href="/free/kw.What%20next%3F%20100%25%20%231/">')

    def test_subject_with_a_slash_is_shown_without_a_link(self):
        # the list URL cannot carry a slash (the path is split on it), so a
        # link would be broken; the subject is still listed with its count
        response = self.client.get("/work/%s/" % self.work.id)
        self.assertContains(response, '<li itemprop="keywords"><span>Art/Design</span> (2)</li>')
        self.assertNotContains(response, 'kw.Art')

    def test_subjects_that_lead_nowhere_are_not_listed_for_readers(self):
        # one free book only (this one), or marked not visible
        response = self.client.get("/work/%s/" % self.work.id)
        self.assertNotContains(response, "Only here")
        self.assertNotContains(response, "Hidden topic")

    def test_readers_do_not_see_the_keyword_editing_list(self):
        response = self.client.get("/work/%s/" % self.work.id)
        self.assertNotContains(response, '<h4>Keywords</h4>')
        self.assertNotContains(response, 'id="kw_list"')

    def test_staff_see_every_keyword_with_its_delete_button(self):
        User.objects.create_superuser('kwstaff', 'kwstaff@example.org', 'test')
        self.client.login(username='kwstaff', password='test')
        response = self.client.get("/work/%s/" % self.work.id)
        self.assertContains(response, '<h4>Keywords</h4>')
        self.assertContains(response, 'id="kw_list"')
        for name in ("Fiction", "Art/Design", "Only here", "Hidden topic"):
            self.assertContains(response, '<span class="deletebutton" data="%s">x</span>' % name)
        # the Explore box is still there for staff
        self.assertContains(response, '<a href="/free/kw.Fiction/"><span>Fiction</span></a> (2)')

    def test_a_linked_subject_page_loads_and_lists_the_work(self):
        response = self.client.get("/free/kw.Science%20Fiction/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keyworded work")


class SearchWithoutTurnstileTokenTests(TestCase):
    """A search link with no Turnstile token (the author links on book pages)
    shows unglue.it's own matches and never calls Google Books. (#1276)"""

    def setUp(self):
        from regluit.core.models import Author, Edition, Relation, Relator
        # Edition.add_author relies on the 'aut' relation having id 1, which
        # holds on a real database but not in every test transaction.
        author = Author.objects.create(name="Ada Linked")
        aut = Relation.objects.get_or_create(code='aut')[0]
        self.work = Work.objects.create(title="Linked Author Book", is_free=True)
        not_free = Work.objects.create(title="Linked Author Unfree", is_free=False)
        for work in (self.work, not_free):
            edition = Edition.objects.create(title=work.title, work=work)
            Relator.objects.create(author=author, edition=edition, relation=aut)

    def _search(self, query, validated):
        with mock.patch.object(frontend_views.cf, 'validate', return_value=validated), \
                mock.patch.object(frontend_views, 'gluejar_search', return_value=[]) as google:
            response = self.client.get("/search/?" + query)
        self.assertEqual(response.status_code, 200)
        return response, google

    def test_author_link_without_token_shows_our_works(self):
        response, google = self._search("q=Ada%20Linked&ty=au", validated=False)
        self.assertEqual([w.id for w in response.context['ug_works']], [self.work.id])
        self.assertContains(response, "Linked Author Book")
        self.assertNotContains(response, "Linked Author Unfree")
        google.assert_not_called()

    def test_title_search_without_token_shows_our_works(self):
        response, google = self._search("q=Linked%20Author%20B", validated=False)
        self.assertEqual([w.id for w in response.context['ug_works']], [self.work.id])
        google.assert_not_called()

    def test_title_search_with_an_emoji_is_a_normal_page(self):
        # The title column is utf8mb3, which MySQL will not compare with a
        # four-byte character: the lookup raised error 1267 and the visitor
        # got a 500. (#1288)
        response, google = self._search("q=%F0%9F%93%99%20Linked%20Author%20B", validated=False)
        self.assertEqual([w.id for w in response.context['ug_works']], [self.work.id])

    def test_author_search_with_an_emoji_is_a_normal_page(self):
        response, google = self._search("q=Ada%20Linked%20%F0%9F%93%99&ty=au", validated=False)
        self.assertEqual([w.id for w in response.context['ug_works']], [self.work.id])

    def test_a_search_that_is_only_an_emoji_is_an_empty_page(self):
        response, google = self._search("q=%F0%9F%93%99%F0%9F%93%99", validated=False)
        self.assertEqual(list(response.context['ug_works']), [])

    def test_no_match_without_token_is_an_empty_page_and_no_google(self):
        response, google = self._search("q=Nobody%20Here&ty=au", validated=False)
        self.assertEqual(list(response.context['ug_works']), [])
        self.assertEqual(list(response.context['results']), [])
        google.assert_not_called()

    def test_without_token_the_query_is_not_stored_in_the_session(self):
        self._search("q=Ada%20Linked&ty=au", validated=False)
        self.assertNotIn('q', self.client.session)

    def test_with_token_google_is_still_asked(self):
        response, google = self._search("q=Ada%20Linked&ty=au", validated=True)
        self.assertEqual([w.id for w in response.context['ug_works']], [self.work.id])
        google.assert_called_once()
        self.assertEqual(self.client.session.get('q'), "Ada Linked")



from django.urls import reverse
from regluit.core.models import Edition, Ebook


class DownloadEbookCdnTests(TestCase):
    """download_ebook sends our own stored files through the CDN only when
    EBOOK_CDN_BASE is set; every other address passes through unchanged."""

    OWN = 'https://tieulgnu.s3.amazonaws.com/ebf/425c23a45e66403caf5a23ec880d28ee.epub'

    def setUp(self):
        work = Work.objects.create(title="CDN Test Book")
        self.edition = Edition.objects.create(title=work.title, work=work)

    def _redirect_for(self, url):
        ebook = Ebook.objects.create(edition=self.edition, url=url, format='epub', provider='Unglue.it')
        response = self.client.get(reverse('download_ebook', args=[ebook.id]), REMOTE_ADDR='127.0.0.1')
        self.assertEqual(response.status_code, 302)
        return response['Location']

    @override_settings(EBOOK_CDN_BASE='')
    def test_setting_empty_keeps_s3(self):
        self.assertEqual(self._redirect_for(self.OWN), self.OWN)

    @override_settings(EBOOK_CDN_BASE='https://files.unglue.it/')
    def test_own_file_goes_through_cdn(self):
        self.assertEqual(self._redirect_for(self.OWN),
                         'https://files.unglue.it/ebf/425c23a45e66403caf5a23ec880d28ee.epub')

    @override_settings(EBOOK_CDN_BASE='https://files.unglue.it')
    def test_base_without_trailing_slash(self):
        self.assertEqual(self._redirect_for(self.OWN),
                         'https://files.unglue.it/ebf/425c23a45e66403caf5a23ec880d28ee.epub')

    @override_settings(EBOOK_CDN_BASE='https://files.unglue.it/')
    def test_outside_hosts_unchanged(self):
        for url in ('https://library.oapen.org/bitstream/handle/20.500.12657/1/book.pdf',
                    'https://unglueit-files.s3.amazonaws.com/ebf/old.epub',
                    'https://tieulgnu.s3.amazonaws.com.example.org/ebf/x.epub'):
            self.assertEqual(self._redirect_for(url), url)

    @override_settings(EBOOK_CDN_BASE='https://files.unglue.it/')
    def test_query_string_kept(self):
        self.assertEqual(self._redirect_for(self.OWN + '?v=2'),
                         'https://files.unglue.it/ebf/425c23a45e66403caf5a23ec880d28ee.epub?v=2')
