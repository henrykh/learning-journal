from lettuce import *
from journal import *
import datetime
import os
from contextlib import closing

from journal import connect_db


world.DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id serial PRIMARY KEY,
    title VARCHAR (127) NOT NULL,
    text TEXT NOT NULL,
    created TIMESTAMP NOT NULL
)
"""
INSERT_ENTRY = """INSERT INTO entries (title, text, created) VALUES (%s, %s, %s)
"""

TEST_DSN = 'dbname=test_learning_journal user=henryhowes'
INPUT_BTN = '<input type="submit" value="Share" name="Share"/>'
READ_ENTRY = """SELECT * FROM entries
"""
RETRIEVE_BY_TITLE = """SELECT * FROM entries WHERE title=%s
"""

settings = {'db': TEST_DSN}


@world.absorb
def run_query(db, query, params=(), get_results=True):
    '''Run database SQL query.'''
    cursor = db.cursor()
    cursor.execute(query, params)
    db.commit()
    results = None
    if get_results:
        results = cursor.fetchall()
    return results


@before.each_scenario
def init_db(scenario):
    '''Initialize a test database for the tests.'''
    with closing(connect_db(settings)) as db:
        db.cursor().execute(world.DB_SCHEMA)
        db.commit()


@after.each_scenario
def clear_db(scenario):
    ''' Clear the test database. '''
    with closing(connect_db(settings)) as db:
        db.cursor().execute("DROP TABLE entries")
        db.commit()


@before.each_scenario
def app(scenario):
    ''' Start the web app for the tests. '''
    from journal import main
    from webtest import TestApp
    os.environ['DATABASE_URL'] = TEST_DSN
    app = main()

    world.app = TestApp(app)


@world.absorb
def add_entry(app, title, body):
    ''' Provide a single entry in the database. '''
    now = datetime.datetime.utcnow()
    expected = (title, body, now)
    with closing(connect_db(settings)) as db:
        world.run_query(db, INSERT_ENTRY, expected, False)
        db.commit()

    return expected


@world.absorb
def login_helper(username, password, app):
    '''Encapsulate app login for reuse in tests.
    Accept all status codes so that we can make assertions in tests
    '''
    login_data = {'username': username, 'password': password}
    return app.post('/login', params=login_data, status='*')


@step('that I want to see detail for post (\d+)')
def the_post(step, id):
    ''' Get the post id. '''
    world.number = int(id)


@step('when I enter the url /detail/(\d+)')
def test_detail_listing(step, id):
    ''' Get the entry values. '''
    # Add a entyr into the database for testing.
    world.entry = world.add_entry(world.app, 'Test Title', 'Test Text')
    world.response = world.app.get('/detail/{}'.format(id))


@step('Then I see the detail page and the content of that post')
def detial_compare(step):
    ''' Check if we can see the detail page if it contains the data. '''
    assert world.response.status_code == 200

    actual = world.response.body
    for expected in world.entry[:2]:
        assert expected in actual


@step('that I want to edit post (\d+)')
def the_edit(step, id):
    ''' Get the post id. '''
    world.number = int(id)


@step('when I enter the url /editview/(\d+)')
def test_edit_listing(step, id):
    ''' Get the entry values. '''
    # Add a entry into the database to edit for testing.
    world.entry = world.add_entry(world.app, "Test Title", "Test Text")
    world.entry_data = {
        'title': 'Hello there',
        'text': 'This is a post',
    }

    username, password = ('admin', 'secret')
    login_helper(username, password, world.app)

    world.response_post = world.app.post(
        '/editview/{}'.format(id), params=world.entry_data, status='3*')
    world.response_get = world.app.get('/detail/{}'.format(id))


@step('Then I can see the new edit page and edit the entry')
def edit_compare(step):
    ''' Check if we can see the edit page if it contains the new data. '''
    assert world.response_get.status_code == 200
    world.entry_data
    actual = world.response_get.body
    for expected in world.entry_data:
        assert world.entry_data[expected] in actual


@step("that I use markdown syntax in my post")
def markdown(step):
    ''' Add an entry with markdown to the database for testing. '''
    world.markdown_post = world.add_entry(
        world.app,
        'Test Markdown Title', '#Test Text\n##Test H2\n*list item\n*list item 2')


@step("When I view the markdown post")
def add_post_with_markdown(step):
    ''' Get the the body of the detail page. '''
    world.markdown_response = world.app.get('/detail/{}'.format(1))


@step("Then markdown in the post will be rendered properly")
def test_markdown_renders(step):
    ''' Check for the html that indicates the markdown was rendered. '''
    assert "<h1>Test Text</h1>" in world.markdown_response.body


@step("that I use backticks to denote a code block in my post")
def add_post_with_backticks(step):
    ''' Add an entry with a code block to the database for testing. '''
    world.markdown_colorized_post = world.add_entry(
        world.app, 'Test Color Syntax Title', "```pyton\n   print test\n```")


@step("When I view the color post")
def get_color_post(step):
    ''' Get the the body of the detail page. '''
    world.color_response = world.app.get('/detail/{}'.format(1))


@step("Then the code in that block will be colorized")
def check_color(step):
    ''' Check for the html that indicates the code block was rendered. '''
    assert 'class="codehilite"' in world.color_response.body
