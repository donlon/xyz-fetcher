# SPDX-License-Identifier: MIT

import argparse
from datetime import datetime

import pymongo

import config

def open_db(cfg: config.ConfigFile):
    mongo_config = {
        'host': cfg.database_host,
        'port': cfg.database_port,
        'serverSelectionTimeoutMS': 3000
    }
    mongo_config.update({
        'username': cfg.database_username,
        'password': cfg.database_password,
        'authSource': cfg.database_auth_source,
    })

    mongodb = pymongo.MongoClient(**mongo_config)
    server_info = mongodb.server_info()
    # db = mongodb[cfg.database_database_name]
    return mongodb

def main(args):
    cfg = config.ConfigFile(args.config_file)
    cfg.load()

    if not args.pid and not args.task_id:
        print('--task-id or --pid should be set')
        return

    mongodb = open_db(cfg)
    db = mongodb[cfg.database_database_name]

    episode_col: pymongo.collection.Collection = db['episode']
    # TODO: taskid + pid index
    filters = {}
    if args.pid:
        filters['pid'] = args.pid
    if args.task_id:
        filters['__task_id'] = args.task_id
    queries = episode_col.find(filters)
    
    for item in queries:
        id = item.get('_id')
        eid = item.get('eid')
        title = item.get('title')
        pub_date = item.get('pubDate')
        
        # Parse the ISO 8601 date string
        dt = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%S.%fZ")
        # Format to 'YYYYMMDD'
        formatted = dt.strftime("%Y%m%d")

        print(f'id: {id} date: {formatted} link: https://www.xiaoyuzhoufm.com/episode/{eid} title: {title}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export episodes fetched in a task')
    parser.add_argument('config_file', help='path to configuration file')
    # TODO: mode?
    parser.add_argument('--task-id', help="task id to export")
    parser.add_argument('--pid', help="podcast id to export")

    args = parser.parse_args()

    main(args)
