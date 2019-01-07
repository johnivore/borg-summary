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
import csv
import datetime
from pathlib import Path
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey


BORG_ENV = os.environ.copy()
# TODO: possibly want these configureable
BORG_ENV['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
BORG_ENV['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'

BACKUP_FIELDS = ['backup_id', 'start_time', 'end_time', 'num_files', 'original_size',
                 'dedup_size', 'all_original_size', 'all_dedup_size', 'command_line']

Base = declarative_base()


def get_xdg():
    """
    Return a Path to the XDG_DATA_HOME for borg-summary.
    """
    if 'XDG_DATA_HOME' in os.environ:
        return os.environ['XDG_DATA_HOME'] / '.local' / 'share' / 'borg-summary'
    return Path.home() / '.local' / 'share' / 'borg-summary'


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
        return (Path(self.location) / 'lock.exclusive').exists()

    def get_backup_list(self):
        """
        Return a list of (id, fingerprint) for this borg back repo that get be queried with "borg info".
        Returns None if the directory is locked by borgbackup.
        Exits with 1 on error from borg.
        """
        # check for lock file
        if self.lock_file_exists():
            return None
        result = subprocess.run(['borg', 'list', '--short', str(self.location)],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=BORG_ENV)
        if result.returncode != 0:
            print_error('Error running: {}'.format(' '.join(result.args)), result.stdout, result.stderr)
            exit(1)
        backup_list = []
        for line in result.stdout.decode().split('\n'):
            if line:  # there is a blank newline at the end
                backup_list.append(line)
        return backup_list

    def update_backups(self, verbose=False):
        if self.lock_file_exists():
            if verbose:
                print(f'Cannot update {self.location}; lock file exists')
            return
        backups = self.get_backup_list()
        if not backups:
            # either no backups, or repo is locked (i.e., a backup is running)
            return
        session = Session()
        for backup_id in backups:
            # in SQL?
            backup = session.query(BorgBackup).filter(BorgBackup.id == backup_id).first()
            if backup is None:
                # this backup does not exist in SQL; add it
                info = self.get_backup_info(backup_id)
                new_backup = BorgBackup(id=info['backup_id'],
                                        repo=self.id,
                                        start_time=info['start_time'],
                                        end_time=info['end_time'],
                                        num_files=info['num_files'],
                                        original_size=info['original_size'],
                                        dedup_size=info['dedup_size'],
                                        all_original_size=info['all_original_size'],
                                        all_dedup_size=info['all_dedup_size'],
                                        command_line=info['command_line']
                                        )
                if verbose:
                    print('adding {}'.format(new_backup))
                session.add(new_backup)
                session.commit()
        session.close()

    def get_backup_info(self, backup_id):
        """
        Returns a dictionary describing the borg backup <backup_id> in our <location>.
        Exits with 1 on error from borg.
        TODO: throw an exception instead of exiting
        """
        result = subprocess.run(['borg', 'info', f'{self.location}::{backup_id}'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                env=BORG_ENV)
        if result.returncode != 0:
            print_error('Error running "{}"'.format(' '.join(result.args)), result.stdout, result.stderr)
            exit(1)
        borg_info = {'backup_id': backup_id}
        lines = result.stdout.decode().split('\n')
        for line in lines:
            s = line.split()
            if line.startswith('Time (start):'):
                borg_info['start_time'] = datetime.datetime.strptime('{} {}'.format(s[3], s[4]), '%Y-%m-%d %H:%M:%S')
            elif line.startswith('Time (end):'):
                borg_info['end_time'] = datetime.datetime.strptime('{} {}'.format(s[3], s[4]), '%Y-%m-%d %H:%M:%S')
            elif line.startswith('Number of files:'):
                borg_info['num_files'] = int(s[3])
            elif line.startswith('This archive:'):
                borg_info['original_size'] = size_to_gb('{} {}'.format(s[2], s[3]))
                borg_info['dedup_size'] = size_to_gb('{} {}'.format(s[6], s[7]))
            elif line.startswith('All archives:'):
                borg_info['all_original_size'] = size_to_gb('{} {}'.format(s[2], s[3]))
                borg_info['all_dedup_size'] = size_to_gb('{} {}'.format(s[6], s[7]))
            elif line.startswith('Command line:'):
                borg_info['command_line'] = line[14:]
        return borg_info

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
        result = subprocess.check_output('du -sh {}'.format(self.location), shell=True)
        print('Actual size on disk (GB):              {:>8.1f}'.format(size_to_gb(result.decode().split()[0])))
        print()
        print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('Start time', 'End time', '# files', 'Orig size', 'Dedup size'))
        print('{:<16s}  {:<16s}  {:>10s}  {:>10s}  {:>10s}'.format('----------', '--------', '-------', '---------', '----------'))
        for backup in backups:
            print('{:%Y-%m-%d %H:%M}  {:%Y-%m-%d %H:%M}  {:>10n}  {:>10.1f}  {:>10.1f}'.format(backup.start_time,
                                                                                        backup.end_time,
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
        last_backup_age_in_days = (datetime.datetime.now() - backups[-1].end_time).days
        if last_backup_age_in_days >= 1:
            print('Warning: {}: no backup for {} {} (last backup finished: '
                  '{:%Y-%m-%d %H:%M})'.format(self.location,
                                              last_backup_age_in_days,
                                              'day' if last_backup_age_in_days == 1 else 'days',
                                              backups[-1].end_time))


class BorgBackup(Base):
    __tablename__ = 'backup'
    id = Column(String, primary_key=True)
    repo = Column(String, ForeignKey('repo.id'), nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    num_files = Column(Integer)
    original_size = Column(Float)
    dedup_size = Column(Float)
    all_original_size = Column(Float)
    all_dedup_size = Column(Float)
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

    global Session
    engine = sqlalchemy.create_engine('sqlite:////root/borg-summary.sqlite3', echo=False)
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
