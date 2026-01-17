# Fusion 360 Add-in: ElectrifyCopilotUI
# Creates a Copilot-style chat palette for Electrify integration

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import os
import json
import sys

# Add fusion_executor to path
add_in_dir = os.path.dirname(os.path.dirname(__file__))
if add_in_dir not in sys.path:
    sys.path.insert(0, add_in_dir)

from fusion_executor import run_actions, ExecutionResult


# Global references
app = None
ui = None
palette = None
handlers = []

# Palette configuration
PALETTE_ID = 'ElectrifyCopilotPalette'
PALETTE_NAME = 'Electrify Copilot'
PALETTE_WIDTH = 400
PALETTE_HEIGHT = 600



class HTMLEventHandler(adsk.core.HTMLEventHandler):
    """Handle events from the palette HTML/JS"""
    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            html_args = adsk.core.HTMLEventArgs.cast(args)
            action = html_args.action
            data_str = html_args.data
            
            app.log(f'[Copilot] Received: {action} - {data_str}')
            
            # Parse the incoming data
            data = json.loads(data_str) if data_str else {}
            
            if action == 'sendMessage':
                # User sent a message from the UI
                handle_user_message(data)
            
            elif action == 'paletteReady':
                # Palette has loaded
                app.log('[Copilot] Palette ready')
                send_to_palette('copilot_status', {
                    'connected': True,
                    'message': 'Connected'
                })
            
            elif action == 'newChat':
                # User requested a new chat
                app.log('[Copilot] New chat requested')
            
            # Return success
            html_args.returnData = 'OK'
            
        except:
            app.log(f'[Copilot] Error in HTMLEventHandler: {traceback.format_exc()}')
            if args:
                args.returnData = 'ERROR'


class PaletteClosedHandler(adsk.core.UserInterfaceGeneralEventHandler):
    """Handle palette close event"""
    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            global palette
            palette = None
            app.log('[Copilot] Palette closed')
        except:
            app.log(f'[Copilot] Error in close handler: {traceback.format_exc()}')


def handle_user_message(data):
    """
    Handle incoming messages from the UI palette.
    
    Main entry point for executing actions from backend.
    
    Supported commands:
    - /demo or /golden - Run voltage divider demo
    - /test rotation - Run rotation example
    - /test edit - Run edit-mode example
    - /test edges - Run edge cases example
    - /execute <path> - Run custom JSON file
    - /help - Show available commands
    """
    message = data.get('message', '').strip()
    app.log(f'[Copilot] User message: {message}')
    
    # Get the add-in directory for finding example files
    add_in_path = os.path.dirname(os.path.realpath(__file__))
    fusion_addin_dir = os.path.dirname(add_in_path)
    
    # Help command
    if message.lower() in ['/help', '/commands', '/?']:
        help_text = (
            "Available commands:\n\n"
            "/demo or /golden\n"
            "  → Run voltage divider demo (10 actions)\n\n"
            "/test rotation\n"
            "  → Run rotation example (12 actions)\n\n"
            "/test edit\n"
            "  → Run edit-mode example (15 actions)\n\n"
            "/test edges\n"
            "  → Run edge cases example (6 actions)\n\n"
            "/execute <path>\n"
            "  → Run custom JSON file\n\n"
            "/help\n"
            "  → Show this help"
        )
        send_to_palette('copilot_reply', {'message': help_text})
        return
    
    # Demo/golden path shortcuts
    if message.lower() in ['/demo', '/golden', '/test demo']:
        actions_path = os.path.join(fusion_addin_dir, 'example_voltage_divider.json')
        execute_actions_file(actions_path, "Voltage Divider Demo")
        return
    
    # Test rotation
    if message.lower() in ['/test rotation', '/rotation', '/test rot']:
        actions_path = os.path.join(fusion_addin_dir, 'example_with_rotation.json')
        execute_actions_file(actions_path, "Rotation Test")
        return
    
    # Test edit mode
    if message.lower() in ['/test edit', '/edit', '/test edit-mode']:
        actions_path = os.path.join(fusion_addin_dir, 'example_edit_mode.json')
        execute_actions_file(actions_path, "Edit-Mode Test")
        return
    
    # Test edge cases
    if message.lower() in ['/test edges', '/edges', '/test edge']:
        actions_path = os.path.join(fusion_addin_dir, 'example_edge_cases.json')
        execute_actions_file(actions_path, "Edge Cases Test")
        return
    
    # Execute custom file
    if message.lower().startswith('/execute '):
        # Extract file path: /execute path/to/actions.json
        actions_path = message[9:].strip()
        execute_actions_file(actions_path, "Custom Actions")
        return

    if message.lower() in ['/bob', '/test bob']:
        actions_path = os.path.join(fusion_addin_dir, 'actions_manual.json')
        execute_actions_file(actions_path, "Edge Cases Test")
        return
    
    # Default behavior - show help
    response = (
        f"I received: '{message}'\n\n"
        f"Try these commands:\n"
        f"• /demo - Run voltage divider\n"
        f"• /test rotation - Test rotations\n"
        f"• /test edit - Test edit operations\n"
        f"• /help - Show all commands"
    )
    send_to_palette('copilot_reply', {'message': response})


def execute_actions_file(actions_path, description):
    """
    Execute actions from a JSON file and send results to palette.
    
    Args:
        actions_path: Path to actions JSON file
        description: Human-readable description for display
    """
    if not os.path.exists(actions_path):
        send_to_palette('copilot_reply', {
            "message": f"Error: File not found:\n{actions_path}"
        })
        return
    
    send_to_palette('copilot_reply', {
        "message": f"Executing {description}...\n{os.path.basename(actions_path)}"
    })
    
    try:
        result = run_actions(actions_path, grid_unit="MM", grid_size=2.54)
        
        # Build result message
        if result.success:
            msg = (
                f"✓ {description} - Success!\n\n"
                f"Actions: {result.actions_count}\n"
                f"Script: {os.path.basename(result.script_path)}\n"
            )
            if result.warnings:
                msg += f"\nWarnings: {len(result.warnings)}"
        else:
            msg = f"✗ {description} - Failed\n\n"
            if result.errors:
                msg += "Errors:\n" + "\n".join(f"• {e[:80]}" for e in result.errors[:3])
        
        send_to_palette('copilot_reply', {'message': msg})
        
    except Exception as e:
        send_to_palette('copilot_reply', {
            "message": f"✗ Exception:\n{str(e)[:200]}"
        })



def send_to_palette(action, data):
    """Send data to the palette HTML/JS"""
    global palette
    try:
        if palette:
            palette.sendInfoToHTML(action, json.dumps(data))
            app.log(f'[Copilot] Sent to palette: {action}')
    except:
        app.log(f'[Copilot] Error sending to palette: {traceback.format_exc()}')


def create_palette():
    """Create and show the Copilot palette"""
    global palette, handlers
    
    try:
        # Delete any existing palette to ensure fresh creation
        existing_palette = ui.palettes.itemById(PALETTE_ID)
        if existing_palette:
            existing_palette.deleteMe()
            app.log('[Copilot] Deleted existing palette')
        
        # Get the path to the HTML file (use forward slashes for URL)
        add_in_path = os.path.dirname(os.path.realpath(__file__))
        html_path = os.path.join(add_in_path, 'palette.html')
        # Convert to forward slashes for proper URL formatting
        html_path = html_path.replace('\\', '/')
        
        app.log(f'[Copilot] HTML path: {html_path}')
        
        # Create the palette
        palette = ui.palettes.add(
            PALETTE_ID,
            PALETTE_NAME,
            html_path,
            True,   # isVisible
            True,   # showCloseButton
            True,   # isResizable
            PALETTE_WIDTH,
            PALETTE_HEIGHT,
            True    # useNewWebBrowser
        )
        
        # Set docking
        palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
        
        # Add event handlers
        html_handler = HTMLEventHandler()
        palette.incomingFromHTML.add(html_handler)
        handlers.append(html_handler)
        
        close_handler = PaletteClosedHandler()
        palette.closed.add(close_handler)
        handlers.append(close_handler)
        
        app.log(f'[Copilot] Palette created: {html_path}')
        
        return palette
        
    except:
        app.log(f'[Copilot] Error creating palette: {traceback.format_exc()}')
        if ui:
            ui.messageBox(f'Error creating palette:\n{traceback.format_exc()}')
        return None


class ShowPaletteCommandExecuteHandler(adsk.core.CommandEventHandler):
    """Handle the show palette command execution"""
    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            create_palette()
        except:
            if ui:
                ui.messageBox(f'Command failed:\n{traceback.format_exc()}')


class ShowPaletteCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Handle the show palette command creation"""
    def __init__(self):
        super().__init__()
    
    def notify(self, args):
        try:
            cmd = args.command
            on_execute = ShowPaletteCommandExecuteHandler()
            cmd.execute.add(on_execute)
            handlers.append(on_execute)
        except:
            if ui:
                ui.messageBox(f'Command creation failed:\n{traceback.format_exc()}')


def run_golden_path():
    """
    Demo entrypoint: Execute a sample voltage divider circuit.
    
    This is the "golden path" demo that shows:
    - Loading compiled actions from JSON
    - Executing them via fusion_executor
    - Displaying results (script path, action count, warnings/errors)
    
    Purpose: Visual verification in Fusion Electronics that parts are
    placed and nets are created correctly.
    
    Usage from Fusion Python Console:
        import ElectrifyCopilotUI
        ElectrifyCopilotUI.run_golden_path()
    """
    global app, ui
    
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        # Path to sample compiled actions
        add_in_path = os.path.dirname(os.path.realpath(__file__))
        fusion_addin_dir = os.path.dirname(add_in_path)
        sample_json = os.path.join(fusion_addin_dir, 'example_voltage_divider.json')
        
        # Print header
        print("\n" + "=" * 70)
        print("ELECTRIFY GOLDEN PATH DEMO")
        print("=" * 70)
        print(f"\nSample actions: {sample_json}")
        
        if not os.path.exists(sample_json):
            print(f"✗ Error: Sample file not found: {sample_json}")
            ui.messageBox(f"Sample file not found:\n{sample_json}")
            return
        
        print(f"✓ Sample file exists")
        
        # Execute actions
        print("\nExecuting actions...")
        result = run_actions(sample_json, grid_unit="MM", grid_size=2.54)
        
        # Print results
        print("\n" + "-" * 70)
        print("EXECUTION RESULTS")
        print("-" * 70)
        print(f"Status: {'✓ SUCCESS' if result.success else '✗ FAILED'}")
        print(f"Actions executed: {result.actions_count}")
        print(f"Script path: {result.script_path}")
        
        if result.warnings:
            print(f"\nWarnings ({len(result.warnings)}):")
            for i, warning in enumerate(result.warnings, 1):
                print(f"  [{i}] {warning}")
        else:
            print("\nWarnings: None")
        
        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for i, error in enumerate(result.errors, 1):
                print(f"  [{i}] {error}")
        else:
            print("\nErrors: None")
        
        # Show script contents if successful
        if result.script_path and os.path.exists(result.script_path):
            print("\n" + "-" * 70)
            print("GENERATED SCRIPT")
            print("-" * 70)
            with open(result.script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            print(script_content)
        
        print("\n" + "=" * 70)
        print("Demo complete! Check Fusion Electronics for placed components.")
        print("=" * 70 + "\n")
        
        # Show message box with summary
        summary = (
            f"Electrify Golden Path Demo\n\n"
            f"Status: {'SUCCESS' if result.success else 'FAILED'}\n"
            f"Actions: {result.actions_count}\n"
            f"Script: {result.script_path}\n\n"
        )
        
        if result.warnings:
            summary += f"Warnings: {len(result.warnings)}\n"
        if result.errors:
            summary += f"Errors: {len(result.errors)}\n"
        
        if result.success:
            summary += "\nCheck the schematic for placed components and nets!"
        
        ui.messageBox(summary, "Electrify Demo")
        
        return result
        
    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"\n✗ Exception in run_golden_path():\n{error_msg}")
        if ui:
            ui.messageBox(f"Golden path demo failed:\n{error_msg}")
        return None


def run(context):
    """Called when the add-in is started."""
    global app, ui
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        # Create command definition
        cmd_def = ui.commandDefinitions.itemById('ShowElectrifyCopilot')
        if not cmd_def:
            cmd_def = ui.commandDefinitions.addButtonDefinition(
                'ShowElectrifyCopilot',
                'Electrify Copilot',
                'Open the Electrify Copilot chat panel',
                ''  # No icon for now
            )
        
        # Add command created handler
        on_command_created = ShowPaletteCommandCreatedHandler()
        cmd_def.commandCreated.add(on_command_created)
        handlers.append(on_command_created)
        
        # Add to UI (Add-Ins panel)
        add_ins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
        if add_ins_panel:
            existing_control = add_ins_panel.controls.itemById('ShowElectrifyCopilot')
            if not existing_control:
                add_ins_panel.controls.addCommand(cmd_def)
        
        # Auto-show the palette on startup
        create_palette()
        
        app.log('[Copilot] ElectrifyCopilotUI add-in started')
        
    except:
        if ui:
            ui.messageBox(f'Failed to start:\n{traceback.format_exc()}')


def stop(context):
    """Called when the add-in is stopped."""
    global app, ui, palette, handlers
    try:
        # Remove the palette (get fresh reference)
        palette_to_delete = ui.palettes.itemById(PALETTE_ID)
        if palette_to_delete:
            try:
                palette_to_delete.deleteMe()
            except:
                # Palette may already be deleted or not deletable
                app.log('[Copilot] Could not delete palette (may already be gone)')
        palette = None
        
        # Remove command definition
        cmd_def = ui.commandDefinitions.itemById('ShowElectrifyCopilot')
        if cmd_def:
            cmd_def.deleteMe()
        
        # Remove from panel
        add_ins_panel = ui.allToolbarPanels.itemById('SolidScriptsAddinsPanel')
        if add_ins_panel:
            control = add_ins_panel.controls.itemById('ShowElectrifyCopilot')
            if control:
                control.deleteMe()
        
        handlers = []
        
        app.log('[Copilot] ElectrifyCopilotUI add-in stopped')
        
    except:
        if ui:
            ui.messageBox(f'Failed to stop:\n{traceback.format_exc()}')

