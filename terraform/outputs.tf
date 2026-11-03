output "env_dev_url" {
  description = "URL de l'environnement de développement"
  value       = "http://localhost:${var.env_dev_port}"
}

output "env_staging_url" {
  description = "URL de l'environnement de staging"
  value       = "http://localhost:${var.env_staging_port}"
}

output "network_name" {
  description = "Nom du réseau Docker créé"
  value       = docker_network.env_network.name
}
