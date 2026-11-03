terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

# Réseau pour les environnements provisionnés
resource "docker_network" "env_network" {
  name = "portail_it_network"
}

# Environnement de développement
resource "docker_container" "env_dev" {
  name  = "env-dev-server"
  image = "nginx:alpine"

  networks_advanced {
    name = docker_network.env_network.name
  }

  ports {
    internal = 80
    external = 8081
  }

  labels {
    label = "environment"
    value = "development"
  }

  labels {
    label = "managed_by"
    value = "portail_it"
  }
}

# Environnement de staging
resource "docker_container" "env_staging" {
  name  = "env-staging-server"
  image = "nginx:alpine"

  networks_advanced {
    name = docker_network.env_network.name
  }

  ports {
    internal = 80
    external = 8082
  }

  labels {
    label = "environment"
    value = "staging"
  }

  labels {
    label = "managed_by"
    value = "portail_it"
  }
}
