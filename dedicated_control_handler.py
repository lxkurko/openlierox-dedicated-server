#!/usr/bin/python -u
# Dedicated Control handler script for OpenLieroX


# Needed for sleeping/pausing execution
import time
# Needed for directory access
import os
import sys
import threading
import traceback
import random
import subprocess, signal, os.path
#import re	#for regular expression searches

import portalocker
import dedicated_control_io as io
import dedicated_control_ranking as ranking
import dedicated_control_usercommands as cmds
import dedicated_control_presets as presetcfg	#NEW!



# Preset list
#Key = preset name, value = number of votes
availablePresets = []


#Autocycler preset and map
#Listed in cfg
currentAutocyclePreset = 0
currentAutocycleMap = 0

worms = {} # List of all worms on the server
# Bots don't need to be itterated with the other ones.
bots = {}  # Dictionary of all possible bots

#IP and release time
kickedUsers = {}

# Function that controls ded server behavior
controlHandler = None

scriptPaused = False


# Uncomment following 3 lines to get lots of debug spam into dedicated_control_errors.log file
#def HeavyDebugTrace(frame,event,arg):
#	sys.stderr.write( 'Trace: ' + str(event) + ': ' + str(arg) + ' at ' + str(frame.f_code) + "\n" )
#sys.settrace(HeavyDebugTrace)

# Game states
GAME_READY = -1
GAME_QUIT = 0
GAME_LOBBY = 1
GAME_WEAPONS = 2
GAME_PLAYING = 3

gameState = GAME_READY

sentStartGame = False

vote_locked = False		#Use this to determine if it's safe to change settings

shuffle_counter = 0	#Use this to count team shuffles

class Worm:
	def __init__(self):
		self.Name = ""		#This is used for ranks. This can be modified by the control script!
		self.real_name = ""	#This is the name used by the server ##NOTE: Use the sanitized version (see getCleanName() below) unless you really know that this is needed!
		self.Ip = ""
		self.iID = -1
		self.isAdmin = False
		self.isDedAdmin = False
		self.Ping = [] # Contains 25 ping values, real ping = average
		self.Lives = -1 # -1 means Out
		self.Team = 0
		self.Alive = False
		self.kickVoted = 0	#Number of kick votes placed to the player
		self.spammed = 0	#Number of spam messages sent
		self.tags_detected = 0 #Number of attempts to use non-allowed tags, e.g. to impersonate another player
		
		#Votes of this player
		self.votedMap = ""
		self.votedPreset = ""
		self.votedKick = None	#Player ID
		self.votedTeams = 0
	
	def resetKickVotes(self):
		self.kickVoted = 0
	
	def resetVotes(self):
		self.votedMap = ""
		self.votedPreset = ""
		
	def resetTeamVotes(self):
		self.votedTeams = 0
		
	#If the real name contains double quotes ("), it may cause troubles when passed in a command to the server
	#Return a sanitized name without double quotes
	def getCleanName(self):
		return self.real_name.replace("\"", "\'\'")
	
def init():

	checkConfigLists()
	initPresets()

	io.startLobby(cfg.SERVER_PORT)

	# if we load this script with already some worms on board, we have to update our worm list now
	for w in io.getWormList():
		parseNewWorm( w, io.getWormName(w) )

	
	for f in cfg.GLOBAL_SETTINGS.keys():
		io.setvar( f, cfg.GLOBAL_SETTINGS[f] )
	
	if io.getVar("GameOptions.GameInfo.AllowEmptyGames") == "false" and cfg.MIN_PLAYERS < 2:
		io.messageLog("GameOptions.GameInfo.AllowEmptyGames is false - setting cfg.MIN_PLAYERS to 2", io.LOG_WARN)
		cfg.MIN_PLAYERS = 2
		

#Check that autocycle maps and shortcut maps are actually available
def checkConfigLists():
	
	availableMapList = io.listMaps()
	
	for l in cfg.LEVELS:
		if l not in availableMapList:
			io.messageLog("Autocycle map not found: %s" % l, io.LOG_ERROR)
		
	for k in presetcfg.MAP_SHORTCUTS.values():
		if k not in availableMapList:
			io.messageLog("Shortcut map not found: %s" % k, io.LOG_ERROR)
		

# Parses all signals that are not 2 way (like getip info -> olx returns info)
# Returns False if there's nothing to read
def signalHandler(sig):
	global gameState, oldGameState, scriptPaused, sentStartGame, worms
	global vote_locked

	oldGameState = gameState

	if len(sig) == 0:
		return False #Didn't get anything
		
	header = sig[0]
	
	try:
		if header == "newworm":
			parseNewWorm(int(sig[1]), sig[2])
		elif header == "wormleft":
			parseWormLeft(sig)
		elif header == "privatemessage":
			parsePrivateMessage(sig)
		elif header == "chatmessage":
			parseChatMessage(sig)
		elif header == "wormdied":
			parseWormDied(sig)
		elif header == "wormspawned":
			parseWormSpawned(sig)
		elif header == "wormauthorized":
			parseWormAuthorized(sig)
		elif header == "wormgotadmin":
			worms[int(sig[1])].isDedAdmin = True
			# no other difference to wormauthorized yet - and we also get wormauthorized, so nothing to do anymore
			pass
			
		## Check GameState ##
		elif header == "quit":
			gameState = GAME_QUIT
			exit()
	
		elif header == "backtolobby" or header == "lobbystarted":
			if cfg.RANKING:
				ranking.refreshRank()
			gameState = GAME_LOBBY
			sentStartGame = False
			vote_locked = False		#Always unlock voting when back to lobby
			controlHandler()
	
		elif header == "weaponselections":
			gameState = GAME_WEAPONS
			controlHandler()
		elif header == "gamestarted":
			gameState = GAME_PLAYING
			sentStartGame = False
			controlHandler()
		#TODO: gamestarted && gameloopstart are pretty much duplicates
		# Or are they? Check.
		# Same thing for gameloopend and backtolobby
		elif header == "gameloopstart": #Sent when game starts
			pass
			#io.messageLog("TEST -- SIGNAL: gameloopstart", io.LOG_INFO)	#TEST
		elif header == "gameloopend": #Sent at game end
			pass
			#io.messageLog("TEST -- SIGNAL: gameloopend", io.LOG_INFO)	#TEST
		#elif header == "gameloopend": #Sent when OLX starts
		#	pass
		elif header == "timer": # Sent once per second
			controlHandler()
			
		elif header == "custom":
			io.messageLog(("CUSTOMSIGNAL: %s" % (sig)), io.LOG_INFO)	#TEST
			parseCustom(sig)
			
		else:
			io.messageLog(("I don't understand %s." % (sig)),io.LOG_ERROR)
	
	except Exception:
		traceback.print_exc(None, sys.stderr)

	return True


def parseNewWorm(wormID, name):
	global worms

	
	exists = False
	try:
		worm = worms[wormID]
		exists = True
	except KeyError: #Worm doesn't exist.
		worm = Worm()
	
	worm.real_name = name	#NOTE: This is the name used by the server
	#Now prepare the name used by the script - used for ranking, for example
	name = name.replace("\t", " ").strip() # Do not allow tab in names, it will screw up our ranking tab-separated text-file database	
	#Check if the player has quotation marks in his/her name
	quotemarks_in_nick = 0
	if "\"" in name:
		name = name.replace("\"", "\'\'")	#Double quotes (") cause problems with chat/private messages - convert to single quotes (')
		quotemarks_in_nick = 1
	
	worm.Name = name
	worm.iID = wormID
	worm.Ping = []
	
	wormIP = io.getWormIP(wormID).split(":")[0]	#Get worm IP address now - it will be needed later
	worm.Ip = wormIP
	
	worms[wormID] = worm
	
	#Set team for handler ##NOTE: OLX sets a team when the player joins - and it may not always be 0 (blue)!!! So get the team number now!
	#TEST: Log these initial teams
	if cfg.TEAMCHANGE_LOGGING:
		io.messageLog("TEAMJOIN: Game reports team " + str(io.getWormTeam(wormID)) + " for joining worm " + str(name), io.LOG_INFO)
	worm.Team = io.getWormTeam(wormID)
	
	# io.messageLog("Curtime " + str(time.time()) + " IP " + str(wormIP) + " Kicked worms: " + str(kickedUsers), io.LOG_INFO)
	if wormIP in kickedUsers and kickedUsers[wormIP] > time.time():
		io.kickWorm( wormID, "You can join in " + str(int(kickedUsers[wormIP] - time.time())/60 + 1) + " minutes" )
		return
	
	#Original ranking authentication based on skin color...
	#NOTE: This is a weak way of authentication
	if cfg.RANKING_AUTHENTICATION:
		if not name in ranking.auth:
			ranking.auth[name] = getWormSkin(wormID)
			try:
				f = open(io.getWriteFullFileName(cfg.RANKING_AUTH_FILE),"a")
				try:
					portalocker.lock(f, portalocker.LOCK_EX)
				except:
					pass
				f.write( name + "\t" + str(ranking.auth[name][0]) + " " + ranking.auth[name][1] + "\n" )
				f.close()
			except IOError:
				msg("ERROR: Unable to open ranking authentication file: " + cfg.RANKING_AUTH_FILE)
		else:
			if ranking.auth[name] != getWormSkin(wormID):
				io.kickWorm(wormID, "Player with name %s already registered" % name)
				return

	
	#Kick players that have forbidden nicks
	if name in cfg.FORBIDDEN_NAMES:
		if cfg.NAME_CHECK_ACTION == 1:
			worm.Name = "random" + str(random.randint(0,cfg.NAME_CHECK_RANDOM))	#Assign random name
			io.privateMsg(wormID, cfg.NAME_CHECK_WARNMSG)
		elif cfg.NAME_CHECK_ACTION == 2:
			io.kickWorm(wormID, cfg.NAME_CHECK_KICKMSG)
			return
	
	
	#NEW: Kick players who have newline tags in their nicks - those can cause annoyance
	#NOTE: This may give false positives if there are nested tags, but it's an unlikely case
	if detectFormattingTags(name):
		io.kickWorm(wormID, "Please remove formatting tags ( <...> ) from your nickname - they cause problems")
		return
		
	#Kick players with excessively long nicks.
	#NOTE: In 0.59, oversized name are truncated automatically so this becomes obsolete
	if len(name) > cfg.MAX_NAME_LENGTH:
		io.kickWorm(wormID, "name too long")
		return

	#Kick players with quotation marks in their name (only if configured!)
	#NOTE: This should not be needed anymore
	if quotemarks_in_nick==1 and cfg.KICK_QUOTEMARKS==1:
		io.kickWorm(wormID, "please remove quotation marks from your nickname - they screw up ranking.")
		return
	
	#If only one player per IP allowed, check if there is already a player from the IP
	#NOTE: This is a weak check and may cause more harm than good as it prevents people behind a shared IP from joining while not really preventing rank manipulation
	if cfg.ONE_PLAYER_PER_IP:
		for w in worms.keys():
			if worms[w].Ip == wormIP and w != wormID:
				io.kickWorm(wormID, "only one player per IP address allowed")
				return
	
	#Assign team
	if io.getGameType() == 1:
		worms[wormID].votedTeams = 1  #Set vote status to 1 so that it will be TDM if it was TDM before this player joined
		io.privateMsg(wormID, "Game type is team deathmatch - say !noteams if you do not want teams for the next game")
		#NOTE: The player is already assigned to a team by the game! - so assigning him to the smallest team here would lead to unbalancement
		# if the team status were, for example, [4, 4]. So check whether 1) teams are balanced (difference <=1) or not, and 2) the player is not in the smallest team
		#NOTE: Calling balanceTeams might look more elegant, but it might move other players as well, and it should not be called when we are not in lobby
		#NOTE: Be careful with RandomTeamForNewWorm option! It may cause an exception!
		team_status = getNumberWormsInAllTeams()			#Get team member counts
		team_status = team_status[0:cfg.MAX_TEAMS]			#Remove teams that are not used
		wormteam = io.getWormTeam(wormID)				#Could use worm.Team too, but this might be safer...
		if (max(team_status)-min(team_status)) > 1 and wormteam != team_status.index(min(team_status)):
			setTeam(wormID, team_status.index(min(team_status)))
	
	#Update votes - this is needed if there are, let's say, 3 players who all vote for TDM but TDM requires 4 - now there are 4 and 3 of them vote so TDM should be selected!
	#No need to broadcast anything - TDM is broadcasted if the status changes.
	updateVotes()

def parseWormLeft(sig):
	global worms, gameState, scriptPaused

	wormID = int(sig[1])
	name = sig[2:]

	try:
		if worms[wormID].isAdmin:
			io.messageLog(("Worm %i (%s) removed from admins" % (wormID,name)),io.LOG_ADMIN)
	except KeyError:
		io.messageLog("AdminRemove: Our local copy of wormses doesn't match the real list.",io.LOG_ERROR)
	
	#NOTE: There may be a better way to do this...
	#Check which vote options to broadcast when this player leaves
	temp_votedstatus = []
	if wormID in worms.keys():		#Note: this should be always true but checked anyway...
		if worms[wormID].votedMap:
			temp_votedstatus.append("map")
		if worms[wormID].votedPreset:
			temp_votedstatus.append("mod")
		#NOTE: No need to check team votes here because team status will be checked separately.
		
	# Call last, that way we still have the data active.
	worms.pop(wormID)

	#Update voting status after removing this player from the worms table
	updateVotes(send_msg=tuple(temp_votedstatus))
	
	#Balance teams
	if io.getGameType() == 1:
		if gameState == GAME_LOBBY or cfg.BALANCE_TEAMS_INGAME:
			balanceTeams(bmsg="player left")

	# If all admins left unpause ded server (or it will be unusable)
	isAdmins = False
	for w in worms.keys():
		if worms[w].isAdmin:
			isAdmins = True
	if not isAdmins:
		scriptPaused = False



###########################################################
#TEAM HANDLING FUNCTIONS
###########################################################

#Count team members
#Moved from IO
def getNumberWormsInTeam(team):
	c = 0
	for w in worms.values():
		if io.getWormTeam( w.iID ) == team:
			c += 1
	return c

#Count all team members
def getNumberWormsInAllTeams():
	ret = [0,0,0,0]
	for t in range(0,4):
		ret[t] = getNumberWormsInTeam(t)
	#Check whether the handler and the game are reporting the same number of players per team
	if cfg.TEAMCHANGE_LOGGING:
		testret = [0,0,0,0]
		for w in worms.values():
			testret[w.Team] += 1
		#Only 4 teams so we can do ugly hard-coded check
		if (ret[0]==testret[0] and ret[1]==testret[1] and ret[2]==testret[2] and ret[3]==testret[3]):
			testmsg = "everything is OK."
		else:
			testmsg = "THERE IS AN ERROR!"
		io.messageLog("TEAMSTATUS: Game reports " + str(ret) + ", handler counts " + str(testret) + " -- " + testmsg, io.LOG_INFO)
	
	return ret

#Moved from IO (was setWormTeam, changed to avoid confusion)
def setTeam(wormid, team):
	if wormid in worms.keys() and worms[wormid].iID != -1:
		worms[wormid].Team = team
		io.setWormTeam(wormid, team)
		if cfg.TEAMCHANGE_LOGGING:
			io.messageLog("TEAMCHANGE: Set worm "+str(wormid)+" "+worms[wormid].Name+" to team "+str(team), io.LOG_INFO)
	else:
		io.messageLog("Worm id %i invalid" % wormid ,LOG_ADMIN)


#Set up teams
#This should be called only when switching from deathmatch to TDM
def setupTeams():
	global worms
	
	if cfg.TEAMCHANGE_LOGGING:
		io.messageLog("TEAMSETUP: setupTeams called", io.LOG_INFO)
	
	counter = 0
	for w in worms.values():
		if w.iID != -1:
			setTeam( w.iID, counter % cfg.MAX_TEAMS )
			counter += 1
		

#Balance teams - call this when player leaves
#NOTE: Because basic dictionary is not ordered, calling setupTeams instead of this would cause annoying problems
def balanceTeams(bmsg=""):
	global worms
	
	if cfg.TEAMCHANGE_LOGGING:
		if bmsg:
			io.messageLog("TEAMBALANCE: balanceTeams called: " + bmsg, io.LOG_INFO)
		else:
			io.messageLog("TEAMBALANCE: balanceTeams called without reason given", io.LOG_INFO)
	
	while True:
		team_status = getNumberWormsInAllTeams()
		team_status = team_status[0:cfg.MAX_TEAMS]	#truncate list
		if (max(team_status)-min(team_status)) > 1:
			maxteam = team_status.index(max(team_status))	#team with most members
			minteam = team_status.index(min(team_status))	#team with least members
			for w in worms.values():
				if io.getWormTeam(w.iID) == maxteam:
					setTeam(w.iID, minteam)					#move player from biggest team to smallest
					break
		else:			#If the difference is 1 or less, no need to do changes
			break
	#Log the team status after balancing
	if cfg.TEAMCHANGE_LOGGING:
		io.messageLog("TEAMBALANCE: balance ended, calling for teamstatus...", io.LOG_INFO)
		getNumberWormsInAllTeams()

#Randomize teams
def shuffleTeams():
	global worms, shuffle_counter
	
	if cfg.TEAMCHANGE_LOGGING:
		io.messageLog("TEAMSHUFFLE: shuffleTeams called", io.LOG_INFO)
	
	# Create team mask
	tmask = []
	for k in range(0,len(worms)):
		tmask.append(k % cfg.MAX_TEAMS)
	# Shuffle it
	random.shuffle(tmask)
	
	# Assign teams
	k = 0
	for w in worms.values():
		setTeam(w.iID, tmask[k])
		k += 1
		
	#Advance counter
	shuffle_counter += 1
	

###########################################################
#END OF TEAM HANDLING FUNCTIONS
###########################################################


		
def parsePrivateMessage(sig):
	pass
	
def parseWormAuthorized(sig):	
	global worms

	wormID = int(sig[1])
	try:
		if not worms[wormID].isAdmin:
			worms[wormID].isAdmin = True
			io.messageLog(("Worm %i (%s) added to admins" % (wormID,worms[wormID].Name)),io.LOG_ADMIN)
			# TODO: Send the last part in a PM to the admin. (Needs new backend for private messaging. Add teamchat too!)
			io.authorizeWorm(wormID)
			io.privateMsg(wormID, "%s authenticated for admin! Type %shelp for command info" % (worms[wormID].Name,cfg.ADMIN_PREFIX))
	except KeyError:
		io.messageLog("AdminAdd: Our local copy of wormses doesn't match the real list.",io.LOG_ERROR)


#Chat message handler
def parseChatMessage(sig):
	global worms

	wormID = int(sig[1])
	message = sig[2]
	
	#Length-based anti-spam - see dedicated_config for details
	if cfg.ANTISPAM != 0:
		if len(message) > cfg.ANTISPAM_KICKLIMIT:
			if cfg.ANTISPAM > 1 and len(message) > cfg.ANTISPAM_BANLIMIT:
				if cfg.ANTISPAM ==2:
					kickWithTime(wormID, "excessive spamming")
					return
				elif cfg.ANTISPAM ==3:
					io.banWorm(wormID, "excessive spamming")
					io.messageLog("Player " + worms[wormID].Name + " from IP " + worms[wormID].Ip + " was banned for spamming", io.LOG_INFO)
					return
			else:
				io.kickWorm(wormID, "spamming")
				return
	
	
	#NEW: Impersonation protection - check if the player tries to impersonate another player using the newline tags.
	#NOTE: The "GOGO" spamfest taunt is whitelisted here!
	if cfg.ANTI_IMPERSONATION:
		if message not in cfg.ANTI_IMPERSONATION_WHITELIST and detectFormattingTags(message):
			#Warn the player and count the attempt
			io.privateMsg(wormID, cfg.ANTI_IMPERSONATION_CLIENT_WARNING)
			worms[wormID].tags_detected += 1
			#TODO HACK EXPERIMENTAL TEST: Check whether the message contains other players' nicknames - if yes, warn the other players
			for w in worms.keys():
				if w != wormID and (worms[w].real_name.strip() in message or worms[w].getCleanName().strip() in message):
					if cfg.ANTI_IMPERSONATION_SERVER_WARNING:	#Do not broadcast warning if it doesn't exist
						io.chatMsg(cfg.ANTI_IMPERSONATION_SERVER_WARNING.replace("<player>", worms[wormID].getCleanName()).replace("<another>", worms[w].getCleanName()))
			#Apply sanctions
			if worms[wormID].tags_detected > cfg.ANTI_IMPERSONATION_LIMIT:
				if cfg.ANTI_IMPERSONATION_ACTION == 1:
					io.kickWorm(wormID, "used non-allowed formatting tags in chat")
					return
				elif cfg.ANTI_IMPERSONATION_ACTION == 2:
					kickWithTime(wormID, "used non-allowed formatting tags in chat")
					return
	
	
	#Taunt antispam - see dedicated_config for details
	if cfg.TAUNT_ANTISPAM:
		for kw in cfg.TAUNT_KEYWORDS:
			if kw in message.lower():
				worms[wormID].spammed += 1
				io.privateMsg(wormID, cfg.TAUNT_ANTISPAM_WARNING)
				if worms[wormID].spammed > cfg.TAUNT_ANTISPAM_LIMIT:
					if cfg.TAUNT_ANTISPAM ==1:
						io.kickWorm(wormID, "spamming")
					elif cfg.TAUNT_ANTISPAM ==2:
						kickWithTime(wormID, "spamming")
					return
	
	#Commands
	ret = None
	aret = None
	if worms[wormID].isAdmin and message.startswith(cfg.ADMIN_PREFIX):
		aret = cmds.parseAdminCommand(wormID,message)
	if message.startswith(cfg.USER_PREFIX):
		ret = cmds.parseUserCommand(wormID,message)
	
	if ret == "map":
		updateVotes(send_msg = ("map",))
	elif ret == "mod":
		updateVotes(send_msg = ("mod",))
	elif ret == "teams":
		updateVotes(send_msg = ("teams",))
	elif ret == "kick":			#Don't broadcast voting status if voted for kick
		updateVotes(send_msg= () )


#Detect non-allowed tags in nicknames and messages
#NOTE: As the tags can contain extra junk we must check for both plain tag and tag with junk (e.g. <br test>) 
# - but not for <brtest> which is invalid and doesn't result in a newline
def detectFormattingTags(teststr):

	ret=False
	lteststr = teststr.lower().strip()
	for a in cfg.ANTI_IMPERSONATION_TAGS:
		if ("<" + a + ">") in lteststr or ( ("<" + a + " ") in lteststr and lteststr.find(">") > lteststr.find("<" + a + " " ) ):
			ret=True
			break
	
	return ret



###########################################################
#VOTING FUNCTIONS
###########################################################
def updateVotes(send_msg=()):
	global gameState, oldGameState
	global vote_locked
	global worms, availablePresets
	
	votedMaps = {}
	votedPresets = {}
	teams_voted = 0
	teams_ready = False
	gametype_old = io.getGameType()
	
	#Reset kick vote counters to zero
	for w in worms.keys():
		worms[w].resetKickVotes()
	
	#Count all votes
	for w in worms.keys():
		#Count map votes
		if worms[w].votedMap:
			if not worms[w].votedMap in votedMaps.keys():
				votedMaps[worms[w].votedMap] = 1
			else:
				votedMaps[worms[w].votedMap] += 1
		#Count mod (preset) votes
		if worms[w].votedPreset:
			if not worms[w].votedPreset in votedPresets.keys():
				votedPresets[worms[w].votedPreset] = 1
			else:
				votedPresets[worms[w].votedPreset] += 1
		#Count kick votes for each player
		if worms[w].votedKick in worms.keys():
			worms[worms[w].votedKick].kickVoted += 1
		else:
			worms[w].votedKick = None	#If player is not on the server, remove vote
		#Count team votes	
		if worms[w].votedTeams:
			teams_voted += 1
	
	#Find most voted ones
	mostVotedMap = ""
	mostVotedPreset = ""
	for m in votedMaps.keys():
		if not mostVotedMap:
			mostVotedMap = m
		else:
			if votedMaps[m] > votedMaps[mostVotedMap]:
				mostVotedMap = m
	for p in votedPresets.keys():
		if not mostVotedPreset:
			mostVotedPreset = p
		else:
			if votedPresets[p] > votedPresets[mostVotedPreset]:
				mostVotedPreset = p
	
	#Announce voting status
	if "map" in send_msg and mostVotedMap:
		io.chatMsg("Most voted map: "+mostVotedMap)
	if "mod" in send_msg and mostVotedPreset:
		io.chatMsg("Most voted preset: "+mostVotedPreset)
	
	#Check teamgame votes
	if len(worms) != 0 and (float(teams_voted)/float(len(worms)) )*100 >= cfg.VOTING_PERCENT and len(worms) >= cfg.MIN_PLAYERS_TEAMS:
		teams_ready = True
	else:
		teams_ready = False 
	
	#Announce team voting status
	if "teams" in send_msg and teams_voted != 0:
		if teams_ready:
			io.chatMsg("Team voting status: Looks like the next game will be Team Deathmatch!")
		elif len(worms) < cfg.MIN_PLAYERS_TEAMS:
			io.chatMsg("Team voting status: Not enough players for team game (" + str(cfg.MIN_PLAYERS_TEAMS) + " is minimum)")
		elif (float(teams_voted)/float(len(worms)))*100 < cfg.VOTING_PERCENT:
			io.chatMsg("Team voting status: Not enough votes for team game yet")
			
	#Check kick votes
	for w in worms.keys():
		if (float(worms[w].kickVoted)/float(len(worms)))*100 > cfg.VOTING_PERCENT:
			kickWithTime(w, "other players voted to kick you")
	
	#If we are safely in lobby, load settings
	if gameState == GAME_LOBBY and not vote_locked:
		#Set map and preset
		if mostVotedMap:
			loadMap(mostVotedMap)
		if mostVotedPreset:
			loadPreset(mostVotedPreset)
		#Set team game
		if teams_ready:
			if io.getGameType() == 0:
				io.setvar("GameOptions.GameInfo.GameType", 1)
				setupTeams()
		else:
			io.setvar("GameOptions.GameInfo.GameType", 0)
	
	#Announce team game status if 1) it has not been announced and 2) game type has been changed
	if not "teams" in send_msg and gametype_old != io.getGameType():
		if teams_ready:
			io.chatMsg("Team voting status: Looks like the next game will be Team Deathmatch!")
		elif len(worms) < cfg.MIN_PLAYERS_TEAMS:
			io.chatMsg("Team voting status: Not enough players for team game (" + str(cfg.MIN_PLAYERS_TEAMS) + " is minimum)")
		elif (float(teams_voted)/float(len(worms)))*100 < cfg.VOTING_PERCENT:
			io.chatMsg("Team voting status: Not enough votes for team game")
	
	return (mostVotedMap, mostVotedPreset, int(teams_ready))
		
	
#Clear votes ##NOTE: Team votes only if configured	#NOTE: Not kick votes!
def clearVotes():
	global worms
	
	for w in worms.keys():
		worms[w].resetVotes()
		if cfg.AUTOCLEAR_TEAM_VOTES:
			worms[w].resetTeamVotes()


###########################################################
#END OF VOTING FUNCTIONS
###########################################################


def parseWormDied(sig):
	global worms

	deaderID = int(sig[1])
	killerID = int(sig[2])
	worms[deaderID].Lives -= 1
	worms[deaderID].Alive = False

	if not cfg.RANKING:
		return

	try:
		f = open(io.getWriteFullFileName(cfg.RANKING_FILE),"a")
		if not killerID in io.getComputerWormList():
			try:
				portalocker.lock(f, portalocker.LOCK_EX)
			except:
				pass
			f.write( time.strftime("%Y-%m-%d %H:%M:%S") + "\t" + worms[deaderID].Name + "\t" + worms[killerID].Name + "\n" )
		f.close()
	except IOError:
		io.msg("ERROR: Unable to open ranking file: " + cfg.RANKING_FILE)

	if not killerID in io.getComputerWormList():
		if deaderID == killerID:
			try:
				ranking.rank[worms[killerID].Name][2] += 1
			except KeyError:
				ranking.rank[worms[killerID].Name] = [0,0,1,len(ranking.rank)+1]
		else:
			try:
				ranking.rank[worms[killerID].Name][0] += 1
			except KeyError:
				ranking.rank[worms[killerID].Name] = [1,0,0,len(ranking.rank)+1]
	if not deaderID in io.getComputerWormList():
		try:
			ranking.rank[worms[deaderID].Name][1] += 1
		except KeyError:
			ranking.rank[worms[deaderID].Name] = [0,1,0,len(ranking.rank)+1]

def parseWormSpawned(sig):
	global worms

	wormID = int(sig[1])
	worms[wormID].Alive = True

def parseCustom(sig):
	if not cmds.parseAdminCommand(-1, "%s%s" % (cfg.ADMIN_PREFIX, str(sig[1:]))):
		cmds.parseUserCommand(-1, "%s%s" % (cfg.USER_PREFIX, str(sig[1:])))




## Preset loading functions ##
def initPresets():
	global availablePresets

	# Reset - incase we get called a second time
	availablePresets = []
	
	
	if len(cfg.PRESETS) == 0:
		for f in presetcfg.MOD_PRESETS.keys():
			availablePresets.append(f)
	else:
		for p in cfg.PRESETS:
			if p not in presetcfg.MOD_PRESETS.keys():
				io.messageLog("Preset error - %s not found in preset table." % p, io.LOG_WARN)
			else:
				if not p in availablePresets:
					availablePresets.append(p)
		
	if (len(availablePresets) == 0):
		io.messageLog("There are no presets available - nothing to do. Exiting.",io.LOG_CRITICAL)
		exit()


## Control functions

def average(a):
	r = 0
	for i in a:
		r += i
	return r / len(a)

def checkMaxPing():
	
	global worms
	for f in worms.keys():
		if worms[f].iID == -1 or not worms[f].Alive:
			continue
		ping = int(io.getWormPing(worms[f].iID))
		if ping > 0:
			worms[f].Ping.insert( 0, ping )
			if len(worms[f].Ping) > 25:
				worms[f].Ping.pop()
				if average(worms[f].Ping) > cfg.MAX_PING:
					io.kickWorm( worms[f].iID, "your ping is " + str(average(worms[f].Ping)) + " allowed is " + str(cfg.MAX_PING) )

					
#Ban temporarily
def kickWithTime(wid, reason = ""):
	global worms, kickedUsers
	
	wip = worms[wid].Ip
	kickedUsers[wip] = time.time() + 60*cfg.VOTING_KICK_TIME
	io.kickWorm(wid, reason)



#Preset loader
def loadPreset(name):
	
	loadDefaultPreset()
	
	#Other settings first
	for k in presetcfg.MOD_PRESETS[name].keys():
		if k != "WEAPONFILE":
			io.setvar(k, presetcfg.MOD_PRESETS[name][k])
	
	#Weapon bans
	try:
		weaponBans = presetcfg.MOD_PRESETS[name]["WEAPONFILE"]
		modName = io.getVar("GameOptions.GameInfo.ModName")
		io.setvar( "GameServer.WeaponRestrictionsFile", "cfg/presets/" + modName + "/" + weaponBans + ".wps" )
	except KeyError:
		pass
	
#Map loader (pretty useless...)
def loadMap(name):
	io.setvar("GameOptions.GameInfo.LevelName", name)
	
	
def loadDefaultPreset():
	pass




lobbyWaitBeforeGame = time.time() + cfg.WAIT_BEFORE_GAME
lobbyWaitAfterGame = time.time()
lobbyWaitGeneral = time.time() + cfg.WAIT_BEFORE_SPAMMING_TOO_FEW_PLAYERS_MESSAGE
lobbyEnoughPlayers = False
oldGameState = GAME_LOBBY

def controlHandlerDefault():

	global worms, gameState, lobbyChangePresetTimeout, lobbyWaitBeforeGame, lobbyWaitAfterGame
	global lobbyWaitGeneral, lobbyEnoughPlayers, oldGameState, scriptPaused, sentStartGame
	global currentAutocyclePreset, currentAutocycleMap
	global vote_locked, shuffle_counter
	
	if scriptPaused:
		return

	curTime = time.time()
	
	if gameState == GAME_LOBBY:

		# Do not check ping in lobby - it's wrong

		if oldGameState != GAME_LOBBY:
			lobbyEnoughPlayers = False # reset the state
			lobbyWaitGeneral = curTime + cfg.WAIT_BEFORE_SPAMMING_TOO_FEW_PLAYERS_MESSAGE
			lobbyWaitAfterGame = curTime
			if oldGameState == GAME_PLAYING:
				lobbyWaitAfterGame = curTime + cfg.WAIT_AFTER_GAME
			
			#Reset shuffle counter
			shuffle_counter = 0
			
			#Update votes when game ends
			updateResult = updateVotes(send_msg=("map","mod","teams"))
			#Autocycle if not voted
			#Advance autocycle counters first
			if not updateResult[0]:
				currentAutocycleMap += 1
				if currentAutocycleMap >= len(cfg.LEVELS):
					currentAutocycleMap = 0
			if not updateResult[1]:
				currentAutocyclePreset += 1
				if currentAutocyclePreset >= len(cfg.PRESETS):
					currentAutocyclePreset = 0
			##Map
			if not updateResult[0]:
				io.setvar("GameOptions.GameInfo.LevelName", cfg.LEVELS[currentAutocycleMap])	
			##Mod (preset)
			if not updateResult[1]:
				loadPreset(cfg.PRESETS[currentAutocyclePreset])
			
			#Check if teams are balanced
			##This should be done because teams may become uneven if people leave during game and BALANCE_TEAMS_INGAME is not set
			if io.getGameType() == 1:
				io.chatMsg("Checking if teams are even...")
				balanceTeams(bmsg="game ended")
		
		if lobbyWaitAfterGame <= curTime:

			if not lobbyEnoughPlayers and lobbyWaitGeneral <= curTime:
				lobbyWaitGeneral = curTime + cfg.WAIT_BEFORE_SPAMMING_TOO_FEW_PLAYERS_MESSAGE
				io.chatMsg(cfg.TOO_FEW_PLAYERS_MESSAGE)

			if not lobbyEnoughPlayers and len(worms) >= cfg.MIN_PLAYERS: # Enough players already - start game
				lobbyEnoughPlayers = True
				io.chatMsg(cfg.WAIT_BEFORE_GAME_MESSAGE)
				lobbyWaitBeforeGame = curTime + cfg.WAIT_BEFORE_GAME

			if lobbyEnoughPlayers and len(worms) < cfg.MIN_PLAYERS: # Some players left when game not yet started
				lobbyEnoughPlayers = False
				io.chatMsg(cfg.TOO_FEW_PLAYERS_MESSAGE)

			if lobbyEnoughPlayers and not sentStartGame:

				if lobbyWaitBeforeGame <= curTime: # Start the game
					
					#Starting game...		##NOTE Removed team check from here - teams should be assigned before the round starts
					if io.startGame():
						if cfg.ALLOW_TEAM_CHANGE and len(worms) >= cfg.MIN_PLAYERS_TEAMS:
							io.chatMsg(cfg.TEAM_CHANGE_MESSAGE)
						sentStartGame = True
						vote_locked = True	#Lock vote-able settings when starting
						clearVotes()		#Clear votes when starting
					else:
						io.messageLog("Game could not be started", io.LOG_ERROR)		#Log these errors!
						io.chatMsg("Game could not be started")
						oldGameState == GAME_PLAYING # hack that it resets at next control handler call
				
	
	
	if gameState == GAME_WEAPONS:

		# if we allow empty games, ignore this check
		if len(worms) < cfg.MIN_PLAYERS and not io.getVar("GameOptions.GameInfo.AllowEmptyGames"): # Some players left when game not yet started
			io.chatMsg("Too few players -> back to lobby")
			io.gotoLobby()
			sentStartGame = False

	if gameState == GAME_PLAYING:
		
		if cfg.PING_CHECK:
			checkMaxPing()
	
	#Unlock voting when the game is safely running
	if (gameState == GAME_WEAPONS or gameState == GAME_PLAYING) and oldGameState != GAME_LOBBY and vote_locked:
		vote_locked = False
	
	
controlHandler = controlHandlerDefault

