from osuapi import OsuApi, ReqConnector, enums
import aiohttp, asyncio, sys, os, datetime, pprint
import OSDLBot_storage
api = OsuApi(OSDLBot_storage.OSU_API_KEY, connector=ReqConnector())

class MatchNotFoundError(Exception):
    pass

class Map():
    def __init__(self, map_id):
        self.map = api.get_beatmaps(beatmap_id=map_id)[0]
        self.id = self.map.beatmap_id

class Game():
    def __init__(self, game_api):
        self.is_v2 = game_api.scoring_type == enums.ScoringType.score_v2
        self.map = Map(game_api.beatmap_id)

        #init player scores dict {osu_user: score}
        self.player_scores = {}
        for teamscore in game_api.scores:
            self.player_scores[resolve_user(teamscore.user_id)] = teamscore.score

        #Store data about which mods players used

    #check map played is in pool dictionary
    def in_pool(self, pool):
        return self.map.id in pool.values()

class Match():

    def __init__(self, id):
        try:
            self.json = api.get_match(id)
        except:
            raise MatchNotFoundError()
        self.round_list = [Game(g) for g in self.json.games]

    def valid_tourney(self, pool, warmups=2, scorev2=True):
        remove_warmups = self.round_list[warmups:]
        #Check all maps in pool
        for game in remove_warmups:
            #Invalid if map not in pool or game doesn't match scorev2 req
            if not game.in_pool(pool) or game.is_v2 != scorev2:
                return False
        return True

def resolve_user(id):
    return api.get_user(id)[0].username
