import os
import pandas as pd
import torch
import transformers
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer, \
    DataCollatorForLanguageModeling, BitsAndBytesConfig
from peft import prepare_model_for_kbit_training, LoraConfig, get_peft_model
from IMITATOR_CONFIG import csv_path, model_path

# Set up paths and parameters
model_name = "meta-llama/Llama-2-7b-chat-hf"
output_dir = model_path + "-tmp"
num_epochs = 5
batch_size = 3
learning_rate = 2.5e-5
PYTORCH_CUDA_ALLOC_CONF = 'expandable_segments:True'

# Load and preprocess the CSV data
df = pd.read_csv(csv_path)
df['message'] = df['message'].apply(lambda x: str(x) if not pd.isnull(x) else '')
messages = df["message"].tolist()
prompts = messages[:-1]
responses = messages[1:]
print("Loaded and preprocessed the CSV data.")

# Create a dictionary with prompts and responses
data_dict = {"prompt": prompts, "response": responses}
print("Created a dictionary with prompts and responses.")

# Convert the conversational pairs into a Dataset
dataset = Dataset.from_dict(data_dict)
print("Converted the conversational pairs into a Dataset.")

# Load the tokenizer and model
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, quantization_config=bnb_config, device_map="auto")
print("Loaded the tokenizer and model.")

# Apply PEFT to prepare the model for k-bit training
model.gradient_checkpointing_enable()
model = prepare_model_for_kbit_training(model)
config = LoraConfig(
    r=8,
    lora_alpha=32,
    # target_modules=["query_key_value"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)

model = get_peft_model(model, config)
print("Applied PEFT to prepare the model for k-bit training.")

# Ensure padding token is set correctly
tokenizer.pad_token = tokenizer.eos_token # should this be EOS token?


# Tokenize the dataset
def tokenize_function(examples):
    concatenated_examples = [p + "<|ENDOFPROMPT>" + tokenizer.eos_token + r for p, r in zip(examples['prompt'], examples['response'])]
    return tokenizer(concatenated_examples, truncation=True, padding="max_length", max_length=512)


tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=["prompt", "response"])
print("Tokenized the dataset.")


# Data collator
data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer,
    mlm=False,
)

# Set up training arguments
training_args = TrainingArguments(
    output_dir=output_dir,
    num_train_epochs=num_epochs,
    per_device_train_batch_size=batch_size,
    learning_rate=learning_rate,
    save_strategy="epoch",
    logging_steps=100,
    report_to="none",  # Avoid setting up any logging service
)

trainer = transformers.Trainer(
    model=model,
    train_dataset=tokenized_dataset,
    args=transformers.TrainingArguments(
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        warmup_steps=2,
        max_steps=10,
        learning_rate=learning_rate,
        fp16=True,
        logging_steps=1,
        output_dir="outputs",
        optim="paged_adamw_8bit"
    ),
    data_collator=transformers.DataCollatorForLanguageModeling(tokenizer, mlm=False),
)
print("Initialized the Trainer.")

# Fine-tune the model
trainer.train()

# Save the fine-tuned model to cloud
tokenizer.push_to_hub(output_dir, private=True)
model.push_to_hub(output_dir, private=True)
print("Saved the fine-tuned model.")

# Save the fine-tuned model
trainer.save_model(output_dir)
tokenizer.save_pretrained(output_dir + "_tokenizer")
