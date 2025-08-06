#!/usr/bin/env python3
"""
Command-line interface for agent-deployer
"""
import argparse
import os
import sys
import subprocess
import shutil
from .deploy import deploy_api

def log(message):
    """Print a formatted log message"""
    print(f"\033[1m[agent-deployer]\033[0m {message}")

def check_dependencies(verbose=False):
    """Check and install required system dependencies"""
    log("Checking for required system dependencies...")
    
    required_packages = {
        "nginx": "nginx",
        "certbot": "certbot",
        "python3-certbot-nginx": "python3-certbot-nginx"
    }
    
    missing_packages = []
    
    for package, install_name in required_packages.items():
        if verbose:
            print(f"[agent-deployer] Checking for {package}...")
        
        try:
            # Check if package is installed
            if package == "nginx":
                subprocess.run(["nginx", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            elif package == "certbot":
                subprocess.run(["certbot", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            else:
                # For python packages, we can check differently
                result = subprocess.run(["dpkg", "-l", install_name], 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE, 
                                       check=False)
                if result.returncode != 0:
                    missing_packages.append(install_name)
        except FileNotFoundError:
            missing_packages.append(install_name)
    
    if missing_packages:
        log(f"The following required packages are missing: {', '.join(missing_packages)}")
        install = input("Would you like to install them now? (y/n): ").lower().strip()
        
        if install == 'y':
            try:
                log("Updating package lists...")
                subprocess.run(["sudo", "apt-get", "update"], check=True)
                
                log(f"Installing missing packages: {', '.join(missing_packages)}...")
                subprocess.run(["sudo", "apt-get", "install", "-y"] + missing_packages, check=True)
                log("Dependencies installed successfully!")
            except subprocess.CalledProcessError as e:
                log(f"Error installing dependencies: {e}")
                return False
        else:
            log("Please install the required dependencies manually and try again.")
            return False
    else:
        log("All required dependencies are installed.")
    
    return True

def main():
    """Main entry point for the CLI"""
    # Print banner
    print("\n" + "=" * 60)
    print("  AGENT DEPLOYER - Deploy Python APIs with ease")
    print("=" * 60 + "\n")
    
    parser = argparse.ArgumentParser(
        description="Deploy Python APIs to servers with systemd and Nginx configuration"
    )
    
    # Required arguments
    parser.add_argument("--project-path", required=True, help="Path to the project directory")
    parser.add_argument("--service-name", required=True, help="Name for the systemd service")
    parser.add_argument("--framework", required=True, choices=["flask", "fastapi", "django"], 
                        help="Python web framework used")
    parser.add_argument("--port", type=int, required=True, help="Port to run the service on")
    parser.add_argument("--venv-name", required=True, help="Name of virtual environment directory")
    
    # Optional arguments
    parser.add_argument("--workers", type=int, default=2, help="Number of worker processes")
    parser.add_argument("--timeout", type=int, default=120, help="Worker timeout in seconds")
    parser.add_argument("--domain", help="Domain name for Nginx configuration")
    parser.add_argument("--enable-db", action="store_true", help="Enable database connection")
    parser.add_argument("--env-file", help="Path to environment file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    # Frontend options
    parser.add_argument("--frontend-path", help="Path to frontend build directory")
    parser.add_argument("--frontend-url-prefix", default="/", help="URL prefix for frontend (default: /)")
    parser.add_argument("--api-url-prefix", default="/api", help="URL prefix for API endpoints (default: /api)")
    
    args = parser.parse_args()
    
    try:
        log(f"Starting deployment process for {args.framework} application")
        
        # Check for required dependencies
        if not check_dependencies(args.verbose):
            return 1
            
        # Check if Python virtual environment exists
        venv_path = os.path.join(args.project_path, args.venv_name)
        if not os.path.isdir(venv_path):
            log(f"Error: Virtual environment '{args.venv_name}' not found in {args.project_path}")
            log("Please create the virtual environment first and install your application dependencies.")
            return 1
        
        log(f"Virtual environment found at {venv_path}")
            
        deploy_api(
            project_path=args.project_path,
            service_name=args.service_name,
            framework=args.framework,
            workers=args.workers,
            timeout=args.timeout,
            port=args.port,
            venv_name=args.venv_name,
            domain=args.domain,
            enable_db=args.enable_db,
            env_file=args.env_file,
            verbose=args.verbose,
            frontend_path=args.frontend_path,
            frontend_url_prefix=args.frontend_url_prefix,
            api_url_prefix=args.api_url_prefix
        )
        
        # Display information about where to access the application
        server_ip = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.strip().split()[0]
        
        print("\n" + "=" * 60)
        print("  DEPLOYMENT SUCCESSFUL")
        print("=" * 60)
        
        if args.domain:
            log(f"Your application is now available at:")
            protocol = "https" if os.path.exists(f"/etc/letsencrypt/live/{args.domain}") else "http"
            print(f"  • {protocol}://{args.domain}")
            
            if args.frontend_path and args.api_url_prefix != "/":
                print(f"  • API: {protocol}://{args.domain}{args.api_url_prefix}")
                print(f"  • Frontend: {protocol}://{args.domain}{args.frontend_url_prefix}")
        else:
            log(f"Your application is now available at:")
            print(f"  • http://{server_ip}:{args.port}")
            
            if args.frontend_path and args.api_url_prefix != "/":
                print(f"  • API: http://{server_ip}:{args.port}{args.api_url_prefix}")
                print(f"  • Frontend: http://{server_ip}:{args.port}{args.frontend_url_prefix}")
        
        print("\nTo check service status: sudo systemctl status " + args.service_name)
        print("To view logs: sudo journalctl -u " + args.service_name + " -f")
        print("=" * 60 + "\n")
        
        log("Deployment completed successfully!")
        return 0
    except Exception as e:
        log(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())