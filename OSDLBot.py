import discord, random
from aioconsole import ainput
import OSDLBot_storage
from datetime import datetime
from log_oop import log

intents = discord.Intents.all()
client = discord.Client(intents=intents)

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
    argsLower = lower.split(' ')
    author = message.author
    channel = message.channel
    guild = message.guild
    ####################################

    if cmd == "help":
        await sendEmbed(OSDLBot_storage.HELP_EMBED, channel)


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
            start_time = datetime(date[2], date[0], date[1])
        multi_url_format = "https://osu.ppy.sh/community/matches/"
        matches = []
        async for result in match_chan.history(after=start_time, limit=None):
            tokenized = result.content.translate({ord(i): None for i in '<>'}).split()
            try:
                ind_link = [tokenized.index(l) for l in tokenized if l.startswith(multi_url_format)][0]
            except:
                #url format not in message
                continue
            match_id = int(tokenized[ind_link][len(multi_url_format):])
            if match_id not in matches:
                matches.append(match_id)

        log_file = await log(matches, datetime.now())
        await sendFile(log_file, channel)


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

client.run(OSDLBot_storage.TOKEN)
