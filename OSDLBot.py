import discord, random
from dill.source import getsource
from aioconsole import ainput
import OSDLBot_storage
from datetime import datetime
from log_matches import log
from mm_utils import *
from multi_structs import *
from dotenv import load_dotenv

intents = discord.Intents.all()
client = discord.Client(intents=intents)
load_dotenv()

#On bot startup/ready
@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

    await client.change_presence(activity=discord.Game(name=f"use {OSDLBot_storage.PREFIX}help for help!"))

    while True:
        cmd = await ainput()
        await handleCline(cmd)

#On message received
@client.event
async def on_message(message):
    if message.author == client.user or message.content == None:
        return
    
    #LOCK BOT
    if not message.author.id in OSDLBot_storage.ADMIN_ID:
        return

    if message.guild == None:
        #Message is a dm
        print(f"DM received from {message.author}")

        #If not from dev, forward to dev
        if message.author.id != OSDLBot_storage.ADMIN_ID[0]:
            dmForward = f"Message from {message.author.name} (ID: {message.author.id}): {message.content}"
            dev = client.get_user(int(OSDLBot_storage.ADMIN_ID[0]))
            await sendMsg(dmForward,dev)

    #Check if admin command
    if message.author.id in OSDLBot_storage.ADMIN_ID:
        await adminCmd(message)

    #Check if prefixed command
    if message.content.startswith(OSDLBot_storage.PREFIX):
        await prefixed(message)
    else:
        await implicit(message)

#Prefixed commands
async def prefixed(message):
    #### Message property variables ####
    cmd = message.content[len(OSDLBot_storage.PREFIX):]
    args = cmd.split(' ')
    lower = cmd.lower()
    author = message.author
    channel = message.channel
    guild = message.guild
    ####################################

    if cmd == "help":
        await sendEmbed(OSDLBot_storage.HELP_EMBED, channel)
    
    if args[0] == "link":
        #Check if second arg passed
        if len(args)<2:
            await sendEmbed(discord.Embed(description="Please provide an osu! username or ID to link with your account"), channel)
            return
        #Get string of the osu username or ID
        osu_user = ' '.join(args[1:])

        try:
            #get user
            player_obj = await link_account(osu_user,author.id)
        except UserNotFoundError:
            await sendEmbed(discord.Embed(description=f"User {osu_user} could not be found on osu!"), channel)
            return
        except AlreadyLinkedError:
            await sendEmbed(discord.Embed(description=f"You already have an osu! account linked! Contact Scheisse if you believe this is an error."), channel)
            return

        await sendEmbed(discord.Embed(description=f"Discord user {author.name} linked to {player_obj.username}"), channel)

    if args[0] == "osu":
        try:
            if len(message.mentions)>0:
                #Get the linked account of user mentioned in command
                fetching = message.mentions[0]
                emb = await get_linked_embed(discord_id=fetching.id, pfp_url=fetching.avatar_url)
            elif len(args)>1:
                passed = ' '.join(args[1:])
                if "osu.ppy.sh" in passed:
                    #profile link was passed
                    passed = passed.split("/")[-1]
                elif not passed.isdigit():
                    #Convert osu username to int id
                    passed = await get_osu_user_id(passed)
                emb = await get_linked_embed(osu_user=int(passed))
            else:
                emb = await get_linked_embed(discord_id=author.id, pfp_url=author.avatar_url)
        except PlayerNotFound:
            emb = discord.Embed(description="Could not find this user!")
        await sendEmbed(emb, channel)

    if args[0] == "match":
        #Check for multi link passed as second arg
        if len(args)<2 or not args[1].startswith(OSDLBot_storage.multi_url_format):
            await sendEmbed(discord.Embed(description=f"Please provide a link to the match played (should start with {OSDLBot_storage.multi_url_format}"),channel)
            return
        
        #Process linked match
        try:
            response = await process_match(int(args[1][len(OSDLBot_storage.multi_url_format):]))
        except AlreadyCalcError:
            await sendEmbed(discord.Embed(description=f"This match has already been processed! Contact Scheisse if you believe this is an error."), channel)
        await sendEmbed(response,channel)
    
    if args[0] == "leaderboard" or args[0] == "lb":
        if len(args)>1 and args[1].isdigit():
            #Page was passed
            lb = await leaderboard(author.id,page=int(args[1]))
        else:
            #Get first page
            lb = await leaderboard(author.id)
        await sendEmbed(lb,channel)



#Implicit commands
async def implicit(message):
    #### Message property variables ####
    text = message.content
    lower = text.lower()
    channel = message.channel
    author = message.author
    ####################################

    if lower == "ping":
        await sendMsg("pong", channel)

#Admin commands
async def adminCmd(message):
    text = message.content
    channel = message.channel
    lower = text.lower()
    guild = message.guild
    #Implicits

    #Prefixed
    if text == '' or text[0] != OSDLBot_storage.PREFIX:
        return
    cmd = text[1:].split(" ")

    if cmd[0] == "addelo":
        await add_elo_by_discord(int(cmd[1]),int(cmd[2]))
    
    if cmd[0] == "setelo":
        await set_elo_by_discord(int(cmd[1]),int(cmd[2]))

    if cmd[0] == "revert":
        linking = int(cmd[1])
        osu_id = int(cmd[2])
        player_obj = await reset_link(linking, osu_id)
        await sendEmbed(discord.Embed(description=f"Account {player_obj.username} reverted."), channel)


    if cmd[0] == "logmatches":
        match_chan = guild.get_channel(OSDLBot_storage.MATCH_RESULT_CHAN)
        start_time = match_chan.created_at
        if len(cmd)>1:
            #Start date passed MM/DD/(YY)YY
            date_in = cmd[1].split("/")
            date=[]
            #convert date values to ints
            for d in date_in:
                date.append(int(d))
            #Fix truncated year value
            if date[2]<1000:
                date[2] += 2000
            start_time = datetime.datetime(date[2], date[0], date[1])

        matches = []
        async for result in match_chan.history(after=start_time, limit=None):
            tokenized = result.content.translate({ord(i): None for i in '<>'}).split()
            try:
                ind_link = [tokenized.index(l) for l in tokenized if l.startswith(OSDLBot_storage.multi_url_format)][0]
            except:
                #url format not in message
                continue
            match_id = int(tokenized[ind_link][len(OSDLBot_storage.multi_url_format):])
            if match_id not in matches:
                matches.append(match_id)

        log_file = await log(matches, datetime.datetime.now())
        await sendFile(log_file, channel)
    
    if cmd[0]=='unlink':
        to_unlink = cmd[1]
        await reset_link(to_unlink,breaking=True)


    if cmd[0]=='dm':
        #Intended recipient ID
        dmUser = client.get_user(int(cmd[1]))
        dmMsg = ' '.join(cmd[2:])
        await sendMsg(dmMsg,dmUser)

#######################################################
################## Utility Functions ##################
#######################################################

#Parse and handle commands run from terminal
async def handleCline(cmd):
    clineArgs = cmd.split(' ')

    if clineArgs[0] == "announce":
        if len(clineArgs)<2:
            print("Must pass message to announce")
        else:
            try:
                #Try if channel ID was passed
                ancChan = client.get_channel(int(clineArgs[1]))
                ancMsg = ' '.join(clineArgs[2:])
            except:
                #If channel ID not passed
                ancChan = client.get_channel(OSDLBot_storage.MAIN_CHAT_ID)
                ancMsg = ' '.join(clineArgs[1:])
            await sendMsg(ancMsg,ancChan)

#Sends text to given channel
async def sendMsg(msg, channel):
    try:
        print(f"Sending message to {channel.name}: \n\t-\"{msg}\"")
        return await channel.send(msg)
    except:
        print(f"Error while attempting to send message to {channel.name}")

#Sends embed to given channel, Optional: pass content to go with it
async def sendEmbed(msg, channel, cntnt=None):
    try:
        await channel.send(content=cntnt,embed=msg)
        print(f"Sent embed to {channel.name}: {msg.title}")
    except:
        print(f"Error while attempting to send embed to {channel.name}")

#Sends a file from an absolute local path
async def sendFile(fp, channel, cntnt=None):
    imgFile = discord.File(fp)
    try:
        await channel.send(content=cntnt,file=imgFile)
        print(f"Sent file to {channel.name}: {fp}")
    except:
        print(f"Error while attempting to send {fp} to {channel.name}")

#Return url string of most recently posted image
async def getLastImg(chan):
    async for message in chan.history(limit=100):
        if len(message.attachments) >= 1:
            return message.attachments[0].url
    return None

client.run(os.environ.get('TOKEN'))
