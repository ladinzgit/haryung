import discord
from discord.ext import commands
import os
import asyncio
import typing
try:
    from dotenv import dotenv_values
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    _env = dotenv_values(_env_path)
    print(f"📄 .env 로드 완료 ({_env_path}), 키: {list(_env.keys())}")
except Exception as e:
    print(f"⚠️ .env 로드 실패: {e}")
    _env = {}

def get_env(key):
    """환경 변수를 가져옵니다. .env 파일 값을 우선하고, 없으면 시스템 환경 변수에서 가져옵니다."""
    value = _env.get(key)
    if value:
        return value
    return os.environ.get(key)

application_id = get_env("APPLICATION_ID")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="*", intents=intents, help_command=None, application_id = application_id)
bot_token = get_env("DISCORD_BOT_TOKEN")

# load cogs

async def load():
    success = []
    fail = []
    why = {}

    cogs_path = os.path.join(os.path.dirname(__file__), "cogs")

    # Logger를 우선 로드
    priority = ["Logger"]
    cog_files = sorted(os.listdir(cogs_path))
    ordered = [f for f in cog_files if f[:-3] in priority] + \
              [f for f in cog_files if f[:-3] not in priority]

    for filename in ordered:
        if filename.endswith(".py") and not filename.startswith("__"):
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                success.append(cog_name)
                print(f"✅ {cog_name} 로드 완료")
            except Exception as e:
                print(f"❌ {cog_name} 로드 실패: {e}")
                fail.append(cog_name)
                why[cog_name] = e

    logger = bot.get_cog('Logger')

    if logger:
        if fail:
            for cog in fail:
                await logger.log(f"{cog} cog가 로드에 실패하였습니다. 오류: {why[cog]}", cog)
        await logger.log("모든 cog가 로드되었습니다.", "main.py")
    else:
        print("⚠️ Logger cog가 로드되지 않았습니다.")

# server start

async def main():
    async with bot:
        await bot.start(bot_token)

# bot ready

@bot.event
async def on_ready():
    await load()

    if logger := bot.get_cog('Logger'):
        await logger.log("봇이 성공적으로 시작되었습니다.", "main.py")

    print("Online!")

    activity = discord.CustomActivity(name="👻 흐엥… 나 무서운 유령이야")
    await bot.change_presence(status=discord.Status.online, activity=activity)

    print("Syncing commands to all guilds...")
    for guild in bot.guilds:
        try:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)

            print(f"Synced to {guild.name} ({guild.id})")
        except Exception as e:
            print(f"Failed to sync to {guild.name}: {e}")
    
 # slash command sync

@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(
    ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: typing.Optional[typing.Literal["~","*","^"]] = None) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return

    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1

    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

@sync.error
async def sync_error(error):
    print(f"error in sync: {error}")

asyncio.run(main())
