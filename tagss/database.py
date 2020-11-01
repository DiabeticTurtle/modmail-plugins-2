import asyncio
import copy

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument

DEFAULT = {
    'guild_id': None,
    'logs': {
        'message_delete': None,
        'message_edit': None,
        'member_join': None,
        'member_remove': None,
        'member_ban': None,
        'member_unban': None,
        'vc_state_change': None,
        'channel_create': None,
        'channel_delete': None,
        'role_create': None,
        'role_delete': None
    },
    'modlog': {
        'member_warn': None,
        'member_mute': None,
        'member_unmute': None,
        'member_kick': None,
        'member_ban': None,
        'member_unban': None,
        'member_mute': None,
        'member_softban': None,
        'message_purge': None,
        'channel_lockdown': None,
        'channel_slowmode': None
    },
    'time_offset': 0,
    'detections': {
        'filters': [],
        'block_invite': False,
        'english_only': False,
        'auto_purge_trickocord': False,
        'mention_limit': None,
        'spam_detection': None,
        'repetitive_message': None,
        'sexually_explicit': []
    },
    'giveaway': {
        'channel_id': None,
        'role_id': None,
        'emoji_id': None,
        'message_id': None
    },
    'perm_levels': [],
    'command_levels': [],
    'warn_punishments': [],
    'notes': [],
    'warns': [],
    'mutes': [],
    'tags': [],
    'whitelisted_guilds': [],
    'reaction_roles': [],
    'selfroles': [],
    'autoroles': [],
    'ignored_channels': {
        'filter': [],
        'block_invite': [],
        'english_only': [],
        'mention_limit': [],
        'spam_detection': [],
        'repetitive_message': []
    },
    'mute_role': None,
    'prefix': '!!'
}


class DatabaseManager:
    def __init__(self, mongo_uri, *, loop=None):
        self.mongo = AsyncIOMotorClient(mongo_uri)
        self.coll = self.mongo.rainbot.guilds
        self.users = self.mongo.rainbot.users
        self.guilds_data = {}
        self.users_data = {}

        self.loop = loop or asyncio.get_event_loop()
        self.loop.create_task(self.change_listener())

    async def change_listener(self):
        async with self.coll.watch(full_document='updateLookup') as change_stream:
            async for change in change_stream:
                self.guilds_data[int(change['fullDocument']['guild_id'])] = DBDict(change['fullDocument'])

    async def get_guild_config(self, guild_id):
        if guild_id not in self.guilds_data:
            data = await self.coll.find_one({'guild_id': str(guild_id)})
            if data:
                self.guilds_data[guild_id] = DBDict(data)
            else:
                await self.create_new_config(guild_id)

        return self.guilds_data[guild_id]

    # Guilds
    async def update_guild_config(self, guild_id, update):
        self.guilds_data[guild_id] = DBDict(await self.coll.find_one_and_update({'guild_id': str(guild_id)}, update, upsert=True, return_document=ReturnDocument.AFTER))
        return self.guilds_data[guild_id]

    async def create_new_config(self, guild_id):
        data = copy.copy(DEFAULT)
        data['guild_id'] = str(guild_id)
        await self.coll.insert_one(data)
        self.guilds_data[guild_id] = DBDict(data)
        return self.guilds_data[guild_id]

    # Users
    async def get_user(self, user_id):
        self.users_data[user_id] = await self.users.find_one({'user_id': str(user_id)})
        return self.users_data[user_id]

    async def update_user(self, user_id, update):
        self.users_data[user_id] = await self.users.find_one_and_update({'user_id': str(user_id)}, update, upsert=True, return_document=ReturnDocument.AFTER)
        return self.users_data[user_id]


class DBDict(dict):
    def __init__(self, *args, **kwargs):
        self._default = kwargs.pop('_default', DEFAULT)
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        try:
            item = super().__getitem__(key)
        except KeyError:
            item = self._default[key]

        if isinstance(item, dict):
            return DBDict(item, _default=tryget(self._default, key))
        elif isinstance(item, list):
            return DBList(item, _default=tryget(self._default, key))

        return item

    def __getattr__(self, name):
        try:
            return super().__getattribute__(name)
        except AttributeError as e:
            try:
                return self[name]
            except KeyError:
                raise e

    def __copy__(self):
        return DBDict(copy.copy(dict(self)))

    def getlist(self, key):
        return [self[key]]


class DBList(list):
    def __init__(self, *args, **kwargs):
        self._default = kwargs.pop('_default', DEFAULT)
        super().__init__(*args, **kwargs)

    def __getitem__(self, index):
        try:
            item = super().__getitem__(index)
        except KeyError:
            item = self._default[index]

        if isinstance(item, dict):
            return DBDict(item, _default=tryget(self._default, index))
        elif isinstance(item, list):
            return DBList(item, _default=tryget(self._default, index))

        return item

    def __copy__(self):
        return DBList(copy.copy(list(self)))

    def __iter__(self):
        for i in super().__iter__():
            if isinstance(i, dict):
                i = DBDict(i)
            if isinstance(i, list):
                i = DBList(i)
            yield i

    def get_kv(self, key, value):
        for i in self:
            if i[key] == value:
                return i

        raise IndexError(f'Key {key} with {value} not found')


def tryget(obj, index):
    try:
        return obj[index]
    except (KeyError, IndexError):
        return None
