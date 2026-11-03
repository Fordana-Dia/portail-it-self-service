variable "env_dev_port" {
  description = "Port externe pour l'environnement de développement"
  type        = number
  default     = 8081
}

variable "env_staging_port" {
  description = "Port externe pour l'environnement de staging"
  type        = number
  default     = 8082
}

variable "project_name" {
  description = "Nom du projet"
  type        = string
  default     = "portail-it"
}
