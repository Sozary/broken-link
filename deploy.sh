#!/bin/bash

# Pull
git pull

# Build and start the containers
docker-compose up -d --build

