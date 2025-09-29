# SPDX-License-Identifier: MIT

import argparse
from datetime import datetime, timezone
import json
import os
from collections.abc import Callable

import pymongo
import toml

import api

class AppException(Exception): ...

class Fetcher:
    def __init__(self):
        self.task_id: str = None
        self.mongodb: pymongo.MongoClient = None
        self.fetch_episodes: True = None
        self.episodes_order: str = None
        self.episodes_max_count: int = None
        self.fetch_comments: True = None
        self.comments_max_count_primary: int = None
        self.comments_max_count_thread: int = None
        self.config: dict = {}
        self.token_filename: str = None
        self.device_idfv: str = None
        self.device_id: str = None
        self.access_token: str = None
        self.refresh_token: str = None
        self.api_helper: api.ApiHelper = None


    def main(self, args):
        self.task_id = 'task_' + datetime.now().strftime("%Y%m%d_%H%M%S") # TODO: task id from database
        self.fetch_episodes = args.fetch_episodes
        self.episodes_order = args.episodes_order
        self.episodes_max_count = args.episodes_max_count
        self.fetch_comments = args.fetch_comments
        self.comments_max_count_primary = args.comments_max_count_primary
        self.comments_max_count_thread = args.comments_max_count_thread

        self.load_config_file(args.config_file)
        self.create_api_helper()

        if args.pid:
            if args.eid:
                raise AppException('invalid combination')
            self.fetch_podcast(args.pid)
        elif args.eid:
            if not args.fetch_episodes:
                raise AppException('error: --fetch-episode set to false when --eid is set')
            self.fetch_episode(args.eid)

        else:
            raise AppException('--pid or --eid should be set')


    def load_config_file(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            self.config = toml.load(f)

        fetcher_config = self.config.get('fetcher', {})
        token_filename = fetcher_config.get('token_filename', '')
        self.device_idfv = fetcher_config.get('device_idfv', '')
        self.device_id = fetcher_config.get('device_id', '')

        if not token_filename:
            raise AppException('fetcher.token_filename is not set in config file')

        self.token_filename = os.path.join(os.path.dirname(filename), token_filename)
        self.load_token_file()
        
        database_config: dict = self.config.get('database', {})
        mongo_config = {
            'host': database_config.get('host'),
            'port': database_config.get('port'),
            'serverSelectionTimeoutMS': 3000
        }
        mongo_config.update({
            'username': database_config.get('username'),
            'password': database_config.get('password'),
            'authSource': database_config.get('auth_source', ''),
        })

        self.mongodb = pymongo.MongoClient(**mongo_config)
        server_info = self.mongodb.server_info()
        db_name = database_config.get('database_name')
        if not db_name:
            raise AppException('database.database_name is not set in config file')
        self.db = self.mongodb[db_name]
        print('database connected.')


    def load_token_file(self):
        with open(self.token_filename, 'r', encoding='utf-8') as f:
            tokens: dict = json.load(f)

        self.access_token = tokens.get('access_token', '')
        self.refresh_token = tokens.get('refresh_token', '')
        if not self.access_token:
            raise AppException('access_token is not set in token file')
        if not self.refresh_token:
            raise AppException('refresh_token is not set in token file')


    def save_token_file(self, access_token: str, refresh_token: str):
        tokens = {
            'access_token': access_token,
            'refresh_token': refresh_token,
        }
        with open(self.token_filename, 'w', encoding='utf-8') as f:
            json.dump(tokens, f, indent=4)


    def token_refresh_callback(self, obj: dict):
        if not obj.get('success', False):
            return
        self.save_token_file(access_token=obj.get('x-jike-access-token', ''),
                             refresh_token=obj.get('x-jike-refresh-token', ''))
        print('access token updated')


    def create_api_helper(self):
        self.api_helper = api.ApiHelper(device_idfv=self.device_idfv,
                                        device_id=self.device_id,
                                        access_token=self.access_token,
                                        refresh_token=self.refresh_token,
                                        token_refresh_callback=self.token_refresh_callback)


    def fetch_podcast(self, pid):
        print(f'fetching podcast id={pid}')
        res = self.api_helper.get_podcast(pid)
        podcast_data = res.get('data', None)
        if not podcast_data:
            raise AppException(f'Failed to get podcast data: {pid}')
        self.save_podcast_data(podcast_data)

        if self.fetch_episodes:
            episodes = []
            def fetch_func(load_more_key):
                return self.api_helper.list_episode(pid, load_more_key=load_more_key)
            def save_func(data):
                nonlocal episodes
                for episode in data:
                    eid = episode["eid"]
                    self.save_episode_data(episode)
                    print(f'fetched episode id={eid}')
                    print(f'                title={episode["title"]}')
                    if self.fetch_comments:
                        self.fetch_episode_comments(eid)
                    # self.fetch_episode(eid)
                episodes += data
            self.fetch_items_paged(fetch_func, save_func, self.episodes_max_count)
            print(f'  fetched {len(episodes)} episodes')


    def fetch_episode(self, eid):
        print(f'fetching episode id={eid}')
        res = self.api_helper.get_episode(eid)
        episode_data = res.get('data', None)
        if not episode_data:
            raise AppException(f'Failed to get episode data: {eid}')
        print(f'  title={episode_data["title"]}')
        self.save_episode_data(episode_data)

        if self.fetch_comments:
            self.fetch_episode_comments(eid)


    def fetch_items_paged(self,
                          fetch_func: Callable[[dict], dict],
                          save_func: Callable[[dict], None],
                          max_count):
        fetched_count = 0
        more_key = None
        while max_count == 0 or fetched_count < max_count:
            res = fetch_func(load_more_key=more_key)
            # res['totalCount']
            data = res.get('data', None)
            save_func(data)
            fetched_count += len(data)
            more_key = res.get('loadMoreKey')
            if more_key is None:
                break


    def fetch_episode_comments(self, eid):
        print(f'fetching comments for episode id={eid}')
        comments = []
        def primary_fetch_func(load_more_key):
            return self.api_helper.list_comment_primary(eid, load_more_key=load_more_key)
        def primary_save_func(data):
            nonlocal comments
            for comment in data:
                self.save_comment_data(comment)
            comments += data
        self.fetch_items_paged(primary_fetch_func, primary_save_func, self.comments_max_count_primary)

        print(f'  fetched {len(comments)} primary comments')

        fetched_thread_comments = 0
        current_comment_id = None
        def thread_fetch_func(load_more_key):
            nonlocal current_comment_id
            return self.api_helper.list_comment_thread(current_comment_id, load_more_key=load_more_key)
        def thread_save_func(data):
            nonlocal fetched_thread_comments
            for comment in data:
                self.save_comment_data(comment)
                fetched_thread_comments += 1

        for comment in comments:
            current_comment_id = comment.get('id')
            if comment.get('replyCount', 0) > 0:
                self.fetch_items_paged(thread_fetch_func,
                                       thread_save_func,
                                       self.comments_max_count_thread)
        print(f'  fetched {fetched_thread_comments} thread comments')


    def insert_to_db(self, collection_name: str, obj: dict):
        self.db[collection_name].insert_one({
            **obj,
            '__task_id': self.task_id,
            '__insert_time': datetime.now(timezone.utc),
        })


    def save_user_data(self, user_data):
        self.insert_to_db('user', user_data)


    def save_podcast_data(self, podcast_data: dict):
        podcasters = podcast_data.pop('podcasters', [])
        for podcaster in podcasters:
            self.save_user_data(podcaster)
        podcast_data['podcasters'] = [{'uid': podcaster['uid']} for podcaster in podcasters]
        self.insert_to_db('podcast', podcast_data)


    def save_episode_data(self, episode_data: dict):
        podcast = episode_data.pop('podcast', None)
        episode_data['replyToComment'] = {
            'pid': podcast['pid']
        }
        
        # TODO: drop the following fields:
        # isPlayed
        # isFinished
        # isFavorited
        # isPicked
        # TODO: save podcast if fetching episode
        # TODO: trim sponsors
        self.insert_to_db('episode', episode_data)


    def save_comment_data(self, comment_data: dict):
        author = comment_data.pop('author', None)
        if author:
            self.save_user_data(author)
        if 'replies' in comment_data:
            replies = comment_data.pop('replies', [])
            for reply in replies:
                self.save_comment_data(reply)
            comment_data['replies'] = [{'id': reply['id']} for reply in replies]

        reply_to_comment = comment_data.pop('replyToComment', None)
        if reply_to_comment:
            comment_data['replyToComment'] = {
                'id': reply_to_comment['id']
            }
        self.insert_to_db('comment', comment_data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', help='path to configuration file')
    # Podcast settings
    parser.add_argument('--pid', help="podcast id to fetch")
    # Episode settings
    parser.add_argument('--eid', help="episode id to fetch")
    parser.add_argument('--no-fetch-episodes', action='store_false', dest='fetch_episodes', default=True,
                        help="do not fetch episodes")
    parser.add_argument('--episodes-order', choices=['asc', 'desc'], default='desc',
                        help="max episodes to fetch")
    parser.add_argument('--episodes-max-count', type=int, default=0,
                        help="max episodes to fetch")
    # Comment settings
    parser.add_argument('--no-fetch-comments', action='store_false', dest='fetch_comments', default=True,
                        help="should fetch comments")
    parser.add_argument('--comments-max-count-primary', type=int, default=0,
                        help="max primary comments to fetch")
    parser.add_argument('--comments-max-count-thread', type=int, default=0,
                        help="max thread comments to fetch")
    # TODO: comment order

    args = parser.parse_args()

    fetcher = Fetcher()
    try:
        fetcher.main(args)
    except AppException as e:
        print(e)
        exit(1)