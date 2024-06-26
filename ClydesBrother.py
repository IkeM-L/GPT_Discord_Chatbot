import atexit
import json
import random
import time
from datetime import datetime, timedelta
from typing import Tuple, List

import discord
from discord.ext import tasks
from openai import OpenAI
from openai.types.chat import ChatCompletionMessage, ChatCompletionMessageToolCall

from CONFIG import tools, initial_prompt
from DockerPythonExecutor import DockerPythonExecutor
from FindNewMagicStory import MagicStoryChecker
from Imitator.GetMessages import save_messages
from Imitator.IMITATOR_CONFIG import model_path
from Imitator.imitator_message_gen import generate_message
from MessageGraph import MessageGraph
from TimerTool import set_timer

# Constants
SECRETS_FILE = "secrets.json"
TIMERS_FILE = "timers.json"
MESSAGE_HISTORY_FILE = 'message_history.json'
SCRAPE_MESSAGES_CHANNEL_ID = 944200738605776906
SCRAPE_START_DATE = "2023-01-02"
MAGIC_STORY_CHANNEL_ID = 1032688705128902788
RESPONSE_CHANCE = 0.005

# Initialize the Discord API key and OpenAI API key from secrets.json
# Initialize the Discord and OpenAI API keys
with open(SECRETS_FILE) as secrets_file:
    secrets = json.load(secrets_file)
    DISCORD_API_KEY = secrets["discord_api_key"]
    OPENAI_API_KEY = secrets["openai_api_key"]

# Initialize clients and important variables
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
discord_client = discord.Client(intents=intents)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
model = "gpt-4o"
message_graph = MessageGraph(MESSAGE_HISTORY_FILE)
scrape_messages = False


# Tasks
@tasks.loop(minutes=30)
async def post_new_articles() -> None:
    """Check for and post new Magic Story articles."""
    channel = discord_client.get_channel(MAGIC_STORY_CHANNEL_ID)
    if channel is None:
        print(f"Channel with ID {MAGIC_STORY_CHANNEL_ID} not found.")
        return

    checker = MagicStoryChecker('https://magic.wizards.com/en/news/magic-story')
    new_articles = checker.get_new_articles()
    if not new_articles:
        # Uncomment to log when no new articles are found
        # print("No new articles found.")
        return

    await channel.send("New Magic Story articles found:")
    for article in reversed(new_articles):
        await channel.send(f"https://magic.wizards.com{article}")


@tasks.loop(seconds=5)
async def check_timers() -> None:
    """Check for timers and perform actions when they expire."""
    # Try to check the timers file, if it doesn't exist, return
    try:
        with open(TIMERS_FILE, "r") as file:
            timers = json.load(file)
    except Exception as e:
        print(f"Error reading timers file: {e}")
        return

    # Get current time
    current_time = datetime.now()
    updated_timers = []

    # Check each timer
    for timer in timers:
        expire_time = datetime.fromisoformat(timer['expire_time'])

        # If the timer has expired, perform the action
        if current_time >= expire_time:
            # Send the message
            print(f"Timer expired: {timer['name']}")
            user = await discord_client.fetch_user(timer['user_id'])  # Fetch the user based on user_id
            channel = discord_client.get_channel(timer['channel_id'])
            await channel.send(f"{user.mention} :alarm_clock:: '{timer['name']}'")
        else:
            # Only re-add timers that have not yet expired
            updated_timers.append(timer)

    # Save the updated list of timers back to the file
    try:
        with open(TIMERS_FILE, "w") as file:
            json.dump(updated_timers, file)
    except Exception as e:
        print(f"Error writing timers file: {e}")


# Event Handlers
@discord_client.event
async def on_ready() -> None:
    """
    Runs when the bot is ready and starts various tasks.
    """
    print(f'We have logged in as {discord_client.user}')
    # Start our tasks
    post_new_articles.start()
    check_timers.start()

    # Scrape messages from a channel if enabled
    if scrape_messages:
        await scrape_and_save_messages(SCRAPE_MESSAGES_CHANNEL_ID, SCRAPE_START_DATE)


@discord_client.event
async def on_message(message: discord.Message) -> None:
    """
    Handles incoming messages from the Discord server and decides how to respond.
    :param message: The message object.
    """

    # Ignore messages from the bot itself
    if message.author == discord_client.user:
        return

    # Ignore empty messages that mention the bot
    if not message.content and discord_client.user in message.mentions:
        # Tell the user their message got lost in the void
        await message.reply("Your message was lost in the void. Please try again.")
        return

    # Allow the bot to use a custom prompt when the user message starts with "prompt:"
    if message.content.startswith("prompt:"):
        await process_custom_prompt(message)
        return

    # Allow the custom model to be used with imitator: prefix
    if message.content.startswith("imitator:"):
        await process_imitator_prompt(message)
        return

    # Process general messages
    await process_general_message(message)


async def process_imitator_prompt(message: discord.Message) -> None:
    content = message.content[9:]
    async with message.channel.typing():
        response = generate_message(content, model_path)
        await message.reply(response)


async def process_general_message(message: discord.Message) -> None:
    """Processes general messages."""
    message_details = parse_message(message)
    bot_mentioned = discord_client.user.id in [mention.id for mention in message.mentions]

    if message_details['author_role'] == "user" and not bot_mentioned and not message_details['reply_to_id']:
        if random.random() < RESPONSE_CHANCE and message.channel.id == SCRAPE_MESSAGES_CHANNEL_ID:
            response = generate_message(message.content, model_path)
            await message.reply(response)
            print("Responded with custom model by chance")
        return

    if message_graph.get_message_role(message_details['reply_to_id']) == "user":
        return

    message_graph.add_message(
        message_details['id'], message_details['author_role'], message_details['content'], time.time(),
        reply_to=message_details['reply_to_id']
    )

    async with message.channel.typing():
        response, error = await process_message(message_details)

    if error:
        await message.reply(error)
        return

    if response.tool_calls:
        await process_tool_calls(message, response)
    else:
        await finalize_message_response(message, response, message_details['id'])


# Message Processing Functions

async def process_message(message_details: dict) -> Tuple[ChatCompletionMessage, None] | Tuple[None, str]:
    """
    Processes incoming messages and returns a response.
    In particular, this function fetches a response from the OpenAI API based on the conversation history
    after building a message chain from the message graph and ensuring the conversation starts with the initial prompt.
    :param message_details: The details of the incoming message.
    :return: the response from the OpenAI API and an error message if one occurred.
    """
    if not message_details:
        return None, "Message details not provided."

    message_chain = message_graph.get_message_chain(message_details['id'])
    # Ensure the conversation starts with the initial prompt if necessary
    if len(message_chain) == 1:
        prepend_initial_prompt(message_details['id'])
        message_chain = message_graph.get_message_chain(message_details['id'])

    return await fetch_response_from_openai(message_chain)


def prepend_initial_prompt(message_id: int) -> None:
    """
    Prepends the initial prompt to the message chain if necessary.
    :param message_id: The ID of the message to prepend the initial prompt to.
    """
    if not message_id:
        return

    system_message_id = f"{message_id}_system"
    message_graph.add_message(system_message_id, "system", initial_prompt, time.time())
    message_graph.messages[message_id].parent_id = system_message_id


async def process_custom_prompt(message: discord.Message) -> None:
    """
    Adds a custom prompt to the message graph, so any replies to it will be generated based on the prompt.
    :param message: The message object containing the custom prompt.
    """
    if not message:
        return

    # Exclude the "prompt:" prefix and trim whitespace
    prompt = message.content[7:].strip()
    # Ensure the prompt is not empty
    if not prompt:
        await message.reply("Please provide a non-empty prompt.")
        return
    # Trim the prompt if it's too long
    prompt = prompt[:1000]

    # Add the prompt to the message graph
    message_graph.add_message(message.id, "system",
                              prompt, time.time())

    # react with a thumbs up to indicate the prompt was received
    await message.add_reaction("👍")


# OpenAI API Functions

async def fetch_response_from_openai(message_chain: list) -> Tuple[ChatCompletionMessage, None] | Tuple[None, str]:
    """
    Fetches a response from the OpenAI API.
    :param message_chain: the conversation history
    :return: A tuple containing the response and an error message. One of them will be None.
    """
    try:
        completion = openai_client.chat.completions.create(
            model=model,
            messages=message_chain,
            tools=tools,
            tool_choice="auto"
        )
        response = completion.choices[0].message
        return response, None
    except Exception as e:
        print(e)
        return None, f"Error: {str(e)}"


# Utility Functions


def parse_message(message: discord.Message) -> dict | None:
    """
    Extracts important information from the message object retrieved from Discord's API.
    :param message: The message object.
    :return: A dictionary containing the message details: ID, author role, content, and reply-to ID.
    Role can be "user" or "assistant"
    """
    if not message:
        return None

    return {
        'id': message.id,
        'author_role': "assistant" if message.author == discord_client.user else "user",
        'content': f"{message.author.display_name}: {message.content}",
        'reply_to_id': parse_reply_to_id(message)
    }


def parse_reply_to_id(message: discord.Message) -> int | None:
    """
    Extracts reply-to ID if available.
    :param message: The message object.
    :return: The ID of the message being replied to, or None if there is no reply.
    """
    if message.reference and message.reference.message_id:
        reply_to_id = message.reference.message_id
        return reply_to_id if reply_to_id in message_graph.messages else None
    return None


async def finalize_message_response(original_message: discord.Message,
                                    response: ChatCompletionMessage, message_id: int) -> None:
    """
    Finalizes and sends the response to the original message.
    We split the response into multiple messages if it's too long,
    log the response in the message graph,
    and send the response.
    :param original_message: the user message to reply to
    :param response: The bot's response
    :param message_id: The ID of the message in the message graph
    """
    # Split the response into multiple messages if it's too long
    if len(response.content) > 2000:
        response_parts = [response.content[i:i + 2000] for i in range(0, len(response.content), 2000)]
        for part in response_parts:
            sent_message = await original_message.reply(part)
            response_id = sent_message.id
            message_graph.add_message(response_id, "assistant", part, time.time(), reply_to=message_id)
            message_id = response_id
        return
    sent_message = await original_message.reply(response.content)
    response_id = sent_message.id
    message_graph.add_message(response_id, "assistant", response.content, time.time(), reply_to=message_id)


# Tool Call Handlers


async def process_tool_calls(message: discord.Message, response: ChatCompletionMessage) -> None:
    """
    Processes tool calls within the response.

    This function dispatches each tool call to its respective handler based on the tool's name.
    It makes it easy to extend the bot with additional tools by simply adding new handlers.
    """
    if not response.tool_calls:
        return
    if not message:
        return

    for tool_call in response.tool_calls:
        tool_name = tool_call.function.name
        # Dispatch the tool call to its handler
        if tool_name == "python":
            await handle_python_tool_call(message, tool_call)
        elif tool_name == "timer":
            await handle_timer_tool_call(message, tool_call)
        else:
            print(f"No handler for tool: {tool_name}")


async def handle_python_tool_call(message: discord.Message, tool_call: ChatCompletionMessageToolCall) -> None:
    """
    Handles tool calls for the Python executor tool.

    This function is responsible for executing Python code provided in tool calls
    and sending the results back as a reply to the original message.
    :param message: The original message that triggered the tool call.
    :param tool_call: The tool call to handle.
    """
    if not message:
        return
    if not tool_call:
        return
    if not tool_call.function.arguments:
        return

    # Parse the command in case it's in JSON format
    command = parse_command_from_json(tool_call.function.arguments)
    # Send a message indicating the tool call is being processed
    tool_call_message = await message.reply(f"```python\n{command}```")

    # Execute the Python code
    response, error = execute_python(command)
    if error:
        await tool_call_message.reply(f"Error: {error}")
        # add the error message to the graph
        message_graph.add_message(tool_call_message.id, "system", error, time.time(), reply_to=message.id)
        return

    tool_response_message = await tool_call_message.reply(f"```{response}```")
    # Log the tool call and the response in the message graph
    log_tool_call_in_message_graph(message.id, tool_call_message.id, tool_response_message.id, command, response)


async def handle_timer_tool_call(message: discord.Message, tool_call: ChatCompletionMessageToolCall) -> None:
    """
    Handles tool calls for the timer tool.
    :param message:  The original message that triggered the tool call.
    :param tool_call:  The tool call to handle.
    :return:  None
    """
    # Get the parameters from the tool call
    parameters = tool_call.function.arguments
    if not parameters:
        return
    # Get the name and the time/relative time from the parameters
    # Get the parameters as a dictionary from json
    parameters = json.loads(parameters)
    timer_name = parameters.get("name")
    timer_time = parameters.get("time")
    relative_time = parameters.get("relative_time")
    if timer_time is None and relative_time is None:
        print("Error: Either time or relative_time must be provided.")
        return
    # Set the timer
    if timer_time:
        await set_timer(message, discord_client, timer_time, timer_name)
    elif relative_time:
        # Get the current datetime
        now = datetime.now()
        # Parse the hours and minutes from the relative_time string
        # Define possible time formats
        time_formats = ["%H:%M", "%H:%M:%S", "%D:%H:%M:%S"]

        # Try parsing the relative_time using the defined formats
        for time_format in time_formats:
            try:
                parsed_time = datetime.strptime(relative_time, time_format)
                break
            except ValueError:
                continue
        else:
            # Handle the case where none of the formats matched
            raise ValueError("Invalid time format. Please provide time in HH:MM or HH:MM:SS format.")

        # Calculate the absolute time by adding the relative time to the current datetime
        absolute_time = now + timedelta(hours=parsed_time.hour, minutes=parsed_time.minute, seconds=parsed_time.second)
        # Convert the datetime object to an ISO 8601 formatted string
        iso_format_time = absolute_time.isoformat()
        # Pass the ISO 8601 string to the set_timer function
        await set_timer(message, discord_client, iso_format_time, timer_name)


def parse_command_from_json(command: str) -> str:
    """
    Attempts to parse the command from a JSON string.
    If the command is not a JSON string, or if it doesn't contain the "command" key,
    it returns the original command.
    Note: The GPT API is inconsistent in how it formats the tool calls, this function makes sure it is parsed correctly.
    :param command: The command to parse, this can be a JSON string or a regular string.
    :return: The parsed command, or the original command if it couldn't be parsed.
    Usually the original command is the correct tool call, just not in JSON format.
    """
    try:
        parsed_command = json.loads(command)
        return parsed_command.get("command", command)
    except json.JSONDecodeError:
        return command


def log_tool_call_in_message_graph(message_id: int, tool_call_message_id: int, tool_response_message_id: int,
                                   command: str, response: str) -> None:
    """
    Logs the tool call and its response in the message graph for persistence and future reference.
    :param message_id: The Discord ID of the original message.
    :param tool_call_message_id: The Discord ID of the tool call message.
    :param tool_response_message_id:  The Discord ID of the tool response message.
    :param command: The command executed by the tool.
    :param response: The response generated by the tool.
    """
    message_graph.add_message(tool_call_message_id, "assistant", command, time.time(), reply_to=message_id)
    message_graph.add_message(tool_response_message_id, "system", response, time.time(),
                              reply_to=tool_call_message_id)


def execute_python(code: str) -> Tuple[str, str]:
    """
    Executes Python code using a DockerPythonExecutor.
    Returns the output and any error encountered during execution.
    :param code: The Python code to execute.
    :return: A tuple containing the output and error messages. One of them will be None.
    """
    executor = DockerPythonExecutor()
    output, error = executor.run_code(code)
    return output, error


# Message Scraping Functions


async def scrape_and_save_messages(scrape_messages_channel_id: int, after_date: str) -> None:
    messages = await fetch_messages_after_date(scrape_messages_channel_id, after_date)
    print(f"Number of messages fetched: {len(messages)}")
    # Extract the contents of the messages
    message_content = [f"{message.content}" for message in messages]
    # save the contents of the messages to a file using the GetMessages.py script
    save_messages(message_content)

    # Save each username's messages to a separate file
    usernames = [f"{message.author.display_name}" for message in messages]
    unique_usernames = set(usernames)
    # save each username's messages to a separate file
    for username in unique_usernames:
        user_messages = [f"{message.content}" for message in messages if message.author.display_name == username]
        save_messages(user_messages, f"individual/{username}.csv")


async def fetch_messages_after_date(channel_id: int, after_date: str) -> List[discord.Message]:
    """
    Fetches messages from a channel after a specified date.
    :param channel_id: The ID of the channel to fetch messages from.
    :param after_date: The date in the format 'YYYY-MM-DD' to fetch messages after.
    :return: A list of messages fetched from the channel, or None if an error occurred.
    """

    if not channel_id:
        print("Channel ID not provided.")
        return []
    if not after_date:
        print("After date not provided.")
        return []

    channel = discord_client.get_channel(channel_id)
    if not channel:
        print(f"Channel with ID {channel_id} not found.")
        return []

    try:
        after_datetime = datetime.strptime(after_date, '%Y-%m-%d')
    except ValueError:
        print("Invalid date format. Please use 'YYYY-MM-DD'.")
        return []

    messages = []

    # Fetch messages
    async for message in channel.history(after=after_datetime, limit=None, oldest_first=True):
        messages.append(message)

    return messages


# Final setup
discord_client.run(DISCORD_API_KEY)
# Ensure that the message graph is saved when the bot exits
atexit.register(lambda: message_graph.save_messages())
