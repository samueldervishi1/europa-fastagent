#!/usr/bin/env python3
"""
MCP Server for Spring Boot Project Generation

This server provides tools to generate Spring Boot projects using the Spring Initializr API.
"""

import json
import re
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from mcp.server.fastmcp import FastMCP

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
try:
    from src.mcp_agent.utils.request_cache import cached_request

    CACHING_AVAILABLE = True
except ImportError:
    print("Warning: Request caching not available - falling back to direct requests")
    CACHING_AVAILABLE = False

mcp = FastMCP("Spring Boot Generator")
INITIALIZR_BASE_URL = "https://start.spring.io"
METADATA_URL = f"{INITIALIZR_BASE_URL}/metadata/client"
_metadata_cache: Optional[Dict[str, Any]] = None


def _validate_safe_path(path: str) -> bool:
    """Validate that a path is safe and doesn't contain dangerous characters."""
    safe_pattern = re.compile(r"^[a-zA-Z0-9._/-]+$")
    if not safe_pattern.match(path):
        return False

    if ".." in path or path.startswith("/"):
        return False

    return True


def _validate_safe_name(name: str) -> bool:
    """Validate that a project name is safe."""
    safe_pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
    return bool(safe_pattern.match(name)) and len(name) <= 100


def _sanitize_command_args(args: List[str]) -> List[str]:
    """Sanitize command arguments to prevent injection."""
    sanitized = []
    for arg in args:
        if re.search(r"[;&|`$(){}[\]<>]", arg):
            continue
        sanitized.append(arg)
    return sanitized


async def get_initializr_metadata() -> Dict[str, Any]:
    """Get metadata from Spring Initializr API with caching."""
    global _metadata_cache

    if _metadata_cache is None:
        try:
            if CACHING_AVAILABLE:
                # Cache metadata for 1 hour
                response = cached_request("GET", METADATA_URL, ttl=3600, timeout=10)
            else:
                response = requests.get(METADATA_URL, timeout=10)
            response.raise_for_status()
            _metadata_cache = response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch Spring Initializr metadata: {e}")

    return _metadata_cache


def detect_yaml_type(yaml_path: str) -> str:
    """Detect if YAML is OpenAPI/Swagger spec or Spring Boot config."""
    try:
        with open(yaml_path, "r") as file:
            config = yaml.safe_load(file)

        openapi_indicators = [
            "swagger" in config,
            "openapi" in config,
            "paths" in config,
            "info" in config and "title" in config.get("info", {}),
            "definitions" in config,
            "components" in config,
        ]

        if any(openapi_indicators):
            return "openapi"

        spring_indicators = ["project" in config, "dependencies" in config and isinstance(config["dependencies"], list)]

        if any(spring_indicators):
            return "spring_config"

        return "unknown"

    except Exception:
        return "unknown"


def load_spring_config_from_yaml(yaml_path: str) -> Dict[str, Any]:
    """Load Spring Boot configuration from YAML file."""
    try:
        with open(yaml_path, "r") as file:
            config = yaml.safe_load(file)

        spring_config = {}

        if "project" in config:
            project = config["project"]
            spring_config.update(
                {
                    "name": project.get("name"),
                    "description": project.get("description"),
                    "package_name": project.get("package", project.get("group_id")),
                    "java_version": project.get("java_version"),
                    "spring_boot_version": project.get("spring_boot_version"),
                    "packaging": project.get("packaging"),
                }
            )

        if "dependencies" in config:
            spring_config["dependencies"] = config["dependencies"]

        # Remove None values
        return {k: v for k, v in spring_config.items() if v is not None}

    except Exception as e:
        raise Exception(f"Failed to load YAML config: {e}")


def extract_project_info_from_openapi(yaml_path: str) -> Dict[str, Any]:
    """Extract project information from OpenAPI/Swagger spec."""
    try:
        with open(yaml_path, "r") as file:
            spec = yaml.safe_load(file)

        info = spec.get("info", {})

        title = info.get("title", "generated-api")
        project_name = title.lower().replace(" ", "-").replace("api", "").strip("-")
        if not project_name:
            project_name = "generated-api"

        package_parts = title.lower().replace(" ", "").replace("-", "").replace("api", "")
        package_name = f"com.example.{package_parts}" if package_parts else "com.example.api"

        return {
            "name": project_name,
            "description": info.get("description", f"Spring Boot server for {title}"),
            "package_name": package_name,
            "version": info.get("version", "1.0.0"),
            "title": title,
        }

    except Exception as e:
        raise Exception(f"Failed to extract OpenAPI info: {e}")


@mcp.tool()
async def generate_spring_boot_from_openapi(openapi_yaml_path: str, output_dir: str = ".", override_name: str = None) -> str:
    """
    Generate a complete Spring Boot server from OpenAPI/Swagger specification.

    Args:
        openapi_yaml_path: Path to OpenAPI/Swagger YAML file
        output_dir: Directory to extract the project to
        override_name: Override project name from spec (optional)

    Returns:
        Success message with project location
    """
    try:
        if not _validate_safe_path(openapi_yaml_path):
            return "Error: Invalid OpenAPI YAML path - contains unsafe characters"

        if not _validate_safe_path(output_dir):
            return "Error: Invalid output directory path - contains unsafe characters"

        project_info = extract_project_info_from_openapi(openapi_yaml_path)

        if override_name:
            if not _validate_safe_name(override_name):
                return "Error: Invalid override name - contains unsafe characters"
            project_info["name"] = override_name

        project_name = project_info["name"]
        if not _validate_safe_name(project_name):
            return "Error: Invalid project name - contains unsafe characters"

        output_path = Path(output_dir).resolve()
        project_path = output_path / project_name

        if project_path.exists():
            return f"Error: Directory '{project_path}' already exists"

        try:
            subprocess.run(["which", "openapi-generator-cli"], check=True, capture_output=True, timeout=30)
        except subprocess.CalledProcessError:
            try:
                subprocess.run(
                    ["npm", "install", "-g", "@openapitools/openapi-generator-cli"], check=True, capture_output=True, timeout=120
                )
            except subprocess.CalledProcessError:
                return "Error: Could not install OpenAPI Generator. Please install manually: npm install -g @openapitools/openapi-generator-cli"

        cmd = [
            "openapi-generator-cli",
            "generate",
            "-i",
            openapi_yaml_path,
            "-g",
            "spring",
            "-o",
            str(project_path),
            "--additional-properties",
            f"groupId={project_info['package_name']}.api,"
            f"artifactId={project_name},"
            f"apiPackage={project_info['package_name']}.api,"
            f"modelPackage={project_info['package_name']}.model,"
            f"basePackage={project_info['package_name']},"
            "java8=false,"
            "dateLibrary=java8,"
            "interfaceOnly=false,"
            "useTags=true",
        ]

        sanitized_cmd = _sanitize_command_args(cmd)
        if len(sanitized_cmd) != len(cmd):
            return "Error: Command contains unsafe characters"

        result = subprocess.run(sanitized_cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            return f"OpenAPI Generator failed: {result.stderr}"

        return (
            f"Spring Boot server '{project_name}' generated from OpenAPI spec at: {project_path}\n"
            + f"API Title: {project_info['title']}\n"
            + f"Package: {project_info['package_name']}\n"
            + f"Run with: cd {project_name} && ./mvnw spring-boot:run"
        )

    except Exception as e:
        return f"Failed to generate from OpenAPI: {e}"


@mcp.tool()
async def create_spring_boot_project_from_yaml(yaml_config_path: str, output_dir: str = ".", override_name: str = None) -> str:
    """
    Generate a Spring Boot project using configuration from a YAML file.

    YAML format example:
    ```yaml
    project:
      name: my-api
      description: My REST API
      package: com.example.myapi
      java_version: 17
      spring_boot_version: 3.4.9
      packaging: jar
    dependencies:
      - web
      - security
      - actuator
    ```

    Args:
        yaml_config_path: Path to YAML configuration file
        output_dir: Directory to extract the project to
        override_name: Override project name from YAML (optional)

    Returns:
        Success message with project location
    """
    try:
        yaml_type = detect_yaml_type(yaml_config_path)

        if yaml_type == "openapi":
            return await generate_spring_boot_from_openapi(yaml_config_path, output_dir, override_name)
        elif yaml_type == "spring_config":
            config = load_spring_config_from_yaml(yaml_config_path)

            if override_name:
                config["name"] = override_name

            if not config.get("name"):
                return "Error: Project name not found in YAML config or override"

            return await create_spring_boot_project(
                name=config["name"],
                output_dir=output_dir,
                package_name=config.get("package_name", "com.example.demo"),
                java_version=config.get("java_version", "17"),
                spring_boot_version=config.get("spring_boot_version", "3.4.9"),
                dependencies=config.get("dependencies", ["web"]),
                packaging=config.get("packaging", "jar"),
                description=config.get("description", "Spring Boot project from YAML config"),
            )
        else:
            return (
                "Unknown YAML format. Expected OpenAPI/Swagger specification or Spring Boot configuration.\n"
                + "Found indicators suggest this is not a supported format.\n"
                + "Use 'validate_yaml_config' to check the file structure."
            )

    except Exception as e:
        return f"Failed to create project from YAML: {e}"


@mcp.tool()
async def analyze_yaml_file(yaml_config_path: str) -> str:
    """
    Analyze a YAML file to determine its type and show what can be generated.

    Args:
        yaml_config_path: Path to YAML file

    Returns:
        Analysis results and recommendations
    """
    try:
        yaml_type = detect_yaml_type(yaml_config_path)

        if yaml_type == "openapi":
            project_info = extract_project_info_from_openapi(yaml_config_path)
            return (
                "YAML File Analysis:\n\n"
                + "Type: OpenAPI/Swagger Specification\n"
                + f"API Title: {project_info['title']}\n"
                + f"Description: {project_info['description']}\n"
                + f"Suggested Project Name: {project_info['name']}\n"
                + f"Suggested Package: {project_info['package_name']}\n\n"
                + "Can generate: Complete Spring Boot server with API endpoints\n"
                + "Use: create_spring_boot_project_from_yaml() or generate_spring_boot_from_openapi()"
            )

        elif yaml_type == "spring_config":
            config = load_spring_config_from_yaml(yaml_config_path)
            result = "YAML File Analysis:\n\n" + "Type: Spring Boot Configuration\n"

            for key, value in config.items():
                if isinstance(value, list):
                    result += f"  • {key}: {', '.join(value)}\n"
                else:
                    result += f"  • {key}: {value}\n"

            result += (
                "\nCan generate: Basic Spring Boot project with specified configuration\n" + "Use: create_spring_boot_project_from_yaml()"
            )
            return result

        else:
            return (
                "YAML File Analysis:\n\n"
                + "Type: Unknown/Unsupported format\n"
                + "This doesn't appear to be:\n"
                + "  • OpenAPI/Swagger specification\n"
                + "  • Spring Boot configuration\n\n"
                + "For OpenAPI, file should have: 'swagger', 'openapi', 'paths', 'info'\n"
                + "For Spring config, file should have: 'project', 'dependencies'"
            )

    except Exception as e:
        return f"Failed to analyze YAML file: {e}"


@mcp.tool()
async def validate_yaml_config(yaml_config_path: str) -> str:
    """
    Validate a YAML configuration file for Spring Boot project generation.

    Args:
        yaml_config_path: Path to YAML configuration file

    Returns:
        Validation results and configuration summary
    """
    try:
        config = load_spring_config_from_yaml(yaml_config_path)

        result = "YAML Configuration Valid\n\n"
        result += "Configuration Summary:\n"

        for key, value in config.items():
            if isinstance(value, list):
                result += f"  • {key}: {', '.join(value)}\n"
            else:
                result += f"  • {key}: {value}\n"

        # Validation warnings
        warnings = []
        if not config.get("name"):
            warnings.append("Project name not specified")
        if not config.get("dependencies"):
            warnings.append("No dependencies specified, will use default: ['web']")

        if warnings:
            result += "\nWarnings:\n"
            for warning in warnings:
                result += f"  {warning}\n"

        return result

    except Exception as e:
        return f"YAML validation failed: {e}"


@mcp.tool()
async def generate_sample_yaml_config(project_name: str = "sample-project") -> str:
    """
    Generate a sample YAML configuration file for Spring Boot projects.

    Args:
        project_name: Name for the sample project

    Returns:
        Sample YAML configuration content
    """
    sample_config = {
        "project": {
            "name": project_name,
            "description": f"{project_name} Spring Boot application",
            "package": f"com.example.{project_name.replace('-', '')}",
            "java_version": 17,
            "spring_boot_version": "3.4.9",
            "packaging": "jar",
        },
        "dependencies": ["web", "actuator"],
    }

    yaml_content = yaml.dump(sample_config, default_flow_style=False, sort_keys=False)

    return (
        f"Sample Spring Boot YAML Configuration:\n\n```yaml\n{yaml_content}```\n\n"
        + "Save this as 'spring-config.yaml' and use with create_spring_boot_project_from_yaml()"
    )


@mcp.tool()
async def create_spring_boot_project(
    name: str,
    output_dir: str = ".",
    package_name: str = "com.example.demo",
    java_version: str = "17",
    spring_boot_version: str = "3.4.9",
    dependencies: List[str] = None,
    packaging: str = "jar",
    description: str = "Demo project for Spring Boot",
) -> str:
    """
    Generate a Spring Boot project using Spring Initializr API.

    Args:
        name: Project name and artifact ID
        output_dir: Directory to extract the project to
        package_name: Java package name (e.g., com.example.demo)
        java_version: Java version (8, 11, 17, 21)
        spring_boot_version: Spring Boot version
        dependencies: List of dependencies (web, security, actuator, etc.)
        packaging: Project packaging (jar or war)
        description: Project description

    Returns:
        Success message with project location
    """
    if dependencies is None:
        dependencies = ["web"]

    output_path = Path(output_dir).resolve()
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)

    project_path = output_path / name
    if project_path.exists():
        return f"Error: Directory '{project_path}' already exists"

    params = {
        "type": "maven-project",
        "language": "java",
        "bootVersion": spring_boot_version,
        "baseDir": name,
        "groupId": package_name.rsplit(".", 1)[0] if "." in package_name else "com.example",
        "artifactId": name,
        "name": name,
        "description": description,
        "packageName": package_name,
        "packaging": packaging,
        "javaVersion": java_version,
        "dependencies": ",".join(dependencies),
    }

    try:
        download_url = f"{INITIALIZR_BASE_URL}/starter.zip"
        if CACHING_AVAILABLE:
            response = cached_request("GET", download_url, ttl=300, params=params, timeout=30)
        else:
            response = requests.get(download_url, params=params, timeout=30)
        response.raise_for_status()

        with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
            zip_file.extractall(output_path)

        return f"Spring Boot project '{name}' created successfully at: {project_path}"

    except requests.RequestException as e:
        return f"Failed to generate project: {e}"
    except zipfile.BadZipFile:
        return "Failed to extract project: Invalid ZIP file received"
    except Exception as e:
        return f"Unexpected error: {e}"


@mcp.tool()
async def list_available_dependencies() -> str:
    """Get available Spring Boot dependencies from Spring Initializr."""
    try:
        metadata = await get_initializr_metadata()

        dependencies = metadata.get("dependencies", {}).get("values", [])
        result = {}

        for category in dependencies:
            category_name = category.get("name", "Unknown")
            result[category_name] = []

            for dep in category.get("values", []):
                dep_info = {"id": dep.get("id"), "name": dep.get("name"), "description": dep.get("description", "")}
                result[category_name].append(dep_info)

        return json.dumps(result, indent=2)

    except Exception as e:
        return f"Failed to fetch dependencies: {e}"


@mcp.tool()
async def get_spring_boot_versions() -> str:
    """Get available Spring Boot versions."""
    try:
        metadata = await get_initializr_metadata()

        boot_version = metadata.get("bootVersion", {})
        versions = []

        for version in boot_version.get("values", []):
            version_info = {"id": version.get("id"), "name": version.get("name"), "default": version.get("default", False)}
            versions.append(version_info)

        return json.dumps(versions, indent=2)

    except Exception as e:
        return f"Failed to fetch Spring Boot versions: {e}"


@mcp.tool()
async def get_project_template_info() -> str:
    """Get information about available project templates and parameters."""
    return """
Spring Boot Project Generator

Available parameters:
- name: Project name (required)
- output_dir: Where to create project (default: current directory)
- package_name: Java package (default: com.example.demo)
- java_version: Java version - 8, 11, 17, 21 (default: 17)
- spring_boot_version: Spring Boot version (default: 3.4.9)
- dependencies: List of dependency IDs (default: ["web"])
- packaging: jar or war (default: jar)
- description: Project description

Popular dependencies:
- web: Spring Web (REST APIs)
- security: Spring Security  
- actuator: Spring Boot Actuator (Monitoring)
- devtools: Spring Boot DevTools (Development)
- thymeleaf: Thymeleaf (Template engine)
- validation: Spring Boot Validation

Example usage:
create_spring_boot_project(
    name="my-api",
    dependencies=["web", "security", "actuator"],
    java_version="17",
    package_name="com.mycompany.api"
)
"""


if __name__ == "__main__":
    mcp.run()
