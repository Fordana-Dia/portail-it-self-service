![CI](https://github.com/Fordana-Dia/portail-it-self-service/actions/workflows/ci.yml/badge.svg)

# Portail IT Self-Service Sécurisé

Projet de stage (ETS The Future World, 2026) noté 18/20 : un portail qui provisionne automatiquement des environnements de développement conteneurisés (PostgreSQL + backend + frontend) en moins de 30 secondes.

## Fonctionnalités
- Provisionnement automatisé d'environnements Docker, chacun isolé dans son propre réseau
- Authentification JWT et mots de passe hachés (bcrypt)
- Contrôle d'accès par rôles (RBAC, 4 niveaux)
- Rate limiting et protection anti-brute-force
- Tableau de bord de supervision en temps réel (WebSocket)
- Mot de passe de base de données unique et aléatoire pour chaque environnement

## Stack
Python · FastAPI · PostgreSQL · SQLAlchemy · Docker / Docker Compose · Nginx · Terraform · GitHub Actions · GitLab CI

## Lancer le projet
```bash
cp .env.example .env   # puis remplir les valeurs
docker compose up -d --build
```
- Interface : http://localhost:3000
- API (documentation) : http://localhost:8000/docs

## Sécurité
Aucun secret n'est stocké dans le code : la clé JWT et les mots de passe sont lus depuis le fichier `.env`, exclu du dépôt.
