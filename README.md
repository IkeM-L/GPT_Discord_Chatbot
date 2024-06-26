# A GPT-based Discord bot

## Run the main bot

To run the bot, add a secrets.json with the following variables:

```json
{
  "discord_api_key": "YOUR API KEY",
  "openai_api_key": "YOUR API KEY"
}
```

Then run the bot with `python ClydesBrother.py`

## CONFIG.py

The CONFIG.py file is used to define the tools that the bot can use and it's initial prompt.

The below are the default tool definitions:

## Python Tool Use

To enable python tool use, the following is in the CONFIG.py file:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "python",
            "description": "Allows you to execute python code with numpy, scipi and pandas. You MUST ALWAYS call print() on all output/return values - i.e. print(output)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The python code to execute. MUST print the output using print()"
                    }
                },
                "required": [
                    "command"
                ]
            }
        }
    }
]
```

This will allow the bot to execute python code in a container. See ``DockerPythonExecutor.py`` for more information.

## Timer tool use

To allow the bot to set timers, the following is in the CONFIG.py file:

```python
tools = [
    {
      "type": "function",
           "function": {
               "name": "timer",
               "description": "Allows you to set timers when the user requests it. "
                              "You MUST include EITHER the time OR the relative_time parameter.",
               "parameters": {
                   "type": "object",
                   "properties": {
                       "time": {
                           "type": "string",
                           "description": "The ISO date for the timer"
                       },
                       "relative_time": {
                           "type": "string",
                           "description": "The relative time for the timer, in the format DD:HH:MM:SS"
                       },
                       "name": {
                           "type": "string",
                           "description": "The name of the timer"
                       }
                   },
                   "required": [
                       "name"
                   ]
               }
           }
       }
]
```

NB: If you already have other tools available, you can add it to the list of tools

## Imitator Submodule

This project also includes a tool to imitate the writing style of a list of messages in the Imitator folder. The bot can scrape a discord channel and save the messages to a file, with separate files for each user of the discord saved to the ``individual`` directory. It will scrape when the ``scrape_messages`` variable is true.

The bot will have a ``responce_chance`` chance to respond in the channel that is scraped.

In order to train the model, you will need to:

1. Install the required packages 
2. Create an ``IMITATOR_CONFIG.py`` file with the following variables:
   1. csv_path
   2. model_path
   3. OPTIONAL: huggingface_token 
      - Your huggingface access token, only needed for training/running inference on gated models
      - Note: Do not add this if training in the huggingface cloud, instead add it to secrets in your space
3. Create a ``messages.csv`` file in the Imitator directory, for example by scraping a discord channel and copying it.
   - This is a manual step to avoid accidental data loss as scraping a discord channel can be slow
4. Run one of
   - ``python Imitator_trainer.py`` - This will train a model locally on your hardware
   - ``python trainer_huggingface_cloud.py`` - This will train a model and is adjusted to be compatible with the huggingface cloud, for example by loading secrets from the environment
   - ``python trainer_huggingface_cloud_with_peft.py`` - This is also compatible with the huggingface cloud, but uses PEFT (parameter efficient fine-tuning) to train larger models more efficiently and in a quantised form. I have used the 2xA10 node to train the model currently set
   - Note: To run on the cloud in a docker container, use the provided Dockerfile and adjust the file run at the end
   - Note: The cloud training scripts will save the model to the huggingface cloud, but as a private model.

In order to run inference on the model, run ``python imitator_message_gen.py`` or the dev version ``python message_gen_dev.py``. This will generate a message in the style of the messages in the ``messages.csv`` file.

Note: The non-dev version will use the ``distillgpt2`` tokenizer, this should  be changed to the tokenizer used in training if you are using a different model 

## Magic Story Scraping

The bot will check the WotC website for new magic story updated every half an hour and, if a new one is found, send it to the given channel. See ``FindNewMagicStory.py`` for more information.

It can be used by running ``check_for_new_magic_stories()``