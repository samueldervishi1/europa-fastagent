#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REPO="samueldervishi1/mcp"
BINARY_NAME="tauricus"
PROJECT_NAME="tauricus-cli"

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

check_python() {
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.10 or higher first."
        print_status "Visit: https://python.org/downloads/"
        exit 1
    fi
    
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local major_version=$(echo $python_version | cut -d. -f1)
    local minor_version=$(echo $python_version | cut -d. -f2)
    
    if [ "$major_version" -lt 3 ] || ([ "$major_version" -eq 3 ] && [ "$minor_version" -lt 10 ]); then
        print_error "Python 3.10 or higher is required. Current version: $(python3 --version)"
        exit 1
    fi
    
    print_success "Python $(python3 --version | cut -d' ' -f2) found"
}

check_uv() {
    if ! command_exists uv; then
        print_status "UV package manager not found. Installing UV..."
        if command_exists curl; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        else
            print_error "curl is required to install UV. Please install curl first."
            exit 1
        fi
        
        # Source the shell profile to get UV in PATH
        export PATH="$HOME/.local/bin:$PATH"
        
        if ! command_exists uv; then
            print_error "Failed to install UV. Please install it manually: https://docs.astral.sh/uv/"
            exit 1
        fi
    fi
    
    print_success "UV package manager found: $(uv --version)"
}

check_node() {
    if ! command_exists node; then
        print_error "Node.js is not installed. Node.js 16+ is required for MCP servers."
        print_status "Visit: https://nodejs.org/"
        exit 1
    fi
    
    local node_version=$(node --version | sed 's/v//' | cut -d. -f1)
    if [ "$node_version" -lt 16 ]; then
        print_error "Node.js version 16 or higher is required. Current version: $(node --version)"
        exit 1
    fi
    
    print_success "Node.js $(node --version) found"
}

install_from_github() {
    print_status "Installing tauricus from GitHub..."
    
    local temp_dir=$(mktemp -d)
    local install_dir="$HOME/.local/bin"
    local project_dir="$install_dir/$PROJECT_NAME"

    mkdir -p "$install_dir"
    
    # Remove existing installation
    if [ -d "$project_dir" ]; then
        print_status "Removing existing installation..."
        rm -rf "$project_dir"
    fi
    
    print_status "Downloading from GitHub..."
    if command_exists curl; then
        curl -fsSL "https://github.com/$REPO/archive/main.tar.gz" | tar -xz -C "$temp_dir"
    elif command_exists wget; then
        wget -qO- "https://github.com/$REPO/archive/main.tar.gz" | tar -xz -C "$temp_dir"
    else
        print_error "Neither curl nor wget found. Please install one of them."
        exit 1
    fi
    
    cd "$temp_dir/mcp-main"
    
    print_status "Installing Python dependencies with UV..."
    # Install dependencies in the project directory
    uv sync --no-dev
    
    print_status "Installing to $project_dir..."
    cp -r . "$project_dir"

    # Create wrapper script that runs the coordinator
    cat > "$install_dir/$BINARY_NAME" << 'EOF'
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/tauricus-cli"

# Change to project directory and run start.py with UV
cd "$PROJECT_DIR" && exec uv run start.py "$@"
EOF
    
    chmod +x "$install_dir/$BINARY_NAME"
    rm -rf "$temp_dir"
    
    print_success "$BINARY_NAME installed to $install_dir/$BINARY_NAME"
    
    # Check if ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$install_dir:"* ]]; then
        print_warning "$install_dir is not in your PATH"
        print_status "Add this line to your shell profile (~/.bashrc, ~/.zshrc, or ~/.profile):"
        echo
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo
        print_status "Then restart your terminal or run: source ~/.bashrc"
        print_status "Alternatively, you can run tauricus with: $install_dir/$BINARY_NAME"
    fi
}

verify_installation() {
    print_status "Verifying installation..."
    
    local install_dir="$HOME/.local/bin"
    
    if command_exists $BINARY_NAME; then
        print_success "$BINARY_NAME is installed and available in PATH"
        print_status "Try running: $BINARY_NAME --help"
        return 0
    else
        if [ -f "$install_dir/$BINARY_NAME" ]; then
            print_warning "$BINARY_NAME installed but not in PATH"
            print_status "You can run it with: $install_dir/$BINARY_NAME"
            return 0
        else
            print_error "Installation verification failed"
            return 1
        fi
    fi
}

setup_path() {
    local install_dir="$HOME/.local/bin"
    
    # Check if already in PATH
    if [[ ":$PATH:" == *":$install_dir:"* ]]; then
        return 0
    fi
    
    local shell_profile=""
    if [ -n "$ZSH_VERSION" ]; then
        shell_profile="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        shell_profile="$HOME/.bashrc"
    else
        shell_profile="$HOME/.profile"
    fi
    
    echo
    read -p "Would you like to automatically add $install_dir to your PATH? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$shell_profile"
        print_success "Added to PATH in $shell_profile"
        print_status "Please restart your terminal or run: source $shell_profile"
    fi
}

main() {
    print_status "Installing tauricus - AI Coordinator powered by Google Gemini..."
    echo
    
    # Check system requirements
    check_python
    check_uv
    check_node
    
    echo
    install_from_github
    
    if verify_installation; then
        setup_path
        echo
        print_success "Tauricus installation completed successfully!"
        echo
        print_status "Next steps:"
        print_status "1. Run '$BINARY_NAME setup keys' to configure your API keys"
        print_status "2. Run '$BINARY_NAME' to start the AI coordinator with F1 data!"
        echo
        print_status "You'll need:"
        print_status "   • Google Gemini API key (required) - https://aistudio.google.com/app/apikey"
        print_status "   • Tavily API key (optional, for web search) - https://tavily.com/"
        echo
    else
        print_error "Installation verification failed. Please check the installation manually."
        exit 1
    fi
}

# Handle interruption gracefully
trap 'print_error "Installation interrupted"; exit 1' INT

main "$@"