import discord, math

PREFIX = "%"
ADMIN_ID = [537091937271021580, 411280275633340416]
MAIN_CHAT_ID = 777670580861665333
MATCH_RESULT_CHAN = 785187900772843520
DATA_DIR = "C:\\Users\\Jace\\Desktop\\OSDLBot\\Data"
MAIN_DIR = "C:\\Users\\Jace\\Desktop\\OSDLBot"
multi_url_format = "https://osu.ppy.sh/community/matches/"
LOGO_URL = "https://i.imgur.com/BnrMcNG.jpg"

##ELO FUNCTION##
ELO_WEIGHT = 50
C_VALUE = 2.5

ELO_FUNCTION = lambda  win_ratio,old_elo,op_old_elo: (ELO_WEIGHT * ((.5 * (((C_VALUE*2) * win_ratio)-C_VALUE) / math.sqrt((((2*C_VALUE) * win_ratio)-C_VALUE)**2 + 1) + .5) - (10**(old_elo/400.0)/ (10**(op_old_elo/400.0) + 10**(old_elo/400.0)))))



########## MAP POOLS ##############
pools = {} #dicts of dicts (lol)


#Rounds 1-2
pools["round12"] = {
"BO":5,
"nm1":2443183,
"nm2":2257328,
"nm3":2691257,
"hd1":69102,
"hd2":2304350,
"hr1":1525195,
"hr2":1945604,
"dt1":1560857,
"dt2":2254089,
"fm1":84445,
"fm2":874945,
"tb":1684705
}

pools['test'] = {
"BO":3,
"nm1":855948,
"nm2":785897,
"nm3":2020258
}

CURRENT_POOL = pools["test"]

###### Help Embed ######
HELP_EMBED = discord.Embed(title="OSDLBot Commands", description=f"Prefix: `{PREFIX}`")

HELP_EMBED.add_field(name="`help`",value="Sends a list of commands, duh...",inline=False)
