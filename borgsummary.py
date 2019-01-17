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
import configparser
from pathlib import Path
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from tabulate import tabulate


BORG_ENV = os.environ.copy()
# TODO: possibly want these configureable
BORG_ENV['BORG_RELOCATED_REPO_ACCESS_IS_OK'] = 'yes'
BORG_ENV['BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK'] = 'yes'

Base = declarative_base()
Session = None


def get_data_home():
    """
    Return a Path to the XDG_DATA_HOME for borg-summary.
    """
    if 'XDG_DATA_HOME' in os.environ:
        path = Path(os.environ['XDG_DATA_HOME'])
    else:
        path = Path.home() / '.local' / 'share'
    return (path / 'borg-summary.sqlite3').resolve()


def get_config_home():
    """
    Return a Path to the XDG_CONFIG_HOME for borg-summary.
    """
    if 'XDG_CONFIG_HOME' in os.environ:
        path = Path(os.environ['XDG_CONFIG_HOME'])
    else:
        path = Path.home() / '.config'
    return (path / 'borg-summary.conf').resolve()


def print_error(message, stdout=None, stderr=None):
    """
    Print an error, optionally include stdout and/or stderr strings, using red for error.
    """
    print(message)
    if stdout or stderr:
        print('output from borg follows:')
        if stdout:
            print(stdout.decode().strip())
        if stderr:
            print(stderr.decode().strip())


def du_gb(path):
    """
    Return a float representing the GB size as returned by 'du -sb <path>'.
    """
    result = subprocess.check_output('du -sb {}'.format(str(path)), shell=True)
    return float(result.decode().split()[0]) // 1024 // 1024 // 1024


def get_borg_json(location, cmd):
    """
    <location> is the path to the borg repo.
    Return JSON content for the list <cmd>, executed via subprocess.run().
    Return None if the borg repo is locked (i.e., a backup is currently running).
    Exit with 1 on error.
    """
    # check if lock file exists
    if (Path(location) / 'lock.exclusive').exists():
        return None
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=BORG_ENV)
    if result.returncode != 0:
        print_error('Error running: {}'.format(' '.join(result.args)), result.stdout, result.stderr)
        exit(1)
    json_content = json.loads(result.stdout.decode('utf-8'))
    # print(json.dumps(json_content, indent=4))
    return json_content


class BorgBackupRepo(Base):
    """
    A SQLAlchemy class representing a borg backup repository.
    """

    __tablename__ = 'repo'
    id = Column(String, primary_key=True)
    location = Column(String)

    def __repr__(self):
        return self.location

    @property
    def short_name(self):
        """
        Return the "name" of this repo as a succinct string, derived from its location.
        This assumes the repo is in the "host/repo" directory structure.
        """
        repo_name = str(Path(self.location).name)
        hostname = str(Path(self.location).parent.name)
        if repo_name == hostname:
            return hostname
        else:
            return f'{hostname} - {repo_name}'


    def update(self, verbose=False):
        """
        Get list of backups in the borg backup repo, and add any missing
        backups to SQL.
        """
        list_json = get_borg_json(self.location, ['borg', 'list', '--json', str(self.location)])
        if list_json is None:
            if verbose:
                print(f'Cannot update {self.location}; lock file exists')
            return
        # print(json.dumps(list_json, indent=4))
        session = Session()
        for archive in list_json['archives']:
            backup_name = archive['name']
            backup_id = archive['id']
            # in SQL?
            backup = session.query(BorgBackup).filter_by(id=backup_id).first()
            if backup is not None:
                continue  # exists
            # this backup does not exist in SQL; add it
            info_json = get_borg_json(self.location, ['borg', 'info', '--json', f'{self.location}::{backup_name}'])
            if info_json is None:
                if verbose:
                    print(f'Cannot update {self.location}; lock file exists')
                session.close()
                return
            # print(json.dumps(info_json, indent=4))
            info = info_json['archives'][0]
            # print(json.dumps(info, indent=4))
            # start and end times are like "2018-04-30T08:44:42.000000"
            new_backup = BorgBackup(id=backup_id,
                                    name=backup_name,
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

    def print_summary(self, short_names=False):
        """
        Normal operation - print a summary about the backups in this borg backup repo.
        """
        session = Session()
        backups = session.query(BorgBackup).filter_by(repo=self.id).order_by(BorgBackup.start).all()
        if not backups:
            print('No backups!')
            session.close()
            return
        repo_name = self.short_name if short_names else self.location
        print(repo_name)
        print('-' * len(repo_name))
        print('\nCommand line: {}\n'.format(backups[-1].command_line))
        print('Actual size on disk: {:.1f} GB\n'.format(du_gb(self.location)))
        backup_list = []
        for backup in backups:
            backup_list.append(backup.summary_dict)
        print(tabulate(backup_list, headers='keys', floatfmt=".1f"))
        session.close()

    def check(self):
        """
        Warn if there haven't been any backups for over 24 hours.
        """
        session = Session()
        backups = session.query(BorgBackup).filter_by(repo=self.id).all()
        session.close()
        if not backups:
            print(f'Warning: no backups for {self.location}')
            return
        last_backup_age_in_hours = (datetime.datetime.now() - backups[-1].end).total_seconds() / 3600
        # overridden by config?
        warn_hours = config.getfloat(self.location, 'warn_hours', fallback=30)
        if warn_hours > 0.0 and last_backup_age_in_hours >= warn_hours:
            print('Warning: {}: no backup for {:.1f} hours (last backup finished: '
                  '{:%Y-%m-%d %H:%M})'.format(self.location,
                                              last_backup_age_in_hours,
                                              backups[-1].end))


class BorgBackup(Base):
    """
    A SQLAlchemy class representing a single borg backup.
    """

    __tablename__ = 'backup'
    id = Column(String, primary_key=True)
    repo = Column(String, ForeignKey('repo.id'), nullable=False)
    name = Column(String)
    start = Column(DateTime)
    end = Column(DateTime)
    nfiles = Column(Integer)
    original_size = Column(Integer)
    compressed_size = Column(Integer)
    deduplicated_size = Column(Integer)
    command_line = Column(String)

    def __repr__(self):
        return self.id

    @property
    def duration(self):
        """
        borg stores the duration as number of seconds, but let's return a timedelta
        """
        return self.end - self.start

    @property
    def summary_dict(self):
        """
        Return a dictionary suitable for nicely priting via tabulate
        """
        return {'start': self.start,
                'duration': self.duration,
                '# files': self.nfiles,
                'orig size (GB)': self.original_size / 1073741824,
                'comp size (GB)': self.compressed_size / 1073741824,
                'dedup size (GB)': self.deduplicated_size / 1073741824}


def get_or_create_repo_by_path(path):
    """
    Return the BorgBackupRepo representing <path>, creating if not in SQL.
    """
    session = Session()
    location = str(Path(path).resolve())
    repo = session.query(BorgBackupRepo).filter_by(location=location).first()
    if repo:
        session.close()
        return repo
    # doesn't exist in SQL, so let's add it
    info_json = get_borg_json(location, ['borg', 'info', '--json', location])
    if not info_json:
        session.close()
        print(f'Warning: could not get borg info while trying to create new repo at {location}')
        return None
    repo_id = info_json['repository']['id']
    repo = BorgBackupRepo(id=repo_id, location=location)
    print('Adding new repo: {}'.format(repo))
    session.add(repo)
    session.commit()
    # workaround for https://docs.sqlalchemy.org/en/latest/errors.html#error-bhk3
    repo = BorgBackupRepo(id=repo_id, location=location)
    session.close()
    return repo


def get_all_repos(pool_path):
    """
    Return a list of Paths in pool_path (a Path), each to a single borg backup repo.
    The directory structure is expected to be <pool_path>/<host>/<repo>.  See README.
    """
    repos = []
    for host in sorted(os.listdir(pool_path)):
        for repo in sorted(os.listdir(pool_path / host)):
            repos.append(Path(pool_path / host / repo))
    return repos


def get_summary_info_of_all_repos(pool_path, short_names=False):
    """
    Return a list of dicts, each dict containing some data about a borg backup repo.
    all_repos is a list of paths to borg backup repos.
    """
    session = Session()
    backup_list = []
    for borg_path in get_all_repos(pool_path):
        repo = get_or_create_repo_by_path(borg_path)
        if not repo:
            print(f'Warning: cannot read {borg_path}; perhaps a backup is running')
            continue
        backups = session.query(BorgBackup).filter_by(repo=repo.id).order_by(BorgBackup.start).all()
        if not backups:
            continue  # no backups!
        last_backup = backups[-1]
        # host = session.query(BorgBackupRepo).filter_by(repo=last_backup.repo.id).first().host
        # use the directory structure, which is "host/repo"
        repo_name = repo.short_name if short_names else repo.location
        backup_list.append({'repo': repo_name, 'last backup': last_backup.start,
                            'duration': last_backup.duration, '# files': last_backup.nfiles,
                            '# backups': len(backups), 'size (GB)': du_gb(borg_path)})
    return sorted(backup_list, key=lambda k: k['repo'])


def print_summary_of_all_repos(pool_path, short_names=False):
    """
    Print a brief summary of all backups.
    """
    # actual size of all backups
    print('Size of all backups: {:.1f} GB\n'.format(du_gb(pool_path)))
    backup_list = get_summary_info_of_all_repos(pool_path, short_names)
    # first, warn if there are any repos with no backups
    print(tabulate(backup_list, headers='keys', floatfmt=".1f"))
    print()
    # print detail about every repo
    for repo_path in get_all_repos(pool_path):
        borgbackup = get_or_create_repo_by_path(repo_path)
        if not borgbackup:
            continue
        borgbackup.print_summary(short_names)
        print()


# -----

def main():
    """
    main
    """
    parser = argparse.ArgumentParser(description='Print a summary of a borgbackup repository',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('path', help='The path to a borgbackup repository')
    parser.add_argument('--config', type=str, default=get_config_home(),
                        help='The path to the borg-summary config file to use')
    parser.add_argument('--database', type=str, default=get_data_home(),
                        help='The path to the SQLite data to use')
    parser.add_argument('--update', action='store_true', default=False,
                        help='Update SQL from backup repo (if possible)')
    parser.add_argument('--check', action='store_true', default=False,
                        help='Print a warning if no backups in over 24 hours.')
    parser.add_argument('--detail', action='store_true', default=False,
                        help='Print a summary of the backups in this repo.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Be verbose')
    parser.add_argument('-a', '--all', action='store_true', default=False, help='Work on all repos')
    parser.add_argument('--short-names', action='store_true', default=False,
                        help='In reports, repo "names" are derived from their path (<host>/<repo>).')
    args = parser.parse_args()

    if not args.detail and not args.update and not args.check:
        print('Must specify at least one of "update", "check", detail"')
        return

    global config
    config_filename = Path(args.config).resolve()
    config = configparser.ConfigParser()
    if config_filename.is_file():
        config.read(str(config_filename))  # Python <= 3.5 needs a str here

    sql_filename = Path(args.database).resolve()
    path = Path(args.path).resolve()
    if not path.is_dir():
        print(f'{path} not found!')
        exit(1)

    global Base
    global Session
    engine = create_engine(f'sqlite:///{sql_filename}', echo=False)
    Base.metadata.create_all(engine)
    Session = scoped_session(sessionmaker(bind=engine))

    if not args.all:
        # work on a single repo
        repo = get_or_create_repo_by_path(path)
        if repo:
            # only do stuff if we could read the repo
            if args.update:
                repo.update(verbose=args.verbose)
            if args.check:
                repo.check()
            if args.detail:
                repo.print_summary(short_names=args.short_names)
    else:
        # work on all repos in a directory structure
        for repo_path in get_all_repos(path):
            repo = get_or_create_repo_by_path(repo_path)
            if repo:
                if args.update:
                    repo.update(verbose=args.verbose)
                if args.check:
                    repo.check()
        if args.detail:
            print_summary_of_all_repos(path, short_names=args.short_names)


# -----

if __name__ == '__main__':
    main()
