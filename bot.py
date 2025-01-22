import discord
from discord.ext import commands, tasks
from discord import Embed, ButtonStyle
from discord.ui import View, Button
from datetime import datetime
import asyncio

# Log channel ID
LOG_CHANNEL_ID = 974506795714351168  # Replace with your log channel ID

# Allowed announcement channel ID
ANNOUNCEMENT_CHANNEL_ID = 123456789012345678  # Replace with your announcement channel ID

# Intents and bot setup
intents = discord.Intents.default()
intents.guilds = True  # Required for guild-related events
intents.members = True  # Required for member join events or role assignment
bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary to track invite links and their corresponding roles
invite_roles = {}
guild_invites = {}

# Scheduled announcements dictionary
scheduled_announcements = {}

@bot.event
async def on_ready():
    print(f"UPA Management Bot is ready. Logged in as {bot.user}!")

# Help Command
@bot.command(name="bothelp")
async def bothelp_command(ctx):
    """
    Provide a list of commands and usage instructions.
    """
    embed = Embed(
        title="UPA Management Bot Help",
        description="Here are the available commands and how to use them:",
        color=discord.Color.green()
    )
    embed.add_field(
        name="!create_invite <@Role> [max_uses] [expire_after]",
        value="Creates an invite linked to a role. Example: `!create_invite @Member 10 3600`",
        inline=False
    )
    embed.add_field(
        name="!announce #channel <title> <image_url> <button_label> <button_url> <message>",
        value=(
            "Sends an announcement to the specified channel with a title, image, and button. "
            "Example: `!announce #announcements \"Big Event\" https://example.com/image.jpg \"Learn More\" https://example.com This is an announcement!`"
        ),
        inline=False
    )
    embed.add_field(
        name="!schedule #channel <title> <image_url> <button_label> <button_url> <time> <message>",
        value=(
            "Schedules an announcement. "
            "Time format: `YYYY-MM-DD HH:MM`. Example: `!schedule #announcements \"Big Event\" https://example.com/image.jpg \"Register\" https://example.com \"2025-01-25 18:00\" Join our big event!`"
        ),
        inline=False
    )
    embed.add_field(
        name="!cancel_schedule <time>",
        value="Cancels a scheduled announcement. Example: `!cancel_schedule 2025-01-25 18:00`",
        inline=False
    )
    embed.add_field(
        name="!bothelp",
        value="Displays this help message.",
        inline=False
    )

    await ctx.send(embed=embed)

# Create invite and associate it with a role
@bot.command(name="create_invite")
@commands.has_permissions(manage_roles=True, manage_channels=True)
async def create_invite(ctx, role: discord.Role, max_uses: int = 0, expire_after: int = 0):
    invite = await ctx.channel.create_invite(max_uses=max_uses, max_age=expire_after, unique=True)
    invite_roles[invite.code] = role.id
    await ctx.send(f"Invite created: {invite.url}\nLinked Role: {role.name}")

# Announce a message in a specific channel
@bot.command(name="announce")
@commands.has_permissions(manage_messages=True)
async def announce(ctx, channel: discord.TextChannel, title: str, image_url: str, button_label: str, button_url: str, *, message: str):
    # Check if the specified channel is the allowed announcement channel
    if channel.id != ANNOUNCEMENT_CHANNEL_ID:
        await ctx.send(f"Announcements can only be posted in <#{ANNOUNCEMENT_CHANNEL_ID}>.")
        return

    # Create and send the announcement
    embed = Embed(
        title=title,
        description=message,
        color=discord.Color.blue()
    )
    embed.set_image(url=image_url)
    button = Button(label=button_label, style=ButtonStyle.link, url=button_url)
    view = View()
    view.add_item(button)
    await channel.send(embed=embed, view=view)
    await ctx.send(f"Announcement successfully posted in {channel.mention}.")

# Schedule an announcement
@bot.command(name="schedule")
@commands.has_permissions(manage_messages=True)
async def schedule(ctx, channel: discord.TextChannel, title: str, image_url: str, button_label: str, button_url: str, time: str, *, message: str):
    # Check if the specified channel is the allowed announcement channel
    if channel.id != ANNOUNCEMENT_CHANNEL_ID:
        await ctx.send(f"Scheduled announcements can only be posted in <#{ANNOUNCEMENT_CHANNEL_ID}>.")
        return

    try:
        scheduled_time = datetime.strptime(time, "%Y-%m-%d %H:%M")
        if scheduled_time <= datetime.now():
            await ctx.send("The scheduled time must be in the future.")
            return

        scheduled_announcements[scheduled_time] = {
            'channel_id': channel.id,
            'title': title,
            'message': message,
            'image_url': image_url,
            'button_label': button_label,
            'button_url': button_url
        }
        await ctx.send(f"Announcement scheduled for {scheduled_time} in {channel.mention}.")
    except ValueError:
        await ctx.send("Invalid time format. Use 'YYYY-MM-DD HH:MM'.")

# Background task to send scheduled announcements
@tasks.loop(seconds=30)
async def check_scheduled_announcements():
    now = datetime.now()
    to_remove = []
    for scheduled_time, details in scheduled_announcements.items():
        if scheduled_time <= now:
            channel = bot.get_channel(details['channel_id'])
            if channel:
                embed = Embed(
                    title=details['title'],
                    description=details['message'],
                    color=discord.Color.blue()
                )
                embed.set_image(url=details['image_url'])
                button = Button(label=details['button_label'], style=ButtonStyle.link, url=details['button_url'])
                view = View()
                view.add_item(button)
                await channel.send(embed=embed, view=view)
            to_remove.append(scheduled_time)
    for time in to_remove:
        del scheduled_announcements[time]

# Cancel a scheduled announcement
@bot.command(name="cancel_schedule")
@commands.has_permissions(manage_messages=True)
async def cancel_schedule(ctx, time: str):
    try:
        scheduled_time = datetime.strptime(time, "%Y-%m-%d %H:%M")
        if scheduled_time in scheduled_announcements:
            del scheduled_announcements[scheduled_time]
            await ctx.send(f"Scheduled announcement for {scheduled_time} has been canceled.")
        else:
            await ctx.send("No announcement found for the specified time.")
    except ValueError:
        await ctx.send("Invalid time format. Use 'YYYY-MM-DD HH:MM'.")

# Assign roles when a user joins
@bot.event
async def on_member_join(member):
    guild = member.guild
    invites_after = await guild.invites()
    used_invite = None

    for invite in guild_invites.get(guild.id, []):
        matching_invite = next((i for i in invites_after if i.code == invite.code), None)
        if matching_invite and invite.uses < matching_invite.uses:
            used_invite = matching_invite
            break

    if used_invite and used_invite.code in invite_roles:
        role_id = invite_roles[used_invite.code]
        role = guild.get_role(role_id)
        if role:
            await member.add_roles(role)
            log_channel = guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(f"Assigned role '{role.name}' to {member.mention} via invite {used_invite.url}")
    guild_invites[guild.id] = invites_after

# Sync invite links periodically
@tasks.loop(minutes=10)
async def sync_invites():
    for guild in bot.guilds:
        guild_invites[guild.id] = await guild.invites()

# Run the bot with your token (keep quotes around the token)
bot.run("YOUR_BOT_TOKEN")
