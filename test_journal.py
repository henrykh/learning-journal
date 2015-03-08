# -*- coding: utf-8 -*-
from contextlib import closing
from pyramid import testing
import pytest
from journal import connect_db
from journal import DB_SCHEMA
import datetime
from journal import INSERT_ENTRY
import os
from cryptacular.bcrypt import BCRYPTPasswordManager
from webtest import AppError

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


def test_detail_listing(app, entry, req_context):
    item = run_query(req_context.db, READ_ENTRY)
    response = app.get('/detail/{}'.format(item[0][0]))
    assert response.status_code == 200
    actual = response.body
    for expected in entry[:2]:
        assert expected in actual


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
        assert '<p>{}</p>'.format(expected[1]) == entry['text']
        for key in 'id', 'created':
            assert key in entry


def test_read_entry(req_context):
    # prepare data for testing
    now = datetime.datetime.utcnow()
    expected = ('Test Title', 'Test Text', now)
    run_query(req_context.db, INSERT_ENTRY, expected, False)
    item = run_query(req_context.db, READ_ENTRY)
    req_context.matchdict = {'id': item[0][0]}
    from journal import read_entry
    result = read_entry(req_context)
    # make assertions about the result

    assert 'entry' in result
    assert len(result['entry']) == 4

    assert expected[0] == result['entry']['title']
    assert '<p>{}</p>'.format(expected[1]) == result['entry']['text']
    for key in 'id', 'created':
        assert key in result['entry']


def test_write_entry(req_context):
    from journal import write_entry
    fields = ('title', 'text')
    expected = ('Test Title', 'Test Text')
    req_context.params = dict(zip(fields, expected))

    # assert that there are no entries when we start
    rows = run_query(req_context.db, READ_ENTRY)
    assert len(rows) == 0

    write_entry(req_context)
    # manually commit so we can see the entry on query
    req_context.db.commit()

    rows = run_query(req_context.db, "SELECT title, text FROM entries")
    assert len(rows) == 1
    actual = rows[0]
    for idx, val in enumerate(expected):
        assert val == actual[idx]


def test_edit_entry(req_context):
    from journal import edit_entry
    from journal import write_entry

    fields = ('title', 'text', 'id')
    original = ('Test Title', 'Test Text')
    req_context.params = dict(zip(fields, original))
    write_entry(req_context)
    req_context.db.commit()

    rows = run_query(req_context.db, READ_ENTRY)
    assert len(rows) == 1
    actual = rows[0][1:3]
    for idx, val in enumerate(original):
        assert val == actual[idx]
    # req_context.matchdict = {'id': rows[0][0]}

    expected = ('New Title', 'New Text', rows[0][0])
    req_context.params = dict(zip(fields, expected))
    edit_entry(req_context)
    req_context.db.commit()

    rows = run_query(req_context.db, "SELECT title, text FROM entries")
    assert len(rows) == 1
    actual = rows[0]
    for idx, val in enumerate(expected[0:2]):
        assert val == actual[idx]

# Obsolete with ajax

# def test_post_to_add_view(app):
#     entry_data = {
#         'title': 'Hello there',
#         'text': 'This is a post',
#     }
#     username, password = ('admin', 'secret')
#     login_helper(username, password, app)
#     response = app.post('/add', params=entry_data, status='3*')
#     redirected = response.follow()
#     actual = redirected.body
#     for expected in entry_data.values():
#         assert expected in actual


def test_post_to_add_view_unauthorized(app):
    entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }

    with pytest.raises(AppError):
        app.post('/add', params=entry_data, status='3*')

# Obsolete with ajax

# def test_post_to_edit_view(app, entry, req_context):
#     entry_data = {
#         'title': 'Hello there',
#         'text': 'This is a post',
#     }
#     username, password = ('admin', 'secret')
#     login_helper(username, password, app)

#     item = run_query(req_context.db, READ_ENTRY)

#     response = app.post('/editview/{}'.format(
#         item[0][0]), params=entry_data, status='3*')
#     redirected = response.follow()
#     actual = redirected.body
#     for expected in entry_data.values():
#         assert expected in actual


def test_post_to_edit_view_unauthorized(app, entry, req_context):
    entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }

    username, password = ('admin', 'wrong')
    login_helper(username, password, app)

    item = run_query(req_context.db, READ_ENTRY)

    with pytest.raises(AppError):
        app.post('/editview/{}'.format(
            item[0][0]), params=entry_data, status='3*')


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
    # re-use existing code to ensure we are logged in when we begin
    test_login_success(app)
    redirect = app.get('/logout', status="3*")
    response = redirect.follow()
    assert response.status_code == 200
    actual = response.body
    assert INPUT_BTN not in actual

# These tests don't work with ajax

# def test_post_with_markdown(app):
#     entry_data = {
#         'title': 'Hello there',
#         'text': '###Header',
#     }
#     username, password = ('admin', 'secret')
#     login_helper(username, password, app)
#     response = app.post('/add', params=entry_data, status='3*')
#     redirected = response.follow()
#     actual = redirected.body
#     assert '<h3>Header</h3>' in actual


# def test_post_with_codeblock(app):
#     entry_data = {
#         'title': 'Hello there',
#         'text': '```python\nfor i in list:\nx = y**2\nprint(x)\n```',
#     }
#     username, password = ('admin', 'secret')
#     login_helper(username, password, app)
#     response = app.post('/add', params=entry_data, status='3*')
#     redirected = response.follow()
#     actual = redirected.body
#     assert '<div class="codehilite"><pre>' in actual
