class MessageNode:
    def __init__(self, message_id, role, content, timestamp, parent_id=None, tool_call=None):
        """
        Initialize a new message node.
        :param message_id:  The discord ID of the message.
        :param role: The role of the message (user, assistant, or tool).
        :param content: The content of the message, as a string.
        :param timestamp: The timestamp of the message.
        :param parent_id: The ID of the message to which this message is a reply, or None if it is not a reply.
        :param tool_call: The ID of the tool call associated with this message, or None if it is not a tool call.
        """
        self.message_id = message_id
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.parent_id = parent_id  # 'Pointer' to the parent message
        self.tool_call = tool_call

    def to_dict(self):
        """
        Convert the message node to a dictionary.
        :return: A dictionary containing the message node data:
        message_id, role, content, timestamp, parent_id, tool_call.
        """
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "parent_id": self.parent_id,
            "tool_call": self.tool_call
        }

    @staticmethod
    def from_dict(data):
        """
        Create a new message node from a dictionary.
        :param data: A dictionary containing the message node data
        :return: A new MessageNode object.
        """
        return MessageNode(data["message_id"], data["role"], data["content"], data["timestamp"], data["parent_id"], data["tool_call"])
