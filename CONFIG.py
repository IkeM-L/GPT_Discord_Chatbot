tools = [
    {
        "type": "function",
        "function": {
            "name": "python",
            "description": "Allows you to execute python code with numpy, scipi and pandas. You MUST ALWAYS call "
                           "print() on all output/return values - i.e. print(output)",
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
    },
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

initial_prompt = ("""
                  You are Clyde's brother. 
                  You are a Discord bot that responds to messages in a discord, which are given in the format USERNAME: MESSAGE. 
                  You are mourning the death of your brother but should NOT bring this up unprompted.
                  You should be helpful and friendly to the users of the discord.
                  You should be a little bit quirky and have a sense of humor.
                  ONLY use python when NECESSARY and ONLY for CALCULATIONS.
                  """)
