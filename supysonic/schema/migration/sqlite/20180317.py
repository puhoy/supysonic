import argparse
import hashlib
import sqlite3
import uuid

try:
    bytes = buffer
except:
    pass

parser = argparse.ArgumentParser()
parser.add_argument('dbfile', help = 'Path to the SQLite database file')
args = parser.parse_args()

def process_table(connection, table):
    c = connection.cursor()

    c.execute('ALTER TABLE {0} ADD COLUMN path_hash BLOB NOT NULL DEFAULT ROWID'.format(table))

    hashes = dict()
    for row in c.execute('SELECT path FROM {0}'.format(table)):
        hashes[row[0]] = hashlib.sha1(row[0].encode('utf-8')).digest()
    c.executemany('UPDATE {0} SET path_hash=? WHERE path=?'.format(table), [ (bytes(h), p) for p, h in hashes.items() ])

    c.execute('CREATE UNIQUE INDEX index_{0}_path ON {0}(path_hash)'.format(table))

with sqlite3.connect(args.dbfile) as conn:
    process_table(conn, 'folder')
    process_table(conn, 'track')
    conn.cursor().execute('VACUUM')

