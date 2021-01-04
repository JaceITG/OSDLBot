from osuapi import OsuApi, ReqConnector, enums
import aiohttp, asyncio, sys, os, datetime, pprint, discord, shelve, math
import OSDLBot_storage
from multi_structs import Map, Game, Match, MatchNotFoundError, Player, PlayerNotFound
api = OsuApi(OSDLBot_storage.OSU_API_KEY, connector=ReqConnector())

class UserNotFoundError(Exception):
    pass

class AlreadyLinkedError(Exception):
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
    try:
        with shelve.open("userdb") as db:
            player = db[str(discord_id)]
            #Update the Player object and restore in database
            player.update()
            db[str(discord_id)] = player
        return player
    except:
        return None

#Returns an embed containing information about the Player linked to a discord id
async def get_linked_embed(discord_id, pfp_url=""):
    
    player = await get_linked(discord_id)

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
    return player_embed

async def reset_link(discord_id, osu_user_id):
    with shelve.open("userdb") as db:
        if str(discord_id) in db.keys():
            del db[str(discord_id)]
    
    plr = await link_account(osu_user_id,discord_id)
    return plr

async def elo_formula(win_ratio, old_elo, op_old_elo):
    return (OSDLBot_storage.ELO_WEIGHT * ((.5 * ((6 * win_ratio)-OSDLBot_storage.C_VALUE) / math.sqrt(((6 * win_ratio)-OSDLBot_storage.C_VALUE)**2 + 1) + .5) - (10**(old_elo/400.0)/ (10**(op_old_elo/400.0) + 10**(old_elo/400.0)))))

#Process a 1v1 league match from an int id
#Recalculate ELOs of both players involved in the match
#Send an embed containing match information to the #match-results channel
async def process_match(id):
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
    old_elos = [p1.elo,p2.elo]
    win_ratios = []
    win_ratios.append(player_wins[p1.id]/num_rounds)
    win_ratios.append(player_wins[p2.id]/num_rounds)

    #First player
    delta = await elo_formula(win_ratios[0],old_elos[0],old_elos[1])
    print(f"P1 Elo delta with {win_ratios[0]},{old_elos[0]},{old_elos[1]} = {delta}")
    player_changes[p1] = delta
    p1.add_elo(delta)

    delta2 = await elo_formula(win_ratios[1],old_elos[1],old_elos[0])
    print(f"P2 Elo delta with {win_ratios[1]},{old_elos[1]},{old_elos[0]} = {delta2}")
    player_changes[p2] = delta2
    p2.add_elo(delta2)



    

    #Embed creation
    emb = discord.Embed(title=f"Match ID {id}",description="**Results:**")
    emb.set_thumbnail(url=OSDLBot_storage.LOGO_URL)
    #emb.set_footer(text=f"Played on {match.time_played}")

    #Create field for each player
    for player in player_changes.keys():
        try:
            #check + or - elo
            change = player_changes[player]
            if change<0:
                change_str = str(change)
            else:
                change_str = f"+{change}"
            emb.add_field(name=f"{player.username} ({round(change_str)})",value=f"Points: {player_wins[player.id]}",inline=False)
        except:
            emb.add_field(name="Error on one of the players",value="wtf :(",inline=False)
    
    return emb
    