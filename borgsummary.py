#!/usr/bin/env python3

"""
borgsummary.py

Copyright 2019  John Begenisich

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import subprocess
import argparse
import datetime
import json
from pathlib import Path
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey


BORG_ENV = os.environ.copy()
# TODO: possibly want these configureable
BORG_ENV['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
BORG_ENV['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'

BACKUP_FIELDS = ['backup_id', 'start', 'end', 'num_files', 'original_size',
                 'dedup_size', 'all_original_size', 'all_dedup_size', 'command_line']

Base = declarative_base()


def get_data_home():
    """
    Return a Path to the XDG_DATA_HOME for borg-summary.
    """
    if 'XDG_DATA_HOME' in os.environ:
        path = Path(os.environ['XDG_DATA_HOME'])
    else:
        path = Path.home() / '.local' / 'share'
    return (path / 'borg-summary.sqlite3').resolve()


def size_to_gb(size):
    """
    Convert string size into GB float.
    size is a string like "43.1 GB" or "37.88 T", etc.
    Must end in 'GB', 'G', 'TB', etc.
    """
    import re
    value = float(re.sub('[^0-9\.]', '', size))  # remove everything except numbers & '.'
    size = size.lower()
    if size.endswith('g') or size.endswith('gb'):
        pass
    elif size.endswith('t') or size.endswith('tb'):
        value = value * 1024
    elif size.endswith('m') or size.endswith('mb'):
        value = value / 1024
    elif size.endswith('k') or size.endswith('kb'):
        value = value / 1024 / 1024
    else:
        # I guess we should throw an exception, but...
        print(f'Warning: size_to_gb() can\'t process "{size}"')
    return round(value, 1)


def print_error(message, stdout=None, stderr=None):
    """
    Print an error, optionally include stdout and/or stderr strings, using red for error.
    """
    # TODO: color should be optional
    print(f'\033[0;31m{message}\033[0m')
    if stdout or stderr:
        print('output from borg follows:')
        if stdout:
            print(stdout.decode().strip())
        if stderr:
            print('\033[0;31m{}\033[0m'.format(stderr.decode().strip()))


def get_repo_id(path):
    """
    Return the borg backup repo ID from the path,
    as gleaned from "borg info".
    """
    # check for lock file
    if (Path(path) / 'lock.exclusive').exists():
        # TODO: throw exception
        return None
    result = subprocess.run(['borg', 'info', str(path)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=BORG_ENV)
    if result.returncode != 0:
        print_error('Error running: {}'.format(' '.join(result.args)), result.stdout, result.stderr)
        exit(1)
    for line in result.stdout.decode().split('\n'):
        # there is a blank newline at the end
        if line.startswith('Repository ID:'):
            repo_id = line.split()[-1]
    return repo_id


class BorgBackupRepo(Base):
    __tablename__ = 'repo'
    id = Column(String, primary_key=True)
    location = Column(String)

    def __repr__(self):
        return self.location

    def lock_file_exists(self):
        """
        Check if the lock file for this borg repo exists.
        """
        return (Path(self.location) / 'lock.exclusive').exists()

    def get_borg_json(self, cmd):
        """
        Check for lock file (return None if exists).
        Return JSON content for the list <cmd>, executed via subprocess.run().
        Exit with 1 on error.
        """
        # check for lock file
        if self.lock_file_exists():
            return None
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=BORG_ENV)
        if result.returncode != 0:
            print_error('Error running: {}'.format(' '.join(result.args)), result.stdout, result.stderr)
            exit(1)
        json_content = json.loads(result.stdout.decode('utf-8'))
        # print(json.dumps(json_content, indent=4))
        return json_content

    def update_backups(self, verbose=False):
        """
        Get list of backups in the borg backup repo, and add any missing
        backups to SQL.
        """
        list_json = self.get_borg_json(['borg', 'list', '--json', str(self.location)])
        if list_json is None:
            if verbose:
                print(f'Cannot update {self.location}; lock file exists')
            return
        # print(json.dumps(list_json, indent=4))
        session = Session()
        for archive in list_json['archives']:
            backup_id = archive['archive']
            # in SQL?
            backup = session.query(BorgBackup).filter_by(id=backup_id).first()
            if backup is not None:
                continue  # exists
            # this backup does not exist in SQL; add it
            info_json = self.get_borg_json(['borg', 'info', '--json', f'{self.location}::{backup_id}'])
            if info_json is None:
                if verbose:
                    print(f'Cannot update {self.location}; lock file exists')
                return
            # print(json.dumps(info_json, indent=4))
            info = info_json['archives'][0]
            print(json.dumps(info, indent=4))
            # start and end times are like "2018-04-30T08:44:42.000000"
            # print(datetime.datetime.strptime(info['start'][:19], '%Y-%m-%dT%H:%M:%S'))
            new_backup = BorgBackup(id=info['id'],
                                    repo=self.id,
                                    start=datetime.datetime.strptime(info['start'][:19], '%Y-%m-%dT%H:%M:%S'),
                                    end=datetime.datetime.strptime(info['end'][:19], '%Y-%m-%dT%H:%M:%S'),
                                    nfiles=info['stats']['nfiles'],
                                    original_size=info['stats']['original_size'],
                                    compressed_size=info['stats']['compressed_size'],
                                    deduplicated_size=info['stats']['deduplicated_size'],
                                    command_line=' '.join(info['command_line'])
                                    )
            if verbose:
                print('adding {}'.format(new_backup))
            session.add(new_backup)
            session.commit()
        session.close()

    def print_summary(self):
        """
        Normal operation - print a summary about the backups in this borg backup repo.
        """
        session = Session()
        backups = session.query(BorgBackup).filter_by(repo=self.id).all()
        if not backups:
            print('No backups!')
            session.close()
            return
        print(self.location)
        print('-' * len(self.location))
        print('\nCommand line: {}\n'.format(backups[-1].command_line))
        # TODO: switch to tabulate, I guess
        print('Size of all backups (GB):              {:>8.1f}'.format(backups[-1].all_original_size))
        print('Deduplicated size of all backups (GB): {:>8.1f}'.format(backups[-1].all_dedup_size))
        result = subprocess.check_output('du -sBG {}'.format(self.location), shell=True)
        print('Actual size on disk (GB):              {:>8.1f}'.format(size_to_gb(result.decode().split()[0])))
        print()
        print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('Start time', 'End time', '# files', 'Orig size', 'Dedup size'))
        print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('----------', '--------', '-------', '---------', '----------'))
        for backup in backups:
            print('{:%Y-%m-%d %H:%M}  {:%Y-%m-%d %H:%M}  {:>10n}  {:>10.1f}  {:>10.1f}'.format(backup.start,
                                                                                        backup.end,
                                                                                        backup.num_files,
                                                                                        backup.original_size,
                                                                                        backup.dedup_size))
        session.close()

    def check(self):
        """
        Warn if there haven't been any backups for over 24 hours.
        """
        session = Session()
        backups = session.query(BorgBackup).filter_by(repo=self.id).all()
        if not backups:
            print(f'Warning: no backups for {self.location}')
            session.close()
            return
        # time of backup completion
        last_backup_age_in_days = (datetime.datetime.now() - backups[-1].end).days
        if last_backup_age_in_days >= 1:
            print('Warning: {}: no backup for {} {} (last backup finished: '
                  '{:%Y-%m-%d %H:%M})'.format(self.location,
                                              last_backup_age_in_days,
                                              'day' if last_backup_age_in_days == 1 else 'days',
                                              backups[-1].end))


class BorgBackup(Base):
    __tablename__ = 'backup'
    id = Column(String, primary_key=True)
    repo = Column(String, ForeignKey('repo.id'), nullable=False)
    hostname = Column(String)
    start = Column(DateTime)
    end = Column(DateTime)
    nfiles = Column(Integer)
    original_size = Column(Integer)
    compressed_size = Column(Integer)
    deduplicated_size = Column(Integer)
    command_line = Column(String)

    def __repr__(self):
        return self.id


# -----

def main():
    """
    main
    """
    parser = argparse.ArgumentParser(description='Print a summary of a borgbackup repository',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('path', help='The path to a borgbackup repository')
    # FIXME: use --data-path or remove it
    # parser.add_argument('--data-path', type=str, default=Path.home() / 'borg-summary',
    #                     help='The path to CSV data files holding backup info; default: {}'.format(Path.home() / 'borg-summary'))
    parser.add_argument('--update', action='store_true', default=False, help='Update SQL from backup repo (if possible)')
    parser.add_argument('--check', action='store_true', default=False,
                        help='Print a warning if no backups in over 24 hours.')
    parser.add_argument('--detail', action='store_true', default=False,
                        help='Print a summary of the backups in this repo.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Be verbose')
    args = parser.parse_args()

    if not args.detail and not args.update and not args.check:
        print('Must specify at least one of "update", "check", detail"')
        return

    sql_filename = get_data_home()

    global Session
    engine = sqlalchemy.create_engine(f'sqlite:///{sql_filename}', echo=False)
    Base.metadata.create_all(engine)
    Session = sqlalchemy.orm.sessionmaker(bind=engine)
    session = Session()

    location = Path(args.path).resolve()
    repo_id = get_repo_id(location)

    repo = session.query(BorgBackupRepo).filter_by(id=repo_id).first()
    if repo is None:
        # add repo to SQL
        repo = BorgBackupRepo(id=repo_id, location=str(location))
        if args.verbose:
            print('Adding new repo: {}'.format(repo))
        session.add(repo)
        session.commit()

    if args.update:
        repo.update_backups(verbose=args.verbose)

    if args.check:
        repo.check()

    if args.detail:
        repo.print_summary()

    session.close()


if __name__ == '__main__':
    main()
