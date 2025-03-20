#!/bin/bash

# Pull the latest changes
git pull

# Build and start the containers
docker-compose up -d --build

# Show the status of the containers
docker-compose ps 