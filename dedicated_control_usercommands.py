#!/usr/bin/python -u
# Dedicated Control handler script for OpenLieroX
# (http://openlierox.sourceforge.net)

import time
import os
import sys
import threading
import traceback
import math

import dedicated_control_io as io
import dedicated_control_ranking as ranking
import dedicated_control_handler as hnd
import dedicated_control_presets as presetcfg


#User help
def userCommandHelp(wormid):
	if cfg.RANKING:
		io.privateMsg(wormid, "%stoprank - display the best players" % cfg.USER_PREFIX )
		io.privateMsg(wormid, "%srank [name] - display your or other player rank" % cfg.USER_PREFIX )
		io.privateMsg(wormid, "%sranktotal - display the number of players in the ranking" % cfg.USER_PREFIX )
	if cfg.VOTING:
		io.privateMsg(wormid, "%smod presetName - vote for a mod preset" % cfg.USER_PREFIX)
		io.privateMsg(wormid, "%smap mapName - vote for a map, old style" % cfg.USER_PREFIX)
		io.privateMsg(wormid, "%sm mapCode - quick map voting, try %smaphelp for a list of options" % (cfg.USER_PREFIX, cfg.USER_PREFIX) )
	if cfg.KICK_VOTING:
		io.privateMsg(wormid, "%skick playerID - vote to kick player" % cfg.USER_PREFIX)
	if cfg.TEAMGAMES_VOTING:
		io.privateMsg(wormid, "%steams/%snoteams - vote for team game" % (cfg.USER_PREFIX, cfg.USER_PREFIX))
	if cfg.TEAM_SHUFFLE:
		io.privateMsg(wormid, "%sshuffle - randomize teams" % cfg.USER_PREFIX)
	if cfg.ALLOW_TEAM_CHANGE:
		t_msg = "%steam [b/r" % (cfg.USER_PREFIX)
		if cfg.MAX_TEAMS >= 3:
			t_msg += "/g"
		if cfg.MAX_TEAMS >= 4:
			t_msg += "/y"
		t_msg += "] - set your team"
		io.privateMsg(wormid, t_msg)
		
#Quick map voting help
def mapHelp(wormid):
	
	helpMsg = ""
	tmp = ""
	
	io.privateMsg(wormid, "Map voting shortcuts to use with %sm:" % cfg.USER_PREFIX)
	if len(presetcfg.MAP_SHORTCUTS) == 0:
		io.privateMsg(wormid, "<not available>")
	else:
		for k in presetcfg.MAP_SHORTCUTS.keys():
			tmp = k + " - " + presetcfg.MAP_SHORTCUTS[k].replace(".lxl", "") + " // "
			helpMsg = helpMsg + tmp
		io.privateMsg(wormid, helpMsg)
	

	
#News
def controlUpdatesList(wormid):
	if cfg.CONTROL_UPDATES == 1:
		for updateEntry in cfg.CONTROL_UPDATES_LIST:
			io.privateMsg(wormid, updateEntry)
	else:
		io.privateMsg(wormid, "No recent news")
		
#User interface
def parseUserCommand(wormid,message):

	try: # Do not check on msg size or anything, exception handling is further down
		
		cmd = message.split(" ")[0]
		cmd = cmd.replace(cfg.USER_PREFIX,"",1).lower() #Remove the prefix
		
		if cfg.USERCOMMAND_LOGGING:
			if wormid >= 0:
				io.messageLog("%i:%s issued %s" % (wormid,hnd.worms[wormid].Name,cmd.replace(cfg.USER_PREFIX,"",1)),io.LOG_USRCMD)
			else:
				io.messageLog("ded admin issued %s" % cmd, io.LOG_USRCMD)
			
		# Unnecesary to split multiple times, this saves CPU.
		params = message.split(" ")[1:]
		
		if cmd == "help":
			userCommandHelp(wormid)
			return "none"
		
		elif cmd == "maphelp":
			mapHelp(wormid)
			return "none"
		
		#News feed (previously called updates, hence the command name...)
		elif cmd == "news":
			controlUpdatesList(wormid)
			return "none"
		
		#Teamchanges...
		elif cfg.ALLOW_TEAM_CHANGE and cmd == "team":
			#Not team deathmatch
			if io.getGameType() != 1:
				io.privateMsg(wormid, "Game type is not team deathmatch")
			#Not in lobby
			elif hnd.gameState != hnd.GAME_LOBBY:
				io.privateMsg(wormid, "You can only change team in lobby")
			#No team specified	
			elif not params:
				io.privateMsg(wormid, "You need to specify a team" )
			#Everything OK
			else:
				if params[0].lower() == "blue" or params[0].lower() == "b":
					hnd.setTeam(wormid, 0)
				elif params[0].lower() == "red" or params[0].lower() == "r":
					hnd.setTeam(wormid, 1)
				elif ( params[0].lower() == "green" or params[0].lower() == "g" ) and cfg.MAX_TEAMS >= 3:
					hnd.setTeam(wormid, 2)
				elif ( params[0].lower() == "yellow" or params[0].lower() == "y" ) and cfg.MAX_TEAMS >= 4:
					hnd.setTeam(wormid, 3)
				else:
					io.privateMsg(wormid, "Invalid team")

		elif cfg.RANKING and cmd in ("rank", "toprank", "ranktotal"):
			if cmd == "toprank":
				ranking.firstRank(wormid)
			if cmd == "rank":
				if wormid in hnd.worms:
					wormName = hnd.worms[wormid].Name
					if params:
						wormName = " ".join(params).replace("\"", "\'\'")	#Convert double quotes to prevent annoyance
					ranking.myRank(wormName, wormid)
			if cmd == "ranktotal":
				if cfg.NAME_CHECK_ACTION == 1 and cfg.HANDLE_RANDOMS_IN_RANKTOTAL:
					tmp_rankplayers = sortRankPlayers(randoms=0, random_max = cfg.NAME_CHECK_RANDOM)
					tmp_rankrandoms = sortRankPlayers(randoms=1, random_max = cfg.NAME_CHECK_RANDOM)
					io.privateMsg(wormid, "There are " + str(len(tmp_rankplayers)) + " players and " + str(len(tmp_rankrandoms)) + " unnamed players in the ranking.")
				else:
					io.privateMsg(wormid, "There are " + str(len(ranking.rank)) + " players in the ranking.")
			return "none"
		
		elif cfg.KICK_VOTING and cmd == "kick":
			try:
				kicked = int( params[0] )
			except ValueError:
				io.privateMsg(wormid, "Invalid player ID")
			
			if not kicked in hnd.worms.keys():
				io.privateMsg(wormid, "Invalid player ID")
			else:
				hnd.worms[wormid].votedKick = kicked
				io.chatMsg(hnd.worms[wormid].getCleanName() + " votes to kick " + hnd.worms[kicked].getCleanName() )	#NOTE: We are using the real name here - so it should be cleaned
				return "kick"
		
		elif cfg.VOTING and cmd in ("mod", "map", "m"):
		
			if cmd == "mod":
				
				#NEW: only presets
				preset = -1
				for p in range(len(hnd.availablePresets)):
					if hnd.availablePresets[p].lower().find(params[0].lower()) != -1:
						preset = p
						break
				if preset != -1:
					hnd.worms[wormid].votedPreset = hnd.availablePresets[preset]
					io.privateMsg(wormid, "You voted for %s" % hnd.worms[wormid].votedPreset)	#Send these as private msgs to reduce spam
					return "mod"
				else:
					io.privateMsg(wormid, "Invalid preset, available presets: " + ", ".join(hnd.availablePresets) )
				
			
			if cmd == "map":
				level = ""
				for l in io.listMaps():
					if l.lower().find(" ".join(params[0:]).lower()) != -1:
						level = l
						break
				if level != "":
					hnd.worms[wormid].votedMap = level
					io.privateMsg(wormid, "You voted for %s" % hnd.worms[wormid].votedMap)
					return "map"
				else:
					io.privateMsg(wormid, "Invalid map, available maps: " + ", ".join(io.listMaps()))	#NOTE: This generates a very spammy message...
			
			#Quick map voting
			if cmd == "m":
				if not params:
					io.privateMsg(wormid, "No map specified, try %smaphelp for a list of options" % cfg.USER_PREFIX)
				elif params[0].lower() in presetcfg.MAP_SHORTCUTS.keys():
					hnd.worms[wormid].votedMap = presetcfg.MAP_SHORTCUTS[params[0].lower()]
					io.privateMsg(wormid, "You voted for %s" % hnd.worms[wormid].votedMap)
					return "map"
				else:
					io.privateMsg(wormid, "Invalid map option, try %smaphelp for a list of available options" % cfg.USER_PREFIX)
					
					
			
		elif cfg.TEAMGAMES_VOTING and (cmd == "teams" or cmd == "noteams"):
			if cmd == "teams":
				hnd.worms[wormid].votedTeams = 1
				io.privateMsg(wormid, "You voted for team game!")
			elif cmd == "noteams":
				hnd.worms[wormid].votedTeams = 0
				io.privateMsg(wormid, "You voted for deathmatch!")
			return "teams"
		
		#Team shuffling
		elif cmd == "shuffle" and cfg.TEAM_SHUFFLE:
			#Not TDM
			if io.getGameType() != 1:
				io.privateMsg(wormid, "Not TDM - cannot shuffle")
			#Not in lobby 
			elif hnd.gameState != hnd.GAME_LOBBY:
				io.privateMsg(wormid, "Cannot shuffle when not in lobby")
			#Too many shuffles
			elif hnd.shuffle_counter >= cfg.TEAM_SHUFFLE:
				io.privateMsg(wormid, "Shuffle limit already reached")
			else:
				hnd.shuffleTeams()
			#Not in lobby
			
		
		#TEST: Use this to check team status...
		#elif cfg.TEAMCHANGE_LOGGING and cmd == "teamtest":
		#	io.messageLog("TEAMTEST: teamtest called by player " + str(wormid), io.LOG_INFO)
		#	teamtestresult = str(hnd.getNumberWormsInAllTeams()).replace("[","").replace("]","").replace(","," ")
		#	io.privateMsg(wormid, "Team status is "+teamtestresult+" - is this reasonable?")
		#	return "none"
		
		
		else:
			raise Exception, "Invalid user command"
		
	
	except: # All python classes derive from main "Exception", but confused me, this has the same effect.
		if wormid >= 0:
			io.privateMsg(wormid, "Invalid user command - type !help for list of commands")
		if cfg.USERCOMMAND_ERROR_LOGGING:
			io.messageLog(io.formatExceptionInfo(),io.LOG_ERROR) #Helps to fix errors
		return None
	return "none"


#Extra function to separate players with proper name and random players who didn't set their name
#TODO: Move this somewhere else?
#TODO: Make this less ugly??
def sortRankPlayers(randoms, random_max):
	ret = []
	for k in ranking.rank.keys():
		is_random = False
		try:
			if k.startswith("random"):
				#we must handle cases like "randomrandom13" and "random 13" that would pass lstrip() and int()
				tmpstr = k[6:]	#separate first "random"
				for c in tmpstr:
					if c not in ("1","2","3","4","5","6","7","8","9","0"):	#check if non number characters found
						tmpstr = "xxx"
						break
				if tmpstr != "xxx" and int(tmpstr,10) >= 0 and int(tmpstr,10) <= random_max:
					is_random = True
		except: #probably not needed... but we will use it anyway
			pass

		if (is_random and randoms) or (not is_random and not randoms):
				ret.append(k)

	return ret



#Admin help
def adminCommandHelp(wormid):
	io.privateMsg(wormid, "Admin help:")
	io.privateMsg(wormid, "%skick wormID [time] [reason]" % cfg.ADMIN_PREFIX)
	io.privateMsg(wormid, "%sban wormID [reason]" % cfg.ADMIN_PREFIX)
	io.privateMsg(wormid, "%smute wormID" % cfg.ADMIN_PREFIX)
	io.privateMsg(wormid, "%smod presetName" % cfg.ADMIN_PREFIX)
	io.privateMsg(wormid, "%smap mapName" % cfg.ADMIN_PREFIX)
	io.privateMsg(wormid, "%steam wormID teamID (0123 or brgy)" % cfg.ADMIN_PREFIX)
	io.privateMsg(wormid, "%spause - pause ded script" % cfg.ADMIN_PREFIX)
	io.privateMsg(wormid, "%sunpause - resume ded script" % cfg.ADMIN_PREFIX)

# Admin interface
def parseAdminCommand(wormid,message):
	try: # Do not check on msg size or anything, exception handling is further down
		
		cmd = message.split(" ")[0]
		cmd = cmd.replace(cfg.ADMIN_PREFIX,"",1).lower() #Remove the prefix

		if wormid >= 0:
			io.messageLog("%i:%s issued %s" % (wormid,hnd.worms[wormid].Name,cmd.replace(cfg.ADMIN_PREFIX,"",1)),io.LOG_ADMIN)
		else:
			io.messageLog("ded admin issued %s" % cmd, io.LOG_USRCMD)

		# Unnecesary to split multiple times, this saves CPU.
		params = message.split(" ")[1:]

		
		if cmd == "help":
			adminCommandHelp(wormid)
		
		elif cmd == "kick":
			wormid = int(params[0])
			wormIP = io.getWormIP(wormid).split(":")[0]
			if wormIP != "127.0.0.1":
				if len(params) > 1: # Given some reason
					hnd.kickWithTime(wormid, " ".join(params[2:]) )
				else:
					hnd.kickWithTime(wormid)
		
		elif cmd == "ban":
			if len(params) > 1: # Given some reason
				io.banWorm( int( params[0] ), " ".join(params[1:]) )
			else:
				io.banWorm( int( params[0] ) )
		
		elif cmd == "mute":
			io.muteWorm( int( params[0] ) )
		
		
		elif cmd == "mod":
			preset = -1
			for p in range(len(hnd.availablePresets)):
				if hnd.availablePresets[p].lower().find(params[0].lower()) != -1:
					preset = p
					break
			if preset == -1:
				io.privateMsg(wormid,"Invalid preset, available presets: " + ", ".join(hnd.availablePresets))
			else:
				hnd.loadPreset(availablePresets[p])
		
		elif cmd == "map":
			level = ""
			for l in io.listMaps():
				if l.lower().find(" ".join(params[0:]).lower()) != -1:
					level = l
					break
			if level == "":
				io.privateMsg(wormid,"Invalid map, available maps: " + ", ".join(io.listMaps()))
			else:
				hnd.loadMap(l)
		
		elif cmd == "pause":
			io.privateMsg(wormid,"Ded script paused")
			hnd.scriptPaused = True
		elif cmd == "unpause":
			io.privateMsg(wormid,"Ded script continues")
			hnd.scriptPaused = False
		
		else:
			raise Exception, "Invalid admin command"

	except: # All python classes derive from main "Exception", but confused me, this has the same effect.
		if wormid >= 0:
			io.privateMsg(wormid, "Invalid admin command")
		io.messageLog(io.formatExceptionInfo(),io.LOG_ERROR) #Helps to fix errors
		return False
	return True
