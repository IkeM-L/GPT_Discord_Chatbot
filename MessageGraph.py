import json
from datetime import datetime, timedelta

from MessageNode import MessageNode


class MessageGraph:
    def __init__(self, file_path):
        self.messages = {}
        self.file_path = file_path
        self.load_messages()

    def add_message(self, message_id, role, content, timestamp, reply_to=None, tool_call=None):
        """
        Add a new message to the graph.
        :param message_id: The discord ID of the message.
        :param role: The role of the message (user, assistant, or tool).
        :param content: The content of the message, as a string.
        :param timestamp: The timestamp of the message.
        :param reply_to: The ID of the message to which this message is a reply, or None if it is not a reply.
        :param tool_call: The ID of the tool call associated with this message, or None if it is not a tool call.
        :return:
        """
        if message_id is None:  # While not recommended, it is possible to use any data type as message IDs
            return "Message ID cannot be None"
        if role is None or role not in ["user", "assistant", "tool", "system"]:
            return "Invalid role"
        if content is None:
            return "Content cannot be None"
        if timestamp is None:
            return "Timestamp cannot be None"

        new_message = MessageNode(message_id, role, content, timestamp, parent_id=reply_to, tool_call=tool_call)
        self.messages[message_id] = new_message

    def get_message_chain(self, message_id):
        """
        Build a chain of messages starting from the given message and including the 'chain' of replies to it.
        :param message_id:  The discord ID of the message.
        :return: A list of dictionaries, each containing the role and content of a message in the chain.
        """
        if message_id not in self.messages:
            return "Message not found"

        chain = []
        current_id = message_id

        while current_id:
            current_node = self.messages[current_id]
            if current_node.role == "tool":
                chain.append({"role": current_node.role, "content": current_node.content,
                              "tool_call_id": current_node.tool_call})
            else:
                chain.append({"role": current_node.role, "content": current_node.content})
            current_id = current_node.parent_id

        return chain[::-1]

    def get_message_role(self, message_id):
        """
        Get the role of the message with the given ID.
        :param message_id:  The discord ID of the message.
        :return: The role of the message as a string, or "None" if the message is not found.
        """
        if message_id not in self.messages:
            return "None"

        return self.messages[message_id].role

    def save_messages(self):
        """
        Save the messages to a JSON file.
        """
        with open(self.file_path, 'w') as file:
            json.dump({mid: node.to_dict() for mid, node in self.messages.items()}, file)

    def load_messages(self):
        """
        Load the messages from a JSON file, or create an empty graph if the file does not exist.
        """
        try:
            with open(self.file_path, 'r') as file:
                data = json.load(file)
                one_week_ago = datetime.now() - timedelta(weeks=1)

                for mid, mdata in data.items():
                    if datetime.fromtimestamp(mdata["timestamp"]) > one_week_ago:
                        self.messages[mid] = MessageNode.from_dict(mdata)

        except FileNotFoundError:
            pass  # File not found, so we start with an empty graph

    def delete_old_messages(self):
        """
        Delete messages older than one year.
        """
        one_year_ago = datetime.now() - timedelta(weeks=52)
        to_delete = [mid for mid, node in self.messages.items() if datetime.fromtimestamp(node.timestamp) < one_year_ago]

        for mid in to_delete:
            del self.messages[mid]

        self.save_messages()

    def __del__(self):
        """
        Save the messages when the object is deleted.
        """
        self.save_messages()
