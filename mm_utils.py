from osuapi import OsuApi, ReqConnector, enums
import aiohttp, asyncio, sys, os, datetime, pprint, discord, shelve, math
#Graphing
import numpy as np
import matplotlib.pyplot as plt
import OSDLBot_storage
import glicko
from multi_structs import Map, Game, Match, MatchNotFoundError, Player, PlayerNotFound
from dotenv import load_dotenv
load_dotenv()
api = OsuApi(os.environ.get('OSU_API_KEY'), connector=ReqConnector())

class UserNotFoundError(Exception):
    pass

class AlreadyLinkedError(Exception):
    pass

class AlreadyCalcError(Exception):
    pass


async def add_elo_by_discord(discord_id, elo_delta):
    with shelve.open("userdb") as db:
        player = await get_linked(discord_id)
        player.add_elo(elo_delta)
        db[str(discord_id)] = player

async def set_elo_by_discord(discord_id, elo):
    with shelve.open("userdb") as db:
        player = await get_linked(discord_id)
        player.set_elo(elo)
        db[str(discord_id)] = player

#Generate a leaderboard embed using the OSDL ELO rankings
async def leaderboard(author_id, page=1, length=10):
    with shelve.open("userdb") as db:
        #Create a list of player objs stored in the dict
        players = [db[id] for id in db.keys()]
    
    #Sort by elo
    players.sort(key=lambda p: p.elo, reverse=True)

    if len(players)%length == 0:
        #edge cases (i.e. numplayers 20 length 10, we need 2 pages not 3)
        #this is probably bad way to handle it and im failing at easy math lol
        max_page = (len(players)//(length))
    else:
        max_page = (len(players)//(length)) +1

    if page>max_page:
        #Cap page request at final page
        page = max_page

    author_model = await get_linked(author_id)

    #Make description text
    desc = f"Rank     Name (Osu) [Page {page}/{max_page}]\n"
    #Find index range for requested page
    start = (page-1)*length
    end = min(start+length,len(players))
    for p in range(start,end):
        #Add listing to desc for each player
        ply = players[p]
        ply.update()
        desc+= f"{p+1:<4}➤   # {ply.username:<15} ELO: {round(ply.elo)}\n"
    desc+="____________________________________\n"
    
    #If author is a Player, show their rank in footer
    if author_model:
        desc+=f"Your Rank: {await get_rank(author_model.id,sorted=players):<15} ELO: {round(author_model.elo)}"

    #Instatiate Embed
    emb = discord.Embed(title="OSDL 1v1 Leaderboard",description=f"```{desc}```")
    #Logo
    emb.set_thumbnail(url=OSDLBot_storage.LOGO_URL)
        
    return emb
    
async def get_rank(osu_id, sorted=None):
    if not sorted:
        with shelve.open("userdb") as db:
            #Create a list of player objs stored in the dict
            players = [db[id] for id in db.keys()]
        players.sort(key=lambda p: p.elo)
    else:
        players = sorted
    for i in range(len(players)):
        if players[i].id == osu_id:
            return i+1
    return None

#Return the Player object stored in the dictionary with the given ID, or None if not found
async def find_osu_player(osu_user_id):
    with shelve.open("userdb") as db:
        #Create a list of player objs stored in the dict
        players = [db[id] for id in db.keys()]
    
    for player in players:
        if osu_user_id == player.id:
            return player
    return None

#Create a Player object for a given user id and link it to a discord id
#Stores in userdb shelve dictionary
async def link_account(osu_user,discord_id):
    #Don't allow user to overwrite if account already linked
    with shelve.open("userdb") as db:
        if str(discord_id) in db.keys():
            raise AlreadyLinkedError()

    #Attempt to get the osu user with this username/id from the API
    try:
        user = api.get_user(osu_user)[0]
    except:
        raise UserNotFoundError()
    
    #Check if the osu user id attempting to be linked already exists in the db
    in_storage = await find_osu_player(user.user_id)
    if in_storage:
        #Player obj with this id already exists; use existing
        player = in_storage
    else:
        #Create a new Player obj for this id
        player = Player(user.user_id,discord_id, new=True)

    #Store object in a db dict of discord_id:Player
    with shelve.open("userdb") as db:
        db[str(discord_id)] = player
    return player

#Returns the player model associated with a Discord ID
async def get_linked(discord_id):
    with shelve.open("userdb") as db:
        if str(discord_id) not in db.keys():
            return None
        player = db[str(discord_id)]
    
    #Update the Player object
    player.update()
    return player

#Returns an embed containing information about the Player linked to a discord or osu id
async def get_linked_embed(discord_id=0,osu_user=0, pfp_url=""):
    if discord_id>0:
        player = await get_linked(discord_id)
    elif osu_user>0:
        player = await find_osu_player(osu_user)

    if player is None:
        return discord.Embed(description="Could not find a linked account for this user! Use `%link [username]` to link an osu! account to Discord.")

    player_desc = f"▸ Rank: #{player.rank} ({player.country}#{player.rank_c})\n"
    player_desc+= f"▸ Accuracy: {player.acc}%\n"
    player_desc+= f"▸ ELO: {round(player.elo)}\n"
    player_desc+= f"▸ Playcount: {player.plays}"

    player_embed = discord.Embed(title=f"User profile for {player.username}",url=f"https://osu.ppy.sh/users/{player.id}",description=player_desc)
    player_embed.set_footer(text="Design definitely not stolen from owobot :^)", icon_url="https://cdn.discordapp.com/attachments/545410384132309006/792908237023871006/bruh.jpg")

    if len(pfp_url)>0:
        player_embed.set_thumbnail(url=pfp_url)
    else:
        player_embed.set_thumbnail(url=OSDLBot_storage.LOGO_URL)
    return player_embed

async def reset_link(discord_id, osu_user_id=0, breaking=False):
    with shelve.open("userdb") as db:
        if str(discord_id) in db.keys():
            del db[str(discord_id)]
    
    if breaking:
        return None
    
    plr = await link_account(osu_user_id,discord_id)
    return plr

async def get_osu_user_id(username):
    try:
        return await api.get_user(username)[0].user_id
    except:
        raise PlayerNotFound()

#Process a 1v1 league match from an int id
#Recalculate ELOs of both players involved in the match
#Send an embed containing match information to the #match-results channel
async def process_match(id,override=False):
    #check if match has already been processed
    if not override:
        with open("Data\\calculated.txt","r") as f:
            if str(id) in f.read().splitlines():
                raise AlreadyCalcError()

    try:
        match = Match(id)
        pool = OSDLBot_storage.CURRENT_POOL
        match.strip_nonpool(pool)
        #Gets dict of osu_id:numwins for this match
        player_wins = match.calc_round_wins()
        num_rounds = len(match.round_list)
    except PlayerNotFound:
        return discord.Embed(description="Error, could not find linked account for all players in match. Both players must be in server with linked accounts using `%link [username]`")

    #####ELO#####
    player_changes = {}#dict of ELO changes Player:delta

    #Get players, win ratios, and old elos
    p1 = await find_osu_player(match.players[0])
    p2 = await find_osu_player(match.players[1])
    w1 = player_wins[p1.id]/num_rounds
    w2 = player_wins[p2.id]/num_rounds

    env = Glicko2()
    elo1 = env.rate(r1, [(Glicko.WIN if w1>w2 else LOSS, p2.elo)])
    elo2 = env.rate(r2, [(Glicko.WIN if w2>w1 else LOSS< p1.elo)])
    p1.elo = elo1
    p2.elo = elo2

    #Log match as recorded
    if not override:
        with open("Data\\calculated.txt","a") as f:
            f.write(str(id)+"\n")

    #Embed creation
    emb = discord.Embed(title=f"{match.title}",description="**Results:**")
    emb.set_thumbnail(url=OSDLBot_storage.LOGO_URL)
    emb.set_footer(text=f"Played on {match.time_played}")

    #Create field for each player
    for player in player_changes.keys():
        try:
            #check + or - elo
            change = round(player_changes[player])
            if change<0:
                change_str = str(change)
            else:
                change_str = f"+{change}"
            emb.add_field(name=f"{player.username} ({change_str})",value=f"Points: {player_wins[player.id]}",inline=False)
        except Exception as e:
            emb.add_field(name="Error on one of the players",value=e,inline=False)
    
    return emb
