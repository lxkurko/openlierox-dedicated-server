#!/usr/bin/python -u


import dedicated_control_io as io



SERVER_PORT = 23400 # What port to start server on, 23400 is the default

# Files for logging and ranking
# NOTE: The full path is searched by the game
LOG_FILE = "dedicated_control.log"
RANKING_FILE = "pwn0meter.txt"
RANKING_AUTH_FILE = "pwn0meter_auth.txt"

# Users can enter some commands too
USER_PREFIX = "!"
ADMIN_PREFIX = "@"
#Log user commands and exceptions
USERCOMMAND_LOGGING = False
USERCOMMAND_ERROR_LOGGING = True

VOTING = 1 			#Map/mod voting
KICK_VOTING = 1 	#Kick voting
VOTING_PERCENT = 50	#NOTE: This is now >= instead of >, except for kicks for which it is still >
VOTING_KICK_TIME = 10 # Time in minutes when user kicked by voting cannot re-join server (it auto-kicks user again with message)

#Player and team settings
MIN_PLAYERS = 2
MIN_PLAYERS_TEAMS = 4
MAX_TEAMS = 2			# 2 = Only blue and red teams
TEAMGAMES_VOTING = 1
BALANCE_TEAMS_INGAME = 0	#if 0, balance only in lobby
AUTOCLEAR_TEAM_VOTES = 0	#if 1, clear team votes when round starts
TEAMCHANGE_LOGGING = 0		#if 1, log TDM stuff for debugging purposes
TEAM_SHUFFLE = 20		#Allow team shuffle - 0: don't allow; >0: allow N shuffles per lobby-round

ALLOW_TEAM_CHANGE = False # Player should type "!b", "!r", "!g", or "!y" to set it's own team
TEAM_CHANGE_MESSAGE = "Set your team with %steam b/r" % USER_PREFIX
if MAX_TEAMS >= 3:
	TEAM_CHANGE_MESSAGE += "/g"
if MAX_TEAMS >= 4:
	TEAM_CHANGE_MESSAGE += "/y"


#Game control settings
TOO_FEW_PLAYERS_MESSAGE = "Game will start with minimum %i players." % MIN_PLAYERS
WAIT_BEFORE_SPAMMING_TOO_FEW_PLAYERS_MESSAGE = 40 # Seconds to wait before another "Game will start with %i players" message
FILL_WITH_BOTS_TO = 0 # Fill server with bots if noone playing, set to 2 to get 1 bot with a single human player

WAIT_AFTER_GAME = 10 # Seconds to wait in lobby after round finished
WAIT_BEFORE_GAME = 30 # Seconds to wait in lobby before next round, will give some message
WAIT_BEFORE_GAME_MESSAGE = "Game will start in %i seconds" % WAIT_BEFORE_GAME

#Check ping
PING_CHECK = 1
MAX_PING = 1200 # Max ping to auto-kick player

#Should we check the game version and notify those who use outdated or buggy versions
VERSION_CHECK = 1

# Should we allow !rank user command
RANKING = 1 
# Should we authenticate worm by its skin color 
#NOTE: This is a very weak authentication method and should not really be used
RANKING_AUTHENTICATION = 0 


# List of auto-cycle levels
# NOTE: Use (exact!) file names, not the names shown in game
LEVELS = [	
			"Complex.lxl",
			"FossilFacility.lxl",
		]



# List of presets to use on server - you may specify a preset multiple times
# If this list is empty all presets are used
# See dedicated_control_presets.py for reference
PRESETS = [ "Classic" ]

#Some options that should be set, you don't need to touch them in most cases
#NOTE: Most options are now set in options.cfg
GLOBAL_SETTINGS = {
	
	"GameOptions.Network.EnableChat":               0, # No IRC chat needed for ded server
	"GameOptions.Network.AutoSetupHttpProxy":       0,
	"GameOptions.Network.HttpProxy":                "",
	"GameOptions.Advanced.MaxCachedEntries":        0, # Disable cache for ded server
}

# List of default/lame names that are not allowed on the server
FORBIDDEN_NAMES = [
				"OpenLieroXor",
				"The Second",
				"worm",
				"Player",
				".",
				"",
				" ",
]
#What to do when non-allowed name is detected
NAME_CHECK_ACTION = 1 # 0=no action, 1=warn and use random rankname, 2=kick
NAME_CHECK_KICKMSG = "Please create yourself a proper nickname using the Player Profiles menu"
NAME_CHECK_WARNMSG = "<font color=#FFFF00>Hi! Looks like you are using a default or inappropriate nickname. You can still play here, but your rank will be saved using a random name. For the best game experience, please create yourself a proper nickname using the Player Profiles menu!"
NAME_CHECK_RANDOM = 1337	#Use this to set the number of possible random names
HANDLE_RANDOMS_IN_RANKTOTAL = 1	#Count random#### players separately in !ranktotal

# Server/control script updates that players can see using !news
CONTROL_UPDATES = 0 # Are there any recent updates

# List of recent updates
CONTROL_UPDATES_LIST = [
			"This is a default message",
			"This is another default message",
]

# Should we kick people that have quotation marks in their names - they don't show up properly in ranking.
#NOTE: This should not be needed anymore as the quotes can be removed when setting up the name used by the controller...
KICK_QUOTEMARKS = 0 

#Should we make rank manipulation a bit harder by allowing only one player per one IP
#NOTE: This is a weak check and may cause more harm than good as it prevents people behind a shared IP from joining while not really preventing rank manipulation
ONE_PLAYER_PER_IP = False

#How long nicks are allowed
#NOTE: Now oversized nicks are truncated and this is not needed TODO: Remove this?
MAX_NAME_LENGTH = 20

#Length-based antispam - should we do something to players who send oversized messages and cause excessive lag
ANTISPAM = 2	# 0 = disabled, 1 = kick only, 2 = kick and ban temporarily, 3 = kick and ban
ANTISPAM_KICKLIMIT = 750		#Minimum message length to kick a player
ANTISPAM_BANLIMIT = 1200		#Minimum message length to ban a player

#Should we warn and kick those who send default autotaunts. 
TAUNT_ANTISPAM = 1 # 0 = no action, 1 = kick, 2 = ban temporarily
TAUNT_ANTISPAM_LIMIT = 5	#how many autotaunts are tolerated
TAUNT_ANTISPAM_WARNING = "<font color=#FFFF00>Please stop spamming! You may get kicked!"	#Warning message for spammers
#taunt definitions
TAUNT_KEYWORDS = [
			"edit it in file cfg/taunts.txt",
			"``##``###````##````##````##``###````##````##",
	]		
		
#NEW: Impersonation protection - detect attempts to impersonate another player using the newline tag
ANTI_IMPERSONATION = True
ANTI_IMPERSONATION_ACTION = 1 #0=warn only, 1=kick, 2=kick and ban temporarily
ANTI_IMPERSONATION_LIMIT = 2 #How many attempts are tolerated before kicking. 0=kick immediately. This doesn't affect warnings.
ANTI_IMPERSONATION_TAGS = ["br", "p", "div", "ul", "ol", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "hr"]	#Tags that are not allowed in messages
#NOTE: The default "GOGO" spamfest taunt should be whitelisted here!
ANTI_IMPERSONATION_WHITELIST = ["`<br>``######````######````######````######<br>``##````````````##````##````##````````````##````##<br>``##``###````##````##````##``###````##````##<br>``##````##````##````##````##````##````##````##<br>``######````######````######````######"]
#Warning message for the sender
ANTI_IMPERSONATION_CLIENT_WARNING =  "<font color=#FFFF00>Please do not use newline formatting tags in your message! You may get kicked!"
#Warning message for others. Use <player> and <another> for formatting
ANTI_IMPERSONATION_SERVER_WARNING = "<font color=#FF5000>Warning! <player> might be attempting to impersonate <another>! Note: This may be a false alarm - please report if you think so." 
