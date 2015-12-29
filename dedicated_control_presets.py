#!/usr/bin/python -u


#Preset configuration table.

MOD_PRESETS = {

"Rifles":	{	"GameOptions.GameInfo.ModName": 	"Classic",
				"GameOptions.GameInfo.LoadingTime":	"20",
				
				"WEAPONFILE":		"Rifle only",
				
				},


"Classic":	{	"GameOptions.GameInfo.ModName": 	"Classic",
				"GameOptions.GameInfo.LoadingTime":	"100",
				
				"WEAPONFILE":		"Restricted 100lt",
				
				},
				
			
"Mortars":	{	"GameOptions.GameInfo.ModName":		"MW 1.0",
			"GameOptions.GameInfo.LoadingTime":	"20",

			"WEAPONFILE":		"Mortar Only",	
				
				},

"Xmas":		{	"GameOptions.GameInfo.ModName":	"LieroX-Mas v1.1",
			"GameOptions.GameInfo.LoadingTime":	"75",

				},


}


#Short names for quick map voting (!m)

MAP_SHORTCUTS = {

	"lf":			"Liero Factory.lxl",
	"lfr":			"LieroFactory(Revisited).lxl",
	"lfm":			"LieroFactory_Maintenance.lxl",
	"lamda":		"LamdaBunker.lxl",
	"razlamda":		"Lamda_bunker_(Razvisited).lxl",
	"fossil":		"FossilFacility.lxl",
	"fossil2":		"Fossil Facility 2nd section.lxl",
	"jukke":		"JukkeDome.lxl",
	"jb":			"JailBreak.lxl",
	"complex":		"Complex.lxl",	

	}

# Some other examples...

OTHER_MAP_SHORTCUTS = {
	
	"cs":			"CastleStrike.lxl",
	"castle":		"CastleStrike.lxl",
	"blat":			"Blat Arena.lxl",
	"poo":			"Poo Arena.lxl",
	"wm":			"wormmountain.lxl",
	"tetris":		"Tetrisv2.lxl",
	
}
