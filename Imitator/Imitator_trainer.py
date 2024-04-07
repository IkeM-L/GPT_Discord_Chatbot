import os
import pandas as pd
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from IMITATOR_CONFIG import csv_path, model_path

# Set up paths and parameters
model_name = "distilgpt2"
output_dir = model_path
num_epochs = 3
batch_size = 4
learning_rate = 1e-5

# Load and preprocess the CSV data
try:
    df = pd.read_csv(csv_path)
except FileNotFoundError:
    raise FileNotFoundError(f"File not found at {csv_path}")
except Exception as e:
    raise Exception(f"An error occurred: {e}")
messages = df["message"].tolist()

# Create a Dataset from the messages
dataset = Dataset.from_dict({"text": messages})

# Load the tokenizer and model
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# Set the padding token
tokenizer.pad_token = tokenizer.eos_token

# Tokenize the dataset
def tokenize_function(examples):
    return tokenizer(examples["text"], truncation=True, padding="max_length", max_length=512)


tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["text"])

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

# Save the fine-tuned model
trainer.save_model(output_dir)