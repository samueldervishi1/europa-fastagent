"""Setup wizard for Tauricus API key configuration."""

from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

console = Console()


class TauricusSetupWizard:
    """Interactive setup wizard for Tauricus API keys."""
    
    def __init__(self):
        self.secrets_file = Path("fastagent.secrets.yaml")
        
    def _load_existing_config(self) -> Dict[str, Any]:
        """Load existing secrets configuration if it exists."""
        if not self.secrets_file.exists():
            return {}
            
        try:
            with open(self.secrets_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            console.print(f"[red]Error reading existing config: {e}[/red]")
            return {}
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """Save configuration to secrets file."""
        try:
            with open(self.secrets_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
            return True
        except Exception as e:
            console.print(f"[red]Error saving configuration: {e}[/red]")
            return False
    
    def _mask_key(self, key: str) -> str:
        """Mask API key for display."""
        if not key or len(key) < 8:
            return "***"
        return key[:4] + "*" * (len(key) - 8) + key[-4:]
    
    def show_welcome(self):
        """Display welcome message."""
        welcome_text = Text()
        welcome_text.append("Tauricus API Configuration", style="bold cyan")
        
        panel = Panel(
            welcome_text,
            subtitle="Configure your AI provider API keys",
            border_style="blue"
        )
        console.print(panel)
        console.print()
    
    def check_existing_config(self) -> Dict[str, bool]:
        """Check which API keys are already configured."""
        config = self._load_existing_config()
        
        return {
            'has_gemini': bool(config.get('google', {}).get('api_key')),
            'has_tavily': bool(config.get('TAVILY_API_KEY')),
            'config': config
        }
    
    def prompt_for_gemini_key(self, current_key: Optional[str] = None) -> Optional[str]:
        """Prompt for Google Gemini API key."""
        if current_key:
            console.print(f"[green]Google Gemini key configured:[/green] {self._mask_key(current_key)}")
            if not Confirm.ask("Update Google Gemini key?", default=False):
                return current_key
        
        console.print("\n[bold cyan]Google Gemini API Key (Required)[/bold cyan]")
        console.print("[dim]Get your free key at: https://aistudio.google.com/app/apikey[/dim]")
        
        while True:
            key = Prompt.ask(
                "Enter your Google Gemini API key",
                password=True,
                show_default=False
            )
            
            if key and key.strip():
                return key.strip()
            
            console.print("[red]Google Gemini API key is required to run Tauricus![/red]")
            if not Confirm.ask("Try again?", default=True):
                console.print("[yellow]Without Gemini API key, Tauricus will not function.[/yellow]")
                return None
    
    def prompt_for_tavily_key(self, current_key: Optional[str] = None) -> Optional[str]:
        """Prompt for Tavily API key."""
        if current_key:
            console.print(f"[green]Tavily key configured:[/green] {self._mask_key(current_key)}")
            if not Confirm.ask("Update Tavily key?", default=False):
                return current_key
        
        console.print("\n[bold yellow]Tavily API Key (Optional - Web Search MCP)[/bold yellow]")
        console.print("[dim]Get your free key at: https://tavily.com/[/dim]")
        console.print("[dim]ℹWithout this key, web search MCP will throw 400 errors[/dim]")
        
        if not Confirm.ask("Add Tavily API key for web search?", default=False):
            console.print("[yellow]Web search functionality will not be available[/yellow]")
            return None
        
        key = Prompt.ask(
            "Enter your Tavily API key (or press Enter to skip)",
            password=True,
            show_default=False,
            default=""
        )
        
        return key.strip() if key and key.strip() else None
    
    def show_update_menu(self, status: Dict[str, Any]) -> str:
        """Show menu for updating existing configuration."""
        console.print("\n[bold]Current Configuration[/bold]")
        
        config = status['config']
        gemini_key = config.get('google', {}).get('api_key')
        tavily_key = config.get('TAVILY_API_KEY')
        
        console.print(f"Google Gemini: {'Configured' if status['has_gemini'] else 'Not configured'}")
        if status['has_gemini']:
            console.print(f"  Key: {self._mask_key(gemini_key)}")
            
        console.print(f"Tavily Search: {'Configured' if status['has_tavily'] else 'Not configured'}")
        if status['has_tavily']:
            console.print(f"  Key: {self._mask_key(tavily_key)}")
        
        console.print("\n[bold]What would you like to update?[/bold]")
        choices = [
            "1. Update Google Gemini key",
            "2. Add/Update Tavily key", 
            "3. Update both keys",
            "4. Exit without changes"
        ]
        
        for choice in choices:
            console.print(f"  {choice}")
        
        while True:
            selection = Prompt.ask("Choose an option", choices=["1", "2", "3", "4"], default="4")
            return selection
    
    def create_config(self, gemini_key: str, tavily_key: Optional[str] = None) -> Dict[str, Any]:
        """Create configuration dictionary."""
        config = {
            'google': {
                'api_key': gemini_key
            }
        }
        
        if tavily_key:
            config['TAVILY_API_KEY'] = tavily_key
            
        return config
    
    def show_success_message(self, gemini_configured: bool, tavily_configured: bool):
        """Show success message after configuration."""
        console.print()
        if gemini_configured and tavily_configured:
            console.print("[green]Configuration completed successfully![/green]")
            console.print("Google Gemini API key configured")
            console.print("Tavily API key configured - Web search enabled")
        elif gemini_configured:
            console.print("[green]Configuration completed successfully![/green]")
            console.print("Google Gemini API key configured")
            console.print("Tavily API key not configured - Web search will return 400 errors")
        else:
            console.print("[red]Configuration incomplete![/red]")
            console.print("Google Gemini API key is required to run Tauricus")
            return False
            
        console.print(f"\n[dim]Configuration saved to: {self.secrets_file.absolute()}[/dim]")
        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print("• Run '[bold]tauricus[/bold]' to start the AI coordinator")
        console.print("• Enjoy the interactive terminal with F1 data and MCP integration!")
        
        if not tavily_configured:
            console.print("\n[yellow]Add Tavily key later with:[/yellow] [bold]tauricus setup[/bold]")
        
        return True
    
    def run_initial_setup(self) -> bool:
        """Run initial setup for new configuration."""
        self.show_welcome()
        
        # Get Gemini key (required)
        gemini_key = self.prompt_for_gemini_key()
        if not gemini_key:
            return False
        
        # Get Tavily key (optional)
        tavily_key = self.prompt_for_tavily_key()
        
        # Save configuration
        config = self.create_config(gemini_key, tavily_key)
        if not self._save_config(config):
            return False
            
        return self.show_success_message(bool(gemini_key), bool(tavily_key))
    
    def run_update_setup(self, status: Dict[str, Any]) -> bool:
        """Run setup to update existing configuration."""
        choice = self.show_update_menu(status)
        
        if choice == "4":
            console.print("[dim]No changes made.[/dim]")
            return True
        
        config = status['config'].copy()
        gemini_updated = False
        tavily_updated = False
        
        # Update based on choice
        if choice in ["1", "3"]:  # Update Gemini
            current_gemini = config.get('google', {}).get('api_key')
            new_gemini = self.prompt_for_gemini_key(current_gemini)
            if new_gemini and new_gemini != current_gemini:
                if 'google' not in config:
                    config['google'] = {}
                config['google']['api_key'] = new_gemini
                gemini_updated = True
                
        if choice in ["2", "3"]:  # Update Tavily
            current_tavily = config.get('TAVILY_API_KEY')
            new_tavily = self.prompt_for_tavily_key(current_tavily)
            if new_tavily != current_tavily:  # None is different from existing key
                if new_tavily:
                    config['TAVILY_API_KEY'] = new_tavily
                elif 'TAVILY_API_KEY' in config:
                    del config['TAVILY_API_KEY']
                tavily_updated = True
        
        # Save if changes were made
        if gemini_updated or tavily_updated:
            if not self._save_config(config):
                return False
            
            console.print("\n[green]Configuration updated successfully![/green]")
            if gemini_updated:
                console.print("• Google Gemini key updated")
            if tavily_updated:
                console.print("• Tavily key updated")
        else:
            console.print("\n[dim]No changes made to configuration.[/dim]")
            
        return True
    
    def run(self) -> bool:
        """Main entry point for setup wizard."""
        try:
            status = self.check_existing_config()
            
            if not status['has_gemini'] and not status['has_tavily']:
                # Fresh setup
                return self.run_initial_setup()
            else:
                # Update existing setup
                return self.run_update_setup(status)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Setup cancelled by user.[/yellow]")
            return False
        except Exception as e:
            console.print(f"\n[red]Setup failed: {e}[/red]")
            return False


def run_setup_wizard():
    """CLI entry point for setup wizard."""
    wizard = TauricusSetupWizard()
    success = wizard.run()
    
    if not success:
        raise typer.Exit(code=1)