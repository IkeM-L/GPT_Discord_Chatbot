import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from Imitator.IMITATOR_CONFIG import model_path


def generate_message(input_message, model_path, tokenizer_path=model_path):
    """Generate a response message given an input message using a model."""
    # Assume the model and tokenizer are saved in the same directory: model_path
    tokenizer = AutoTokenizer.from_pretrained("distilgpt2")  # Forgot to save the tokenizer, use the default one
    # TODO: save the tokenizer in the training script
    model = AutoModelForCausalLM.from_pretrained(model_path)

    # Adjust if your model was trained with specific token as a delimiter, else keep using eos_token
    tokenizer.pad_token = tokenizer.eos_token

    # Tokenize the input message, ensuring it's prepared the same way as during training
    input_ids = tokenizer.encode(input_message + " <|endoftext|> ", return_tensors="pt")

    # Generate the response
    output = model.generate(
        input_ids,
        max_length=50,  # Adjust as needed
        num_return_sequences=1,
        no_repeat_ngram_size=2,
        early_stopping=True,
        pad_token_id=tokenizer.eos_token_id,
        temperature=0.7,  # Adjust for creativity/diversity of responses
        num_beams=5,  # Adjust for diversity of responses
        do_sample=True,  # To enable sampling
    )

    # Decode the generated response, ensuring to skip any special tokens.
    response = tokenizer.decode(output[0], skip_special_tokens=True)

    return response[len(input_message):]

# Example usage
'''
input_message = "went for the throat"
generated_message = generate_message(input_message, model_path)
print("Input:", input_message)
print("Generated Response:", generated_message)
'''