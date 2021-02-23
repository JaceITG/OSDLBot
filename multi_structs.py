from osuapi import OsuApi, ReqConnector, enums
import aiohttp, asyncio, sys, os, datetime, pprint, shelve
from threading import Lock
import OSDLBot_storage
from dotenv import load_dotenv
load_dotenv()
api = OsuApi(os.environ.get('OSU_API_KEY'), connector=ReqConnector())
lock = Lock()
class MatchNotFoundError(Exception):
    pass

class PlayerNotFound(Exception):
    pass

class Map():
    def __init__(self, map_id):
        self.map = api.get_beatmaps(beatmap_id=map_id)[0]
        self.id = self.map.beatmap_id
        self.title = self.map.title

class Game():
    def __init__(self, game_api):
        self.is_v2 = game_api.scoring_type == enums.ScoringType.score_v2
        self.map = Map(game_api.beatmap_id)
        self.mods = game_api.mods

        #init player scores dict {Player: score}
        self.player_scores = {}
        self.players = []
        for teamscore in game_api.scores:

            p = find_osu_player(teamscore.user_id)
            if p is None:
                raise PlayerNotFound()
            ##print(f"Mods for {p.username}: {teamscore.enabled_mods}")
            self.players.append(p)
            #FIXME: adjust mod multipliers before adding to player_scores
            #on freemod rounds...
            #nomod multiplied by 0.8, ez by 1.75
            self.player_scores[p] = teamscore.score

        #Store data about which mods players used

    #Get the players in this round
    def get_players(self):
        return self.players

    #Get the Player that won this round/map
    def get_winner(self):
        winnerps = None
        for ps in self.player_scores.items():
            if winnerps is None or ps[1]>winnerps[1]:
                winnerps = ps
        return winnerps[0]

    #check map played is in pool dictionary
    def in_pool(self, pool):
        return self.map.id in pool.values()

class Match():

    def __init__(self, id):
        try:
            self.json = api.get_match(id)
        except:
            raise MatchNotFoundError()

        #Match meta
        self.match = self.json.match
        self.title = self.match.name
        self.time_played = self.match.start_time

        #Games
        self.round_list = [Game(g) for g in self.json.games]
        self.players = []#li of player ids who participated
        self.winner = None

    #Get dict of osu_id:num_wins for this match
    def calc_round_wins(self):
        wins = {}
        for round in self.round_list:
            winner = round.get_winner().id

            #Make an entry in wins dict for every player who appears in Match
            for p in round.get_players():
                if p.id not in self.players:
                    self.players.append(p.id)
                wins.setdefault(p.id,0)
            wins[winner]+=1
        return wins

    #Omit all maps which don't appear in the pool list from round_list
    def strip_nonpool(self, pool):
        new_list = self.round_list
        for r in new_list:
            if not r.in_pool(pool):
                new_list.remove(r)
        self.round_list = new_list

    #Check whether all maps played are in the pool (opt: skip x warmups)
    #FIXME: ensure num rounds correct for Best Of N
    def valid_tourney(self, pool, warmups=0, scorev2=True):
        remove_warmups = self.round_list[warmups:]
        #Check all maps in pool
        for game in remove_warmups:
            #Invalid if map not in pool or game doesn't match scorev2 req
            if not game.in_pool(pool) or game.is_v2 != scorev2:
                return False

        #check win margin
        wins = self.calc_round_wins()
        needed_for_win = (pool['BO']//2)+1
        highest = 0
        lowest = needed_for_win
        #Get higher and lower score
        for wincount in wins.values():
            if wincount>highest:
                highest=wincount
            if wincount<lowest:
                lowest=wincount
        if highest!=needed_for_win:
            return False

        #Check last is TB
        if wincount-1==lowest:
            #Last should have been a TB
            if remove_warmups[len(remove_warmups)-1].map.id != pool['tb']:
                return False
        return True

#Return the Player object stored in the dictionary with the given ID, or None if not found
def find_osu_player(osu_user_id):
    with shelve.open("userdb") as db:
        #Create a list of player objs stored in the dict
        players = [db[id] for id in db.keys()]

    for player in players:
        if osu_user_id == player.id:
            return player
    return None

class Player():
    def __init__(self, user_id, discord=0, new=False):
        in_database = find_osu_player(user_id)
        if in_database and not new:
            self = in_database
        elif new:
            self.obj = api.get_user(user_id)[0]

            self.discord_id = discord
            self.username = self.obj.username
            self.elo = 1000

            #Osu info
            self.id = self.obj.user_id
            self.rank = self.obj.pp_rank
            self.rank_c = self.obj.pp_country_rank
            self.acc = round(self.obj.accuracy,2)
            self.pp = self.obj.pp_raw
            self.plays = self.obj.playcount
            self.country = self.obj.country
        else:
            raise PlayerNotFound()

    def write(self):
        lock.acquire()
        with shelve.open("userdb") as db:
            #find correct link
            for link in db.items():
                if link[1].id == self.id:
                    #overwrite link
                    db[link[0]] = self
                    break
        lock.release()

    def get_elo(self):
        return self.elo

    def set_elo(self, new_elo):
        self.elo = new_elo
        self.write()

    def add_elo(self, elo_delta):
        self.elo += elo_delta
        self.write()
        return self.elo

    def update(self):
        self.obj = api.get_user(self.id)[0]
        self.username = self.obj.username
        #Osu info
        self.id = self.obj.user_id
        self.rank = self.obj.pp_rank
        self.rank_c = self.obj.pp_country_rank
        self.acc = round(self.obj.accuracy,2)
        self.pp = self.obj.pp_raw
        self.plays = self.obj.playcount
        self.country = self.obj.country
        self.write()

def resolve_username(id):
    return api.get_user(id)[0].username
