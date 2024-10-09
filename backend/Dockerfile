# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8000 (this is just a default, the actual port will be determined at runtime)
EXPOSE 8000

# Command to run your Flask app using Gunicorn with the dynamic port
CMD gunicorn --bind 0.0.0.0:$PORT server:app