 # This is a Dockerfile for training on the huggingface cloud, it should work locally as well
 # Use an official Python runtime as a parent image
FROM python:latest

# Set up a new user named "user" with user ID 1000
RUN useradd -m -u 1000 user

# Switch to the "user" user
USER user

# Set home to the user's home directory
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

# Set the working directory to the user's home directory
WORKDIR $HOME/app

# Try and run pip command after setting the user with `USER user` to avoid permission issues with Python
RUN pip install --no-cache-dir --upgrade pip

# Copy the current directory contents into the container at $HOME/app setting the owner to the user
COPY --chown=user . $HOME/app

# Copy the current directory contents into the container at /usr/src/app
COPY . /usr/src/app

# Install any needed packages
RUN pip install --no-cache-dir pandas datasets transformers accelerate bitsandbytes peft

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV MODEL_NAME=distilgpt2

# Run script.py when the container launches
CMD ["python", "./trainer_huggingface_cloud_with_peft.py"]
