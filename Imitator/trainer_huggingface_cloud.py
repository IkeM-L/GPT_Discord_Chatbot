import pandas as pd
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from IMITATOR_CONFIG import csv_path, model_path

# Set up paths and parameters
model_name = "meta-llama/Llama-2-7b-chat-hf"  # Consider using "microsoft/DialoGPT-medium" for a conversational model
output_dir = model_path
num_epochs = 5
batch_size = 5
learning_rate = 1e-3

# Load and preprocess the CSV data
df = pd.read_csv(csv_path)
df['message'] = df['message'].apply(lambda x: str(x) if not pd.isnull(x) else '')
messages = df["message"].tolist()

# Assuming `messages` is a list of text messages from your dataset
prompts = messages[:-1]  # All messages except the last one as prompts
responses = messages[1:]  # All messages except the first one as responses

# Create a dictionary with prompts and responses
data_dict = {"prompt": prompts, "response": responses}

# Correctly converting the conversational pairs into a Dataset
dataset = Dataset.from_dict(data_dict)


# Load the tokenizer and model
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# Set the padding token
tokenizer.pad_token = tokenizer.eos_token

# Tokenize the dataset
def tokenize_function(examples):
    concatenated_examples = [p + " <|endoftext|> " + r for p, r in zip(examples['prompt'], examples['response'])]
    return tokenizer(concatenated_examples, truncation=True, padding="max_length", max_length=512)

tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["prompt", "response"])


# Set up training arguments
training_args = TrainingArguments(
    output_dir=output_dir,
    num_train_epochs=num_epochs,
    per_device_train_batch_size=batch_size,
    learning_rate=learning_rate,
    save_strategy="epoch",
    logging_steps=100,
)


# Create a custom Trainer class
class CustomTrainer(Trainer):
    """Custom Trainer class to compute loss with correct labels"""
    def compute_loss(self, model, inputs, return_outputs=False):
        labels = inputs["input_ids"].clone()
        labels[labels == tokenizer.pad_token_id] = -100
        outputs = model(**inputs, labels=labels)
        loss = outputs.loss
        return (loss, outputs) if return_outputs else loss


# Create a Trainer instance with the custom Trainer class
trainer = CustomTrainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
)

# Fine-tune the model
trainer.train()

# Save the fine-tuned model to cloud
tokenizer.push_to_hub(output_dir, private=True)
model.push_to_hub(output_dir, private=True)
print("Saved the fine-tuned model.")

# Save the fine-tuned model
trainer.save_model(output_dir)
tokenizer.save_pretrained(output_dir + "_tokenizer")
