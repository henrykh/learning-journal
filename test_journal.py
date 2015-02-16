# -*- coding: utf-8 -*-
from contextlib import closing
from pyramid import testing
import pytest
import os

from journal import connect_db
from journal import DB_SCHEMA

import datetime
from journal import INSERT_ENTRY

from cryptacular.bcrypt import BCRYPTPasswordManager
from webtest import AppError
import unittest
import markdown

TEST_DSN = 'dbname=test_learning_journal user=henryhowes'
INPUT_BTN = '<input type="submit" value="Share" name="Share"/>'
READ_ENTRY = """SELECT * FROM entries
"""


def init_db(settings):
    with closing(connect_db(settings)) as db:
        db.cursor().execute(DB_SCHEMA)
        db.commit()


def clear_db(settings):
    with closing(connect_db(settings)) as db:
        db.cursor().execute("DROP TABLE entries")
        db.commit()


def clear_entries(settings):
    with closing(connect_db(settings)) as db:
        db.cursor().execute("DELETE FROM entries")
        db.commit()


def run_query(db, query, params=(), get_results=True):
    cursor = db.cursor()
    cursor.execute(query, params)
    db.commit()
    results = None
    if get_results:
        results = cursor.fetchall()
    return results


@pytest.fixture(scope='session')
def db(request):
    """set up and tear down a database"""
    settings = {'db': TEST_DSN}
    init_db(settings)

    def cleanup():
        clear_db(settings)

    request.addfinalizer(cleanup)

    return settings


@pytest.yield_fixture(scope='function')
def req_context(db, request):
    """mock a request with a database attached"""
    settings = db
    req = testing.DummyRequest()
    with closing(connect_db(settings)) as db:
        req.db = db
        req.exception = None
        yield req

        # after a test has run, we clear out entries for isolation
        clear_entries(settings)


@pytest.fixture(scope='function')
def app(db, request):
    from journal import main
    from webtest import TestApp
    os.environ['DATABASE_URL'] = TEST_DSN
    app = main()

    def cleanup():
        settings = {'db': TEST_DSN}
        clear_entries(settings)

    request.addfinalizer(cleanup)

    return TestApp(app)


@pytest.fixture(scope='function')
def entry(db, request):
    """provide a single entry in the database"""
    settings = db
    now = datetime.datetime.utcnow()
    expected = ('Test Title', 'Test Text', now)
    with closing(connect_db(settings)) as db:
        run_query(db, INSERT_ENTRY, expected, False)
        db.commit()

    def cleanup():
        clear_entries(settings)

    request.addfinalizer(cleanup)

    return expected


@pytest.fixture(scope='function')
def auth_req(request):
    manager = BCRYPTPasswordManager()
    settings = {
        'auth.username': 'admin',
        'auth.password': manager.encode('secret'),
    }
    testing.setUp(settings=settings)
    req = testing.DummyRequest()

    def cleanup():
        testing.tearDown()

    request.addfinalizer(cleanup)

    return req


def test_write_entry(req_context):
    from journal import write_entry
    fields = ('title', 'text')
    expected = ('Test Title', 'Test Text')
    req_context.params = dict(zip(fields, expected))

    # assert that there are no entries when we start
    rows = run_query(req_context.db, "SELECT * FROM entries")
    assert len(rows) == 0

    write_entry(req_context)
    # manually commit so we can see the entry on query
    req_context.db.commit()

    rows = run_query(req_context.db, "SELECT title, text FROM entries")
    assert len(rows) == 1
    actual = rows[0]
    for idx, val in enumerate(expected):
        assert val == actual[idx]


def test_write_entry_without_text(req_context):
    from journal import write_entry
    req_context.params = {'title': 'Test Title'}

    # test whether passing a null value throws an integrity error
    with pytest.raises(BaseException):
        write_entry(req_context)
    req_context.db.commit()


def test_read_entries_empty(req_context):
    # call the function under test
    from journal import read_entries
    result = read_entries(req_context)
    # make assertions about the result
    assert 'entries' in result
    assert len(result['entries']) == 0


def test_read_entries(req_context):
    # prepare data for testing
    now = datetime.datetime.utcnow()
    expected = ('Test Title', 'Test Text', now)
    run_query(req_context.db, INSERT_ENTRY, expected, False)
    # call the function under test
    from journal import read_entries
    result = read_entries(req_context)
    # make assertions about the result
    assert 'entries' in result
    assert len(result['entries']) == 1
    for entry in result['entries']:
        assert expected[0] == entry['title']
        assert expected[1] == entry['text']
        for key in 'id', 'created':
            assert key in entry


def test_read_entries_ordered(req_context):
    # prepare data for testing
    now = datetime.datetime.utcnow()
    later = datetime.datetime.utcnow()
    latest = datetime.datetime.utcnow()

    first = ('Test Title1', 'Test Text1', now)
    second = ('Test Title2', 'Test Text2', later)
    third = ('Test Title3', 'Test Text3', latest)
    ordered = [third, second, first]

    run_query(req_context.db, INSERT_ENTRY, first, False)
    run_query(req_context.db, INSERT_ENTRY, second, False)
    run_query(req_context.db, INSERT_ENTRY, third, False)

    # call the function under test
    from journal import read_entries
    result = read_entries(req_context)
    # make assertions about the result
    assert 'entries' in result
    assert len(result['entries']) == 3
    for idx, entry in enumerate(result['entries']):
        assert ordered[idx][2] == entry['created']


def test_empty_listing(app):
    response = app.get('/')
    assert response.status_code == 200
    actual = response.body
    expected = 'No entries here so far'
    assert expected in actual


def test_listing(app, entry):
    response = app.get('/')
    assert response.status_code == 200
    actual = response.body
    for expected in entry[:2]:
        assert expected in actual


def test_post_to_add_view(app):
    entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }
    response = app.post('/new', params=entry_data, status='3*')
    redirected = response.follow()
    actual = redirected.body
    for expected in entry_data.values():
        assert expected in actual


# tests whether sending a get request fails
def test_post_to_add_view_get(app):
    entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }
    with pytest.raises(BaseException) as excinfo:
        response = app.get('/new', params=entry_data, status='3*')
        redirected = response.follow()
        actual = redirected.body
        for expected in entry_data.values():
            assert expected in actual

    assert 'Bad response: 404 Not Found' in str(excinfo.value)


def test_post_to_add_view_unauthorized(app):
    entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }

    with pytest.raises(AppError):
        app.post('/new', params=entry_data, status='3*')


def test_post_to_edit_view(app, entry, req_context):
    entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }
    username, password = ('admin', 'secret')
    login_helper(username, password, app)

    item = run_query(req_context.db, READ_ENTRY)

    response = app.post('/edit/{}'.format(item[0][0]), params=entry_data, status='3*')
    redirected = response.follow()
    actual = redirected.body
    for expected in entry_data.values():
        assert expected in actual


def test_post_to_edit_view_unauthorized(app, entry, req_context):
    entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }

    username, password = ('admin', 'wrong')
    login_helper(username, password, app)

    item = run_query(req_context.db, READ_ENTRY)

    with pytest.raises(AppError):
        app.post('/edit/{}'.format(item[0][0]), params=entry_data, status='3*')


def test_do_login_success(auth_req):
    from journal import do_login
    auth_req.params = {'username': 'admin', 'password': 'secret'}
    assert do_login(auth_req)


def test_do_login_bad_pass(auth_req):
    from journal import do_login
    auth_req.params = {'username': 'admin', 'password': 'wrong'}
    assert not do_login(auth_req)


def test_do_login_bad_user(auth_req):
    from journal import do_login
    auth_req.params = {'username': 'bad', 'password': 'secret'}
    assert not do_login(auth_req)


def test_do_login_missing_params(auth_req):
    from journal import do_login
    for params in ({'username': 'admin'}, {'password': 'secret'}):
        auth_req.params = params
        with pytest.raises(ValueError):
            do_login(auth_req)


def login_helper(username, password, app):
    """encapsulate app login for reuse in tests

    Accept all status codes so that we can make assertions in tests
    """
    login_data = {'username': username, 'password': password}
    return app.post('/login', params=login_data, status='*')


def test_start_as_anonymous(app):
    response = app.get('/', status=200)
    actual = response.body
    assert INPUT_BTN not in actual


def test_login_success(app):
    username, password = ('admin', 'secret')
    redirect = login_helper(username, password, app)
    assert redirect.status_code == 302
    response = redirect.follow()
    assert response.status_code == 200
    actual = response.body
    assert INPUT_BTN in actual


def test_login_fails(app):
    username, password = ('admin', 'wrong')
    response = login_helper(username, password, app)
    assert response.status_code == 200
    actual = response.body
    assert "Login Failed" in actual
    assert INPUT_BTN not in actual


def test_logout(app):
    test_login_success(app)
    redirect = app.get('/logout', status="3*")
    response = redirect.follow()
    assert response.status_code == 200
    actual = response.body
    assert INPUT_BTN not in actual


class TestCodeHilite(unittest.TestCase):

    def test_exists(self):
        self.pygexists = True
        try:
            import pygments
        except ImportError:
            self.pygexists = False

    def test_codehilite(self):

        text = '\t# This should look like a comment'
        md = markdown.Markdown(extentions=['codehilite', 'fenced_code'])
        self.assertTrue(md.convert(text).startswith('<div class="codehilite"><pre>'))
