import datetime
import json


async def set_timer(ctx, discord_client, time: str, timer_name: str):
    """Sets a timer and writes to timers.json based on user reaction."""
    # Validate and calculate the timer end time
    try:
        timer_end = datetime.datetime.fromisoformat(time)
        if datetime.datetime.now() >= timer_end:
            await ctx.reply("Error: The specified time must be in the future.")
            return
        if (timer_end - datetime.datetime.now()) < datetime.timedelta(minutes=1):
            await ctx.reply("Error: Timer must be at least 5 minutes long.")
            return
    except ValueError:
        await ctx.reply("Invalid datetime format. Please use ISO 8601 format (YYYY-MM-DDTHH:MM).")
        return

    # Post the timer confirmation message
    confirm_message = await ctx.reply(
        f"To set the timer '{timer_name}' for {timer_end.isoformat()}, "
        f"react with :thumbsup: to confirm or :x: to cancel.")
    await confirm_message.add_reaction('👍')
    await confirm_message.add_reaction('❌')

    # Check reactions to set or cancel the timer
    def check(reaction, user):
        return (user != discord_client.user
                and str(reaction.emoji) in ['👍', '❌']
                and reaction.message.id == confirm_message.id)

    reaction, user = await discord_client.wait_for('reaction_add', check=check)
    if str(reaction.emoji) == '👍':
        # Set the timer for the user who reacted with thumbsup
        add_timer(user.id, ctx.channel.id, timer_name, timer_end)
        await ctx.reply(f"Timer set for {user.display_name} at {timer_end.isoformat()}.")
    elif str(reaction.emoji) == '❌' and user.id == ctx.author.id:
        # The user who requested the timer canceled it
        await ctx.reply("Timer setting canceled.")


def add_timer(user_id, channel_id, timer_name, timer_end):
    """Add a new timer to the JSON file."""
    with open("timers.json", "r+") as file:
        try:
            timers = json.load(file)
        except json.JSONDecodeError:
            timers = []  # Handle empty file scenario
        timers.append({
            "user_id": user_id,
            "channel_id": channel_id,
            "name": timer_name,
            "expire_time": timer_end.isoformat()
        })
        file.seek(0)
        json.dump(timers, file, indent=4)
        file.truncate()
