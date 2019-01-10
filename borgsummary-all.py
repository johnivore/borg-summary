#!/usr/bin/env python3

"""
borgsummary-all.py

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
from pathlib import Path
import argparse
import subprocess
from tabulate import tabulate
import sqlalchemy
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker, scoped_session
from borgsummary import init_session, Session, BorgBackup, BorgBackupRepo, get_or_create_repo_by_path, get_data_home


def get_all_repos(pool_path):
    """
    Return a list of Paths in pool_path (a Path), each to a single borg backup repo.
    """
    repos = []
    for host in sorted(os.listdir(pool_path)):
        for repo in sorted(os.listdir(pool_path / host)):
            repos.append(Path(pool_path / host / repo))
    return repos


def get_summary_info_of_all_repos(pool_path):
    """
    Return a list of dicts, each dict containing some data about a borg backup repo.
    all_repos is a list of paths to borg backup repos.
    """
    session = Session()
    backup_data = {}
    for borg_path in get_all_repos(pool_path):
        repo = get_or_create_repo_by_path(borg_path)
        last_backup = session.query(BorgBackup).filter_by(repo=repo).order_by(BorgBackup.start).last()
        print(last_backup)
    #     if not backups:
    #         print('No backups!')
    #         session.close()
    #         return

    #     backup_data[borgbackup.host] = (borgbackup.repo, borgbackup.read_backup_data_file())
    # summaries = []
    # for host in backup_data:
    #     repo, data = backup_data[host]
    #     if not data:
    #         # no data!
    #         summary = {'host': host, 'repo': repo, 'num_backups': 0}
    #     else:
    #         last_backup = data[-1]
    #         duration = last_backup['end_time'] - last_backup['start_time']
    #         # some info about all backups as well as the most recent one
    #         summary = {'host': host,
    #                    'repo': repo,
    #                    'backup_id': last_backup['backup_id'],
    #                    'start_time': last_backup['start_time'],
    #                    'end_time': last_backup['end_time'],
    #                    'duration': duration,
    #                    'num_backups': len(data),
    #                    'num_files': last_backup['num_files'],
    #                    'original_size': last_backup['original_size'],
    #                    'dedup_size': last_backup['dedup_size'],
    #                    'all_original_size': last_backup['all_original_size'],
    #                    'all_dedup_size': last_backup['all_dedup_size'],
    #                    'command_line': last_backup['command_line']}
    #     summaries.append(summary)
    # return summaries


def update_all_repos(pool_path):
    """
    For every repo, update SQLite to reflect the repo's contents.
    Skip if repo is locked.
    """
    for repo_path in get_all_repos(pool_path):
        borg_repo = get_or_create_repo_by_path(repo_path)
        borg_repo.update()


def check_all_repos(pool_path):
    """
    For every repo, print a warning if there hasn't been a backup in over 24 hours.
    """
    for repo_path in get_all_repos(pool_path):
        borg_repo = get_or_create_repo_by_path(repo_path)
        borg_repo.check()


def print_summary_of_all_repos(pool_path):
    """
    Print a brief summary of all backups.
    """
    # actual size of all backups
    result = subprocess.check_output('du -sb {}'.format(str(pool_path)), shell=True)
    du_bytes = int(result.decode().split()[0]) // 1024 // 1024 // 1024
    print('Size of all backups: {:.1f} GB\n'.format(du_bytes))

    summaries = get_summary_info_of_all_repos(pool_path)

    # first, warn if there are any repos with no backups
    for summary in list(summaries):
        if summary['num_backups'] == 0:
            print('Warning: No backups for {}'.format(summary['backup_id']))
            summaries.remove(summary)

    # check if host == repo for all backups
    # if so, we'll remove the repo field to make the report more succinct
    all_host_eq_repo = True
    for summary in summaries:
        if summary['host'] != summary['repo']:
            all_host_eq_repo = False
            break
    if all_host_eq_repo:
        new_summaries = []
        for summary in list(summaries):
            del summary['repo']
            new_summaries.append(summary)
        summaries = new_summaries

    # two tables, one summarizing the last backup & total backup, and one showing the command line
    tables = [
        ['host', 'repo', 'start_time', 'duration', 'num_files', 'num_backups', 'all_dedup_size'],
        # ['host', 'repo', 'command_line']
    ]

    # prettyify the headers
    replacement_keys = {
        'start_time': 'last backup',
        'num_backups': '# backups',
        'num_files': '# files',
        'all_dedup_size': 'size (GB)',
        'command_line': 'command line',
    }

    for table in tables:
        # only include the fields above
        table_data = []
        for summary in summaries:
            new_summary = {}
            for key in table:
                if key in summary:
                    new_summary[key] = summary[key]
                if key in replacement_keys:
                    new_summary[replacement_keys[key]] = summary[key]
                    del new_summary[key]
            table_data.append(new_summary)
        print(tabulate(table_data, headers='keys'))
        print()

    # print detail about every repo
    for repo_path in get_all_repos(pool_path):
        borgbackup = BorgBackupRepo(repo_path)
        borgbackup.print_summary()
        print()



# -----

def main():
    """
    main
    """
    parser = argparse.ArgumentParser(description='Print a summary of borgbackup repositories',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('pool', help='The root directory of a set of borgbackup repositories')
    parser.add_argument('--database', type=str, default=None,
                        help='The path to the SQLite data to use')
    parser.add_argument('--update', action='store_true', default=False,
                        help='Update SQL from backup repo (if possible)')
    parser.add_argument('--check', action='store_true', default=False,
                        help='Print a warning if no backups in over 24 hours.')
    parser.add_argument('--detail', action='store_true', default=False,
                        help='Print a summary of the backups in this repo.')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Be verbose')
    args = parser.parse_args()

    if not args.detail and not args.update and not args.check:
        print('Must specify at least one of "update", "check", detail"')
        return

    if args.database:
        sql_filename = Path(args.database).resolve()
    else:
        sql_filename = get_data_home()

    init_session(sql_filename)

    # global Session
    # engine = sqlalchemy.create_engine(f'sqlite:///{sql_filename}', echo=False)
    # Base.metadata.create_all(engine)

    # Session = scoped_session(sessionmaker(bind=engine))
    # borgsummary.Base.metadata.create_all(engine)
    # borgsummary.Session = scoped_session(sessionmaker(bind=engine))

    # Session = scoped_session(sessionmaker(bind=engine))
    # # Session = sqlalchemy.orm.sessionmaker(bind=engine)
    # session = Session()

    # Session = sqlalchemy.orm.sessionmaker(bind=engine)
    # session = Session()


# engine = create_engine("sqlite:///:memory:")
# base.Base.metadata.create_all(engine, checkfirst=True)
# Session = sessionmaker(bind=engine)
# session = Session()


    pool_path = Path(args.pool)
    if not os.path.isdir(pool_path):
        print(f'{pool_path} not found!')
        exit(1)

    if args.update:
        update_all_repos(pool_path)
        return

    if args.check:
        check_all_repos(pool_path)
        return

    print_summary_of_all_repos(pool_path)


if __name__ == '__main__':
    main()
