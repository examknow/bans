from .db_bans import *
from .db_chanops import *
from .db_comments import *
from .db_channels import *
from .db_config   import *

class ConfigTables(object):
    def __init__(self, location: str):
        self.bot     = BotConfigTable(location)
        self.channel = ChannelConfigTable(location)

class Database(object):
    def __init__(self, location: str):
        self.channels = ChannelsTable(location)
        self.bans     = BansTable(location)
        self.chanops  = ChanOpsTable(location)
        self.comments = CommentsTable(location)
        self.config   = ConfigTables(location)
