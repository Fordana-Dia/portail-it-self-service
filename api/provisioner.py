import secrets
import docker
import random

client = docker.from_env()

def get_free_port(start=9000, end=9999):
    used_ports = set()
    for container in client.containers.list():
        for port_bindings in container.ports.values():
            if port_bindings:
                for binding in port_bindings:
                    used_ports.add(int(binding['HostPort']))
    for port in range(start, end):
        if port not in used_ports:
            return port
    raise RuntimeError("Plus de ports disponibles")

def provision_fullstack(env_name: str):
    network_name = f"net-{env_name}"
    
    # Créer le réseau isolé
    try:
        network = client.networks.create(network_name, driver="bridge")
    except Exception:
        network = client.networks.get(network_name)

    # Ports dynamiques avec plages séparées
    db_port = get_free_port(9100, 9199)
    backend_port = get_free_port(9200, 9299)
    frontend_port = get_free_port(9300, 9399)

    db_password = secrets.token_urlsafe(16)

    # Conteneur PostgreSQL
    db = client.containers.run(
        "postgres:15",
        name=f"db-{env_name}",
        environment={
            "POSTGRES_USER": "dev",
            "POSTGRES_PASSWORD": db_password,
            "POSTGRES_DB": f"db_{env_name}"
        },
        network=network_name,
        ports={"5432/tcp": db_port},
        detach=True,
        remove=False
    )

    # Conteneur Backend (FastAPI simple)
    backend = client.containers.run(
        "tiangolo/uvicorn-gunicorn-fastapi:python3.11",
        name=f"backend-{env_name}",
        environment={
            "DATABASE_URL": f"postgresql://dev:{db_password}@db-{env_name}/db_{env_name}"
        },
        network=network_name,
        ports={"80/tcp": backend_port},
        detach=True,
        remove=False
    )

    # Conteneur Frontend (Nginx)
    frontend = client.containers.run(
        "nginx:alpine",
        name=f"frontend-{env_name}",
        network=network_name,
        ports={"80/tcp": frontend_port},
        detach=True,
        remove=False
    )

    return {
        "env_name": env_name,
        "network": network_name,
        "services": {
            "database": {
                "container": f"db-{env_name}",
                "port": db_port,
                "status": "running"
            },
            "backend": {
                "container": f"backend-{env_name}",
                "url": f"http://192.168.1.172:{backend_port}",
                "status": "running"
            },
            "frontend": {
                "container": f"frontend-{env_name}",
                "url": f"http://192.168.1.172:{frontend_port}",
                "status": "running"
            }
        }
    }

def destroy_environment(env_name: str):
    destroyed = []
    for prefix in ["frontend", "backend", "db"]:
        try:
            container = client.containers.get(f"{prefix}-{env_name}")
            container.stop()
            container.remove()
            destroyed.append(f"{prefix}-{env_name}")
        except Exception:
            pass
    try:
        network = client.networks.get(f"net-{env_name}")
        network.remove()
    except Exception:
        pass
    return {"destroyed": destroyed}

def list_environments():
    containers = client.containers.list()
    envs = {}
    for c in containers:
        name = c.name
        for prefix in ["frontend-", "backend-", "db-"]:
            if name.startswith(prefix):
                env_name = name.replace(prefix, "")
                if env_name not in envs:
                    envs[env_name] = {"services": {}, "env_name": env_name}
                service_type = prefix.replace("-", "")
                ports = c.ports
                url = None
                for container_port, host_bindings in ports.items():
                    if host_bindings:
                        url = f"http://192.168.1.172:{host_bindings[0]['HostPort']}"
                envs[env_name]["services"][service_type] = {
                    "container": name,
                    "status": c.status,
                    "url": url
                }
    return list(envs.values())

def get_container_stats():
    """Récupère CPU% et RAM (MB) de tous les conteneurs gérés par le portail."""
    results = []
    for container in client.containers.list():
        name = container.name
        if not (name.startswith("db-") or name.startswith("backend-") or name.startswith("frontend-")):
            continue
        try:
            stats = container.stats(stream=False)

            # Calcul CPU %
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                num_cpus = stats["cpu_stats"].get("online_cpus", 1)
                cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0

            # Calcul RAM
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)
            mem_mb = mem_usage / (1024 * 1024)
            mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0

            results.append({
                "container": name,
                "status": container.status,
                "cpu_percent": round(cpu_percent, 2),
                "mem_mb": round(mem_mb, 1),
                "mem_percent": round(mem_percent, 2)
            })
        except Exception as e:
            results.append({"container": name, "status": "error", "error": str(e)})
    return results
