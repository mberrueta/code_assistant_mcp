# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install uv
RUN pip install uv

# Copy the requirements file into the container at /app
COPY ./app/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN uv pip install --no-cache-dir --system -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY ./app .

# Make port 80 available to the world outside this container
EXPOSE 80

# Run app.main:app when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
