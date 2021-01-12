from osuapi import OsuApi, ReqConnector, enums
import aiohttp, asyncio, sys, os, datetime, pprint, discord
import OSDLBot_storage
from multi_structs import Map, Game, Match, MatchNotFoundError
api = OsuApi(OSDLBot_storage.OSU_API_KEY, connector=ReqConnector())

#match_ids is list of integer multiplayer ids
async def log(match_ids, date, pool="round12"):
    os.chdir(OSDLBot_storage.DATA_DIR)

    if pool not in OSDLBot_storage.pools.keys():
        return discord.Embed(description=f"Error: could not find pool {pool}")

    curr_pool_dict = OSDLBot_storage.pools[pool]
    print(curr_pool_dict)
    #Create a template scoredict with each map id initialized with a value 0
    scoredict = {}
    for map in OSDLBot_storage.pools[pool].values():
        scoredict.setdefault(map,0)

    path = f"{OSDLBot_storage.DATA_DIR}\\scorelog-{date.month}-{date.day}-{date.year}.csv"

    with open(path,"w") as f:
        players = {} #userid:scoredict
        failed_matches = []
        for id in match_ids:
            try:
                match = Match(id)
            except MatchNotFoundError:
                failed_matches.append(id)
                continue

            for game in match.round_list:
                if not game.in_pool(curr_pool_dict):
                    continue
                for score in game.player_scores.items():
                    #item is (usermodel, score)
                    players.setdefault(score[0].user_id, dict(scoredict))
                    print(f"Logging score {score}")
                    #FIXME: adjust for mods used
                    adj_score = score[1]
                    if adj_score>players[score[0].user_id][game.map.id]:
                        players[score[0].user_id][game.map.id] = adj_score

        #Warn of matches which couldn't be analyzed
        if len(failed_matches)>0:
            f.write(f"******WARNING: matches with the following IDs could not be processed. Please update scores manually: {failed_matches}\n")

        for player in players.items():
            scores = player[1]
            userstr = await resolve_user(player[0])
            for item in scores.items():
                userstr+=","
                userstr+=str(item[1])
            f.write(userstr+"\n")
    return path

async def resolve_user(id):
    print(f"Resolving id {id}")
    return api.get_user(id)[0].username


# players = {userid:scoredict}
# scoredict = {mapid:score}
