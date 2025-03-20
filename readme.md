# Broken Link

## Install docker

### Update system

`sudo apt update && sudo apt upgrade -y`

### Install Docker

`curl -fsSL https://get.docker.com -o get-docker.sh`
`sudo sh get-docker.sh`

### Install Docker Compose

`sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose`
`sudo chmod +x /usr/local/bin/docker-compose`

## Setup the configuration

Create a .env file with your production settings:

```
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=["https://your-frontend-domain.com"]
```

## Run the deployment

`./deploy.sh`
