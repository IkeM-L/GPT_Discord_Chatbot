class MessageNode:
    def __init__(self, message_id, role, content, timestamp, parent_id=None, tool_call=None):
        self.message_id = message_id
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.parent_id = parent_id  # Pointer to the parent message
        self.tool_call = tool_call

    def to_dict(self):
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
        return MessageNode(data["message_id"], data["role"], data["content"], data["timestamp"], data["parent_id"], data["tool_call"])