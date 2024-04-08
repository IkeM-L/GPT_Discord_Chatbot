import atexit
import random
from datetime import datetime
import discord
import json
import time
from discord.ext import tasks, commands

from FindNewMagicStory import MagicStoryChecker
from DockerPythonExecutor import DockerPythonExecutor
from Imitator.IMITATOR_CONFIG import model_path
from Imitator.imitator_message_gen import generate_message
from MessageGraph import MessageGraph
from openai import OpenAI
from CONFIG import discord_api_key, openai_api_key, tools, initial_prompt
from Imitator.GetMessages import save_messages

# Initialize clients and important variables
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
discord_client = discord.Client(intents=intents)
openai_client = OpenAI(api_key=openai_api_key)
model = "gpt-4-turbo-preview"
message_graph = MessageGraph('message_history.json')
scrape_messages = False
response_chance = 0.05

# Channels for special actions
scrape_messages_channel_id = 944200738605776906
magic_story_channel_id = 1032688705128902788


# Tasks
@tasks.loop(minutes=30)
async def post_new_articles():
    """Check for and post new Magic Story articles."""
    channel_id = magic_story_channel_id  # Specific channel ID
    channel = discord_client.get_channel(channel_id)

    if channel is None:
        print(f"Channel with ID {channel_id} not found.")
        return

    checker = MagicStoryChecker('https://magic.wizards.com/en/news/magic-story')
    new_articles = checker.get_new_articles()
    if not new_articles:
        # Uncomment the next line if you want to log when no new articles are found
        # print("No new articles found.")
        return

    await channel.send("New Magic Story articles found:")
    for article in reversed(new_articles):
        await channel.send(f"https://magic.wizards.com{article}")


# Event Handlers
@discord_client.event
async def on_ready():
    """
    Runs when the bot is ready and starts various tasks.
    """
    print(f'We have logged in as {discord_client.user}')
    post_new_articles.start()
    if scrape_messages:
        messages = await fetch_messages_after_date(scrape_messages_channel_id, "2023-01-02")
        print(f"Number of messages fetched: {len(messages)}")
        # Extract the contents of the messages
        message_content = [f"{message.content}" for message in messages]
        # save the contents of the messages to a file using the GetMessages.py script
        save_messages(message_content)
        usernames = [f"{message.author.display_name}" for message in messages]
        unique_usernames = set(usernames)
        # save each username's messages to a separate file
        for username in unique_usernames:
            user_messages = [f"{message.content}" for message in messages if message.author.display_name == username]
            save_messages(user_messages, f"individual/{username}.csv")


@discord_client.event
async def on_message(message):
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
        message.content = message.content[9:]
        async with message.channel.typing():
            response = generate_message(message.content, model_path)
            await message.reply(response)
        return

    # Parse the message
    message_details = parse_message(message)

    # check if the bot's ID is in mentions
    bot_mentioned = discord_client.user.id in [mention.id for mention in message.mentions]

    global response_chance

    # Ignore messages that don't mention the bot or reply to a message in the graph
    if message_details['author_role'] == "user" and not bot_mentioned and not message_details['reply_to_id']:
        # chance of responding to a message that doesn't mention the bot using custom model
        if random.random() < response_chance and message.channel == discord_client.get_channel(scrape_messages_channel_id):
            async with message.channel.typing():
                response = generate_message(message.content, model_path)
                await message.reply(response)
                print("Responded with custom model by chance")
        return

    # Ignore messages that don't reply to a user message
    if message_graph.get_message_role(message_details['reply_to_id']) == "user":
        return

    # Add the message to the message graph
    message_graph.add_message(message_details['id'], message_details['author_role'], message_details['content'],
                              time.time(), reply_to=message_details['reply_to_id'])

    # start the BOT is typing indicator
    async with message.channel.typing():
        # Process the message and send a response
        response, error = await process_message(message_details)
        
    if error:
        async with message.channel.typing():
            await message.reply(error)
        return

    if response.tool_calls:
        async with message.channel.typing():
            await process_tool_calls(message, response)
    else:
        async with message.channel.typing():
            await finalize_message_response(message, response, message_details['id'])


async def process_message(message_details):
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


def prepend_initial_prompt(message_id):
    """
    Prepends the initial prompt to the message chain if necessary.
    :param message_id: The ID of the message to prepend the initial prompt to.
    """
    if not message_id:
        return

    system_message_id = f"{message_id}_system"
    message_graph.add_message(system_message_id, "system", initial_prompt, time.time())
    message_graph.messages[message_id].parent_id = system_message_id


async def process_custom_prompt(message):
    """
    Adds a custom prompt to the message graph, so any replies to it will be generated based on the prompt.
    :param message: The message object containing the custom prompt.
    """
    if not message:
        return

    # Exclude the "prompt:" prefix
    prompt = message.content[7:]
    # Trim whitespace
    prompt = prompt.strip()
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


async def fetch_response_from_openai(message_chain):
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


def parse_message(message):
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


def parse_reply_to_id(message):
    """
    Extracts reply-to ID if available.
    :param message: The message object.
    :return: The ID of the message being replied to, or None if there is no reply.
    """
    if message.reference and message.reference.message_id:
        reply_to_id = message.reference.message_id
        return reply_to_id if reply_to_id in message_graph.messages else None
    return None


async def finalize_message_response(original_message, response, message_id):
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


async def process_tool_calls(message, response):
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
        # Example: Add new tool handlers here
        # elif tool_name == "new_tool":
        #     await handle_new_tool_call(message, tool_call)
        else:
            print(f"No handler for tool: {tool_name}")


async def handle_python_tool_call(message, tool_call):
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

    command = tool_call.function.arguments
    # Parse the command in case it's in JSON format
    command = parse_command_from_json(command)
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


def parse_command_from_json(command):
    """
    Attempts to parse the command from a JSON string.
    If the command is not a JSON string, or if it doesn't contain the "command" key,
    it returns the original command.
    Note: The GPT API is inconsistent in how it formats the tool calls, so this function makes sure it is parsed correctly.
    :param command: The command to parse, this can be a JSON string or a regular string.
    :return: The parsed command, or the original command if it couldn't be parsed.
    Usually the original command is the correct tool call, just not in JSON format.
    """
    try:
        parsed_command = json.loads(command)
        return parsed_command.get("command", command)
    except json.JSONDecodeError:
        return command


def log_tool_call_in_message_graph(message_id, tool_call_message_id, tool_response_message_id, command, response):
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


def execute_python(code):
    """
    Executes Python code using a DockerPythonExecutor.
    Returns the output and any error encountered during execution.
    :param code: The Python code to execute.
    :return: A tuple containing the output and error messages. One of them will be None.
    """
    executor = DockerPythonExecutor()
    output, error = executor.run_code(code)
    return output, error


async def fetch_messages_after_date(channel_id, after_date):
    """
    Fetches messages from a channel after a specified date.
    :param channel_id: The ID of the channel to fetch messages from.
    :param after_date: The date in the format 'YYYY-MM-DD' to fetch messages after.
    :return: A list of messages fetched from the channel, or None if an error occurred.
    """

    if not channel_id:
        print("Channel ID not provided.")
        return
    if not after_date:
        print("After date not provided.")
        return

    channel = discord_client.get_channel(channel_id)
    if not channel:
        print(f"Channel with ID {channel_id} not found.")
        return

    try:
        after_datetime = datetime.strptime(after_date, '%Y-%m-%d')
    except ValueError:
        print("Invalid date format. Please use 'YYYY-MM-DD'.")
        return

    messages = []

    # Fetch messages
    async for message in channel.history(after=after_datetime, limit=None, oldest_first=True):
        messages.append(message)

    return messages


# Final setup
discord_client.run(discord_api_key)
atexit.register(lambda: message_graph.save_messages())
