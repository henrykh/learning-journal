# -*- coding: utf-8 -*-

import psycopg2
import os
import logging
import datetime
from pyramid.config import Configurator
from pyramid.events import NewRequest, subscriber
from pyramid.session import SignedCookieSessionFactory
from pyramid.view import view_config
from waitress import serve
from contextlib import closing


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id serial PRIMARY KEY,
    title VARCHAR (127) NOT NULL,
    text TEXT NOT NULL,
    created TIMESTAMP NOT NULL
)
"""

INSERT_ENTRY = """
INSERT INTO entries (title, text, created) VALUES (%s, %s, %s)
"""

DB_ENTRIES_LIST = """
SELECT id, title, text, created FROM entries ORDER BY created DESC
"""

logging.basicConfig()
log = logging.getLogger(__file__)


@view_config(route_name='home', renderer='string')
def home(request):
    return "Hello World"

def connect_db(settings):
    """Return a connection to the configured database"""
    return psycopg2.connect(settings['db'])

def init_db():
    """Create database dables defined by DB_SCHEMA

    Warning: This function will not update existing table definitions
    """
    settings = {}
    settings['db'] = os.environ.get(
        'DATABASE_URL', 'dbname=learning_journal user=henryhowes'
    )
    with closing(connect_db(settings)) as db:
        db.cursor().execute(DB_SCHEMA)
        db.commit()

@subscriber(NewRequest)
def open_connection(event):
    request = event.request
    settings = request.registry.settings
    request.db = connect_db(settings)
    request.add_finished_callback(close_connection)

def close_connection(request):
    """close the database connection for this request

    If there has been an error in the processing of the request, abort any
    open transactions.
    """
    db = getattr(request, 'db', None)
    if db is not None:
        if request.exception is not None:
            db.rollback()
        else:
            db.commit()
        request.db.close()


def main():
    """Create a configured wsgi app"""
    settings = {}
    settings['reload_all'] = os.environ.get('DEBUG', True)
    settings['debug_all'] = os.environ.get('DEBUG', True)
    settings['db'] = os.environ.get(
    'DATABASE_URL', 'dbname=learning_journal user=henryhowes'
    )
    # secret value for session signing:
    secret = os.environ.get('JOURNAL_SESSION_SECRET', 'itsaseekrit')
    session_factory = SignedCookieSessionFactory(secret)
    # configuration setup
    config = Configurator(
        settings=settings,
        session_factory=session_factory
    )
    config.add_route('home', '/')
    config.scan()
    app = config.make_wsgi_app()
    return app


if __name__ == '__main__':
    app = main()
    port = os.environ.get('PORT', 5000)
    serve(app, host='0.0.0.0', port=port)


def read_entries(request):
    """return a list of all entries as dicts"""
    cursor = request.db.cursor()
    cursor.execute(DB_ENTRIES_LIST)
    keys = ('id', 'title', 'text', 'created')
    entries = [dict(zip(keys, row)) for row in cursor.fetchall()]
    return {'entries': entries}


def write_entry(request):
    """write a single entry to the database"""
    title = request.params.get('title', None)
    text = request.params.get('text', None)
    created = datetime.datetime.utcnow()
    request.db.cursor().execute(INSERT_ENTRY, [title, text, created])
