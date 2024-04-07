import csv
#from IMITATOR_CONFIG import csv_path
csv_path = "messages.csv"


def save_messages(messages, path=csv_path):
    """Save a list of messages to a CSV file."""
    # Open the CSV file in write mode
    with open(path, "w", newline="", encoding="utf-8") as file:
        # Create a CSV writer object
        writer = csv.writer(file)

        # Write the header row
        writer.writerow(["message"])

        # Write each message as a row in the CSV file
        for message in messages:
            writer.writerow([message])


# Assume the messages are stored in a variable called 'messages'
test_messages = [
    "Hello, how are you?",
    "I'm doing great, thanks for asking!",
    "What have you been up to lately?",
    "Not much, just working on some projects.",
    "That sounds interesting. Tell me more!",
]

# Save the messages to a CSV file
# save_messages(test_messages)
# print(f"Messages saved to {csv_path}")