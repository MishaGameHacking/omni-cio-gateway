import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('repair',Path(__file__).with_name('repair_owner57_database.py'))
repair=importlib.util.module_from_spec(spec);spec.loader.exec_module(repair)

class DatabaseRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.db=self.root/'db.sqlite3';self.backup=self.root/'before.sqlite3'
        with sqlite3.connect(self.db) as db:
            db.executescript("""CREATE TABLE owner_password_credentials(singleton,user_id,configured_at,updated_at,scheme,salt,password_hash);
                INSERT INTO owner_password_credentials VALUES(1,1,100,100,'synthetic','salt-fixture','hash-fixture');
                CREATE TABLE installation_owner(singleton,telegram_sub,policy_version);
                INSERT INTO installation_owner VALUES(1,'synthetic-owner','fixture');
                CREATE TABLE sessions(id PRIMARY KEY);INSERT INTO sessions VALUES(1);
                CREATE TABLE snapshots(id INTEGER PRIMARY KEY,value TEXT);INSERT INTO snapshots VALUES(1,'original');""")

    def test_backup_and_credentials_preserved(self):
        result=repair.configure(self.db,self.backup)
        self.assertTrue(result['database_rows_preserved'])
        with sqlite3.connect(self.db) as actual,sqlite3.connect(self.backup) as backup:
            self.assertEqual(actual.execute('PRAGMA journal_mode').fetchone()[0],'wal')
            self.assertEqual(actual.execute('SELECT * FROM owner_password_credentials').fetchall(),backup.execute('SELECT * FROM owner_password_credentials').fetchall())
            self.assertEqual(repair.inventory(actual),repair.inventory(backup))

    def test_reader_no_longer_blocks_login_write(self):
        repair.configure(self.db,self.backup)
        reader=sqlite3.connect(self.db);self.addCleanup(reader.close)
        writer=sqlite3.connect(self.db,timeout=.1);self.addCleanup(writer.close)
        reader.execute('BEGIN');self.assertEqual(reader.execute('SELECT count(*) FROM sessions').fetchone()[0],1)
        writer.execute('BEGIN IMMEDIATE');writer.execute('INSERT INTO sessions VALUES(2)');writer.commit()
        self.assertEqual(reader.execute('SELECT count(*) FROM sessions').fetchone()[0],1)
        reader.rollback()
        self.assertEqual(reader.execute('SELECT count(*) FROM sessions').fetchone()[0],2)

    def test_other_writer_still_requires_bounded_wait(self):
        repair.configure(self.db,self.backup)
        writer=sqlite3.connect(self.db);self.addCleanup(writer.close)
        contender=sqlite3.connect(self.db,timeout=.02);self.addCleanup(contender.close)
        writer.execute('BEGIN IMMEDIATE')
        with self.assertRaises(sqlite3.OperationalError):contender.execute('BEGIN IMMEDIATE')
        writer.rollback();contender.execute('BEGIN IMMEDIATE');contender.rollback()

    def test_existing_backup_is_not_overwritten(self):
        self.backup.write_bytes(b'preserve')
        with self.assertRaisesRegex(RuntimeError,'backup_already_exists'):repair.configure(self.db,self.backup)
        self.assertEqual(self.backup.read_bytes(),b'preserve')

    def test_unconfigured_owner_blocks_change(self):
        with sqlite3.connect(self.db) as db:db.execute('DELETE FROM owner_password_credentials')
        with self.assertRaisesRegex(RuntimeError,'owner_configuration_unexpected'):repair.configure(self.db,self.backup)
        self.assertFalse(self.backup.exists())

    def test_database_symlink_is_rejected(self):
        link=self.root/'linked.sqlite3';link.symlink_to(self.db)
        with self.assertRaisesRegex(RuntimeError,'untrusted_database'):repair.configure(link,self.backup)

if __name__=='__main__':unittest.main()
