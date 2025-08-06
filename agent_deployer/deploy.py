"""
Deployment functionality for agent-deployer
"""
import os
import subprocess
import shutil
import tempfile
from pathlib import Path
from string import Template

# Templates for configuration files
SYSTEMD_TEMPLATE = """[Unit]
Description=$service_name service
After=network.target

[Service]
User=$user
Group=$group
WorkingDirectory=$project_path
ExecStart=$exec_start
Restart=always
RestartSec=5
Environment=PATH=$venv_path/bin:$PATH
$environment_vars

[Install]
WantedBy=multi-user.target
"""

# Basic Nginx template for API only
NGINX_TEMPLATE = """server {
    listen 80;
    server_name $domain;

    location / {
        proxy_pass http://localhost:$port;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""

# Nginx template for API with SSL
NGINX_SSL_TEMPLATE = """server {
    listen 80;
    server_name $domain;
    return 301 https://$domain$request_uri;
}

server {
    listen 443 ssl;
    server_name $domain;

    ssl_certificate /etc/letsencrypt/live/$domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$domain/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;

    location / {
        proxy_pass http://localhost:$port;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""

# Nginx template for frontend + API
NGINX_FRONTEND_TEMPLATE = """server {
    listen 80;
    server_name $domain;

    # API endpoints
    location $api_url_prefix/ {
        proxy_pass http://localhost:$port$api_url_prefix/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend static files
    location $frontend_url_prefix {
        alias $frontend_path/;
        try_files $uri $uri/ $frontend_url_prefix/index.html;
        expires 1d;
        add_header Cache-Control "public";
    }
}
"""

# Nginx template for frontend + API with SSL
NGINX_FRONTEND_SSL_TEMPLATE = """server {
    listen 80;
    server_name $domain;
    return 301 https://$domain$request_uri;
}

server {
    listen 443 ssl;
    server_name $domain;

    ssl_certificate /etc/letsencrypt/live/$domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$domain/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;

    # API endpoints
    location $api_url_prefix/ {
        proxy_pass http://localhost:$port$api_url_prefix/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend static files
    location $frontend_url_prefix {
        alias $frontend_path/;
        try_files $uri $uri/ $frontend_url_prefix/index.html;
        expires 1d;
        add_header Cache-Control "public";
    }
}
"""

def _log(message, verbose=False, important=False):
    """Log messages to the console
    
    Args:
        message: The message to log
        verbose: Whether this is a verbose (detailed) message
        important: Whether this is an important message that should always be shown
    """
    if important or verbose:
        # Use different formatting for important messages
        if important:
            print(f"\033[1m[agent-deployer]\033[0m {message}")
        else:
            print(f"[agent-deployer] {message}")

def _run_command(command, verbose=False):
    """Run a shell command and return the output"""
    _log(f"Running: {command}", verbose)
    result = subprocess.run(command, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {result.stderr}")
    return result.stdout.strip()

def _get_exec_start(framework, project_path, venv_path, port, workers, timeout):
    """Generate the ExecStart command based on the framework"""
    if framework == "fastapi":
        return f"{venv_path}/bin/uvicorn main:app --host 0.0.0.0 --port {port} --workers {workers} --timeout-keep-alive {timeout}"
    elif framework == "flask":
        return f"{venv_path}/bin/gunicorn -w {workers} -b 0.0.0.0:{port} -t {timeout} app:app"
    elif framework == "django":
        project_name = os.path.basename(project_path)
        return f"{venv_path}/bin/gunicorn -w {workers} -b 0.0.0.0:{port} -t {timeout} {project_name}.wsgi:application"
    else:
        raise ValueError(f"Unsupported framework: {framework}")

def deploy_api(
    project_path,
    service_name,
    framework,
    workers=2,
    timeout=30,
    port=8000,
    venv_name="venv",
    domain=None,
    enable_db=False,
    env_file=None,
    verbose=False,
    frontend_path=None,
    frontend_url_prefix="/",
    api_url_prefix="/api"
):
    """
    Deploy a Python API to a server with systemd and Nginx configuration
    
    Args:
        project_path (str): Path to the project directory
        service_name (str): Name for the systemd service
        framework (str): Python web framework (flask, fastapi, django)
        workers (int): Number of worker processes
        timeout (int): Worker timeout in seconds
        port (int): Port to run the service on
        venv_name (str): Name of virtual environment directory
        domain (str, optional): Domain name for Nginx configuration
        enable_db (bool): Enable database connection
        env_file (str, optional): Path to environment file
        verbose (bool): Enable verbose output
        frontend_path (str, optional): Path to frontend build directory
        frontend_url_prefix (str): URL prefix for frontend (default: /)
        api_url_prefix (str): URL prefix for API endpoints (default: /api)
    """
    # Validate inputs
    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        raise ValueError(f"Project path does not exist: {project_path}")
    
    _log(f"Deploying {framework} application from {project_path}", important=True)
    
    # Get current user and group
    _log("Getting current user and group information", verbose=verbose)
    user = _run_command("whoami", verbose)
    group = _run_command("id -gn", verbose)
    
    # Prepare environment variables
    environment_vars = ""
    if env_file and os.path.isfile(os.path.join(project_path, env_file)):
        _log(f"Loading environment variables from {env_file}", important=True)
        with open(os.path.join(project_path, env_file), 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    environment_vars += f'Environment="{key}={value}"\n'
    
    # Create systemd service file
    venv_path = os.path.join(project_path, venv_name)
    exec_start = _get_exec_start(framework, project_path, venv_path, port, workers, timeout)
    
    _log(f"Configuring service to run on port {port} with {workers} workers", important=True)
    
    systemd_content = Template(SYSTEMD_TEMPLATE).substitute(
        service_name=service_name,
        user=user,
        group=group,
        project_path=project_path,
        exec_start=exec_start,
        venv_path=venv_path,
        environment_vars=environment_vars
    )
    
    service_file = f"/etc/systemd/system/{service_name}.service"
    _log(f"Creating systemd service file: {service_file}", important=True)
    
    # Write to a temporary file first, then use sudo to move it
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
        tmp.write(systemd_content)
        tmp_path = tmp.name
    
    _run_command(f"sudo mv {tmp_path} {service_file}", verbose)
    _run_command(f"sudo chmod 644 {service_file}", verbose)
    _log("Systemd service file created successfully", important=True)
    
    # Create Nginx configuration if domain is provided
    if domain:
        _log(f"Setting up Nginx configuration for domain: {domain}", important=True)
        nginx_file = f"/etc/nginx/sites-available/{service_name}"
        
        # Check if SSL certificates exist
        _log("Checking for existing SSL certificates", verbose=verbose)
        ssl_exists = _run_command(f"sudo test -d /etc/letsencrypt/live/{domain} && echo 'yes' || echo 'no'", verbose) == 'yes'
        
        # Check if frontend path is provided
        has_frontend = frontend_path and os.path.isdir(frontend_path)
        if has_frontend:
            _log(f"Frontend detected at {frontend_path}", important=True)
            _log(f"Configuring with API at {api_url_prefix} and frontend at {frontend_url_prefix}", important=True)
        
        # Select the appropriate template based on SSL and frontend
        if has_frontend:
            if ssl_exists:
                _log("SSL certificates found, configuring HTTPS with frontend", important=True)
                nginx_content = Template(NGINX_FRONTEND_SSL_TEMPLATE).substitute(
                    domain=domain,
                    port=port,
                    frontend_path=os.path.abspath(frontend_path),
                    api_url_prefix=api_url_prefix,
                    frontend_url_prefix=frontend_url_prefix
                )
            else:
                _log("No SSL certificates found, configuring HTTP with frontend", important=True)
                nginx_content = Template(NGINX_FRONTEND_TEMPLATE).substitute(
                    domain=domain,
                    port=port,
                    frontend_path=os.path.abspath(frontend_path),
                    api_url_prefix=api_url_prefix,
                    frontend_url_prefix=frontend_url_prefix
                )
        else:
            if ssl_exists:
                _log("SSL certificates found, configuring HTTPS", important=True)
                nginx_content = Template(NGINX_SSL_TEMPLATE).substitute(
                    domain=domain,
                    port=port
                )
            else:
                _log("No SSL certificates found, configuring HTTP only", important=True)
                nginx_content = Template(NGINX_TEMPLATE).substitute(
                    domain=domain,
                    port=port
                )
        
        # Write Nginx config
        _log("Writing Nginx configuration file", verbose=verbose)
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp.write(nginx_content)
            tmp_path = tmp.name
        
        _run_command(f"sudo mv {tmp_path} {nginx_file}", verbose)
        _run_command(f"sudo chmod 644 {nginx_file}", verbose)
        
        # Enable the site if not already enabled
        sites_enabled = f"/etc/nginx/sites-enabled/{service_name}"
        if not os.path.exists(sites_enabled):
            _log("Enabling Nginx site configuration", important=True)
            _run_command(f"sudo ln -s {nginx_file} {sites_enabled}", verbose)
        
        # Check Nginx config and reload
        _log("Validating and reloading Nginx configuration", important=True)
        _run_command("sudo nginx -t", verbose)
        _run_command("sudo systemctl reload nginx", verbose)
        
        # Set up SSL if needed and not already configured
        if domain and not ssl_exists:
            _log("Setting up SSL certificates with Certbot", important=True)
            _run_command(f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos --email admin@{domain}", verbose)
            _log("SSL certificates installed successfully", important=True)
    
    # Enable and start the service
    _log("Enabling and starting the service", important=True)
    _run_command(f"sudo systemctl daemon-reload", verbose)
    _run_command(f"sudo systemctl enable {service_name}", verbose)
    _run_command(f"sudo systemctl restart {service_name}", verbose)
    
    _log(f"Deployment completed successfully!", important=True)
    
    # Print status information
    _log("Checking service status", important=True)
    status = _run_command(f"sudo systemctl status {service_name} --no-pager", verbose)
    print(f"\n--- Service Status ---\n{status}\n-------------------\n")
    
    if domain:
        _log(f"Your API is now accessible at: http{'s' if ssl_exists else ''}://{domain}", important=True)
    else:
        _log(f"Your API is now accessible at: http://server_ip:{port}", important=True)