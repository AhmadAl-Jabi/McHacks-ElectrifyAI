# Fusion 360 Add-in: ElectrifyCopilotUI
# Electronics Schematic Copilot - focuses ONLY on schematics (no 3D fallback)
# ============================================================================

import adsk.core
import adsk.fusion
import adsk.cam
import traceback
import os
import json

# Import history handlers module (routes history_* actions to HistoryService)
try:
    from . import history_handlers
except ImportError:
    # Fallback for direct execution
    import history_handlers

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

def electron_run(command: str) -> str:
    # Runs an Electronics (EAGLE-style) command inside Fusion
    return app.executeTextCommand(f'Electron.run "{command}"')

def test_add_resistor():
    # You must have an Electronics schematic open/active for this to work.
    # This device string may differ in your environment. See the note below.
    #electron_run("GRID mm 1")
    #electron_run("WINDOW FIT")
    electron_run("ADD R (10 10)")
    electron_run("ADD R (20 10)")
    electron_run("ADD R (30 10)")
    electron_run("ADD R (40 10)")
    electron_run("ADD R (50 10)")
    electron_run("ADD R (60 10)")
    electron_run("ADD R (70 10)")
    electron_run("ADD R (80 10)")


def describe_selected_component():
    """
    Attempt to gather information about the currently selected entity and
    send a composed payload to the palette to prefill the composer.
    """
    global app, ui, palette
    try:
        # Try several ways to access the selection (best-effort, API varies)
        sel = None
        try:
            sel = ui.activeSelectionSet
        except Exception:
            pass
        
        if not sel:
            try:
                sel = app.activeProduct.selection if app.activeProduct else None
            except Exception:
                pass

        if not sel:
            app.log('[Copilot] No selection found')
            send_to_palette('copilot_reply', {'message': 'Please select a component in the schematic.'})
            return

        # The selection object may provide an entity property
        entity = None
        try:
            entity = sel.entity
        except Exception:
            pass

        # Gather common fields with fallbacks
        name = ''
        ref = ''
        value = ''
        footprint = ''
        datasheet = ''

        try:
            name = entity.name if entity else ''
        except Exception:
            pass
        try:
            ref = entity.designator if entity else ''
        except Exception:
            pass
        try:
            value = entity.value if entity else ''
        except Exception:
            pass
        try:
            footprint = entity.footprint if entity else ''
        except Exception:
            pass

        # Try to read attributes / custom properties for datasheet or manufacturer
        try:
            if hasattr(entity, 'attributes'):
                for attr in entity.attributes:
                    if attr.name.lower() == 'datasheet':
                        datasheet = attr.value
        except Exception:
            pass

        payload = {
            'name': name,
            'ref': ref,
            'value': value,
            'footprint': footprint,
            'datasheet': datasheet,
            'notes': ''
        }

        send_to_palette('compose_with_component', payload)

    except Exception:
        app.log(f'[Copilot] describe_selected_component error: {traceback.format_exc()}')
        send_to_palette('copilot_reply', {'message': 'Failed to gather selection info. See log.'})


def get_selected_component_info():
    """
    Gather information about the currently selected schematic component
    and send it to the palette to display in the Component Info panel.
    Works only for Electronics/schematic selections.
    """
    global app, ui, palette
    try:
        # Check if we're in Electronics workspace
        is_electronics = False
        try:
            ws = ui.activeWorkspace
            is_electronics = ws.id == 'ElectronicsEnvironment' if ws else False
        except Exception:
            pass

        if not is_electronics:
            send_to_palette('show_component_info', {
                'name': '',
                'ref': '',
                'value': '',
                'footprint': '',
                'datasheet': '',
                'description': 'Switch to Electronics workspace to view component info.'
            })
            return

        # Try to get the current selection
        sel = None
        try:
            sel = ui.activeSelectionSet
        except Exception:
            pass

        if not sel:
            send_to_palette('show_component_info', {
                'name': '',
                'ref': '',
                'value': '',
                'footprint': '',
                'datasheet': '',
                'description': 'No component selected. Select a component in the schematic.'
            })
            return

        if not sel:
            send_to_palette('show_component_info', {
                'name': '',
                'ref': '',
                'value': '',
                'footprint': '',
                'datasheet': '',
                'description': 'Unable to access selection.'
            })
            return

        # Extract entity from selection
        entity = None
        try:
            entity = sel.entity
        except Exception:
            pass

        # Gather component info with fallbacks
        name = ''
        ref = ''
        value = ''
        footprint = ''
        datasheet = ''
        description = ''

        try:
            name = entity.name if entity else ''
        except Exception:
            pass
        try:
            ref = entity.designator if entity else ''
        except Exception:
            pass
        try:
            value = entity.value if entity else ''
        except Exception:
            pass
        try:
            footprint = entity.footprint if entity else ''
        except Exception:
            pass
        try:
            datasheet = entity.datasheet if entity else ''
        except Exception:
            pass

        # Try to read attributes for datasheet
        try:
            if hasattr(entity, 'attributes'):
                for attr in entity.attributes:
                    if attr.name.lower() == 'datasheet':
                        datasheet = attr.value
                    elif attr.name.lower() == 'description':
                        description = attr.value
        except Exception:
            pass

        # Log what we found
        app.log(f'[Copilot] Component info: name={name}, ref={ref}, value={value}, footprint={footprint}')

        # Send to palette
        send_to_palette('show_component_info', {
            'name': name,
            'ref': ref,
            'value': value,
            'footprint': footprint,
            'datasheet': datasheet,
            'description': description
        })

    except Exception:
        app.log(f'[Copilot] get_selected_component_info error: {traceback.format_exc()}')
        send_to_palette('show_component_info', {
            'name': '',
            'ref': '',
            'value': '',
            'footprint': '',
            'datasheet': '',
            'description': 'Error gathering component info. See log.'
        })


# ============================================================================
# SchematicController - Clean abstraction for all schematic operations
# ============================================================================

class SchematicController:
    """
    Abstraction layer for Electronics/Schematic operations.
    All schematic detection, inspection, and command execution lives here.
    """

    # Known Electronics workspace and command IDs (discovered via Fusion internals)
    ELECTRONICS_WORKSPACE_ID = 'ElectronicsEnvironment'
    
    # Common Electronics command IDs (prefix pattern: Electronics*)
    KNOWN_COMMAND_PATTERNS = [
        'Electronics',
        'Schematic',
        'PCB',
        'Symbol',
        'Component',
        'Wire',
        'Net',
        'Place',
    ]

    def __init__(self, application, user_interface):
        self.app = application
        self.ui = user_interface
        self._context_cache = None
        self._cache_timestamp = None

    # -------------------------------------------------------------------------
    # Context Discovery
    # -------------------------------------------------------------------------

    def get_context(self, force_refresh=False):
        """
        Discover current Electronics workspace context.
        Returns dict with: { active_workspace, workspace_id, product_name, ... }
        """
        try:
            import time
            now = time.time()
            
            # Return cached result if fresh enough (5 seconds)
            if not force_refresh and self._context_cache and (now - self._cache_timestamp) < 5:
                return self._context_cache
            
            context = {
                'active_workspace': None,
                'workspace_id': None,
                'is_electronics': False,
                'product_name': None,
                'has_selection': False,
                'selection_count': 0,
            }
            
            try:
                ws = self.ui.activeWorkspace
                if ws:
                    context['active_workspace'] = ws.name
                    context['workspace_id'] = ws.id
                    context['is_electronics'] = (ws.id == self.ELECTRONICS_WORKSPACE_ID)
            except Exception as e:
                self._log(f'Error getting workspace: {e}')
            
            try:
                if self.app.activeProduct:
                    context['product_name'] = self.app.activeProduct.name
            except Exception:
                pass
            
            try:
                sel = self.ui.activeSelectionSet
                if sel:
                    context['has_selection'] = True
                    context['selection_count'] = sel.count
            except Exception:
                pass
            
            self._context_cache = context
            self._cache_timestamp = now
            return context
            
        except Exception as e:
            self._log(f'get_context error: {e}')
            return {'active_workspace': None, 'workspace_id': None, 'is_electronics': False}

    def invalidate_cache(self):
        """Invalidate the context cache"""
        self._context_cache = None
        self._cache_timestamp = None

    def is_electronics_active(self):
        """Check if Electronics workspace is currently active"""
        context = self.get_context()
        return context.get('is_electronics', False)

    # -------------------------------------------------------------------------
    # Context Reporting (Debug)
    # -------------------------------------------------------------------------

    def get_context_report(self):
        """Get a detailed text report of the current context (for debugging)"""
        try:
            ctx = self.get_context(force_refresh=True)
            report = []
            report.append('=== Current Electronics Context ===')
            report.append(f'Active Workspace: {ctx.get("active_workspace", "None")}')
            report.append(f'Workspace ID: {ctx.get("workspace_id", "None")}')
            report.append(f'Is Electronics: {ctx.get("is_electronics", False)}')
            report.append(f'Product: {ctx.get("product_name", "None")}')
            report.append(f'Has Selection: {ctx.get("has_selection", False)}')
            report.append(f'Selection Count: {ctx.get("selection_count", 0)}')
            return '\n'.join(report)
        except Exception as e:
            return f'Error generating context report: {e}'

    def _summarize_members(self, obj, limit=30):
        """Helper: summarize public members of an object for debugging"""
        try:
            members = [m for m in dir(obj) if not m.startswith('_')][:limit]
            return ', '.join(members)
        except:
            return '(unable to inspect)'

    # -------------------------------------------------------------------------
    # Command Discovery
    # -------------------------------------------------------------------------

    def discover_electronics_commands(self, limit=50):
        """
        Discover available Electronics commands by inspecting UI command definitions.
        Returns list of command IDs matching known patterns.
        """
        try:
            commands = []
            if self.ui.commandDefinitions:
                for cmd_def in self.ui.commandDefinitions:
                    cmd_id = cmd_def.id
                    # Match against known patterns
                    if any(pattern in cmd_id for pattern in self.KNOWN_COMMAND_PATTERNS):
                        commands.append(cmd_id)
                        if len(commands) >= limit:
                            break
            return commands
        except Exception as e:
            self._log(f'discover_electronics_commands error: {e}')
            return []

    def get_command_info(self, command_id):
        """Get information about a specific command"""
        try:
            cmd_def = self.ui.commandDefinitions.itemById(command_id)
            if cmd_def:
                return {
                    'id': cmd_def.id,
                    'name': cmd_def.name if hasattr(cmd_def, 'name') else '',
                    'tooltip': cmd_def.tooltip if hasattr(cmd_def, 'tooltip') else ''
                }
        except Exception as e:
            self._log(f'get_command_info error: {e}')
        return None

    # -------------------------------------------------------------------------
    # Command Execution
    # -------------------------------------------------------------------------

    def execute_command(self, command_id):
        """Execute a Fusion command by ID"""
        try:
            cmd_def = self.ui.commandDefinitions.itemById(command_id)
            if cmd_def:
                cmd_def.execute()
                return True
        except Exception as e:
            self._log(f'execute_command error: {e}')
        return False

    def execute_place_component(self):
        """Place a component (Electronics-specific)"""
        try:
            # Try to execute Place Component command
            return self.execute_command('Electronics:PlaceComponent')
        except Exception as e:
            self._log(f'execute_place_component error: {e}')
            return False

    # -------------------------------------------------------------------------
    # Schematic Operations (PoC)
    # -------------------------------------------------------------------------

    def poc_add_resistor(self, x_mm=10, y_mm=15, value='1kΩ'):
        """
        Proof-of-concept: Add a resistor to the current schematic.
        Requires: Electronics workspace active + schematic document open.
        """
        try:
            if not self.is_electronics_active():
                return self._get_not_electronics_message(self.get_context())
            
            # Execute the EAGLE-style command via Electron
            cmd = f'ADD R ({x_mm} {y_mm})'
            self.app.executeTextCommand(f'Electron.run "{cmd}"')
            return f'Added resistor at ({x_mm}mm, {y_mm}mm)'
        except Exception as e:
            self._log(f'poc_add_resistor error: {e}')
            return f'Error adding resistor: {e}'

    def _get_not_electronics_message(self, ctx):
        """Return user-friendly message when not in Electronics workspace"""
        return (
            'Please switch to the Electronics workspace and open a schematic '
            f'(currently in: {ctx.get("active_workspace", "Unknown")})'
        )

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def _log(self, message):
        """Internal logging"""
        if self.app:
            self.app.log(f'[SchematicController] {message}')


# ============================================================================
# Global Controller Instance
# ============================================================================
schematic_controller = None


def get_controller():
    """Get or create the SchematicController instance."""
    global schematic_controller, app, ui
    if schematic_controller is None:
        schematic_controller = SchematicController(app, ui)
    return schematic_controller



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
            
            # ============================================
            # Chat History Actions (history_* prefix)
            # Routes to HistoryService via history_handlers
            # Protocol v1.1.0 compliant responses
            # ============================================
            if action.startswith('history_') and history_handlers.is_history_action(action):
                try:
                    # Route to history handlers
                    response = history_handlers.handle_history_action(action, data)
                    
                    # Send response back with proper action type
                    # Response action is: history_list_result, history_create_result,
                    # history_load_result, history_ok, or history_error
                    response_action = response.get('action', 'history_error')
                    send_to_palette(response_action, response)
                    
                except Exception as e:
                    app.log(f'[Copilot] History error: {traceback.format_exc()}')
                    # Send error response with requestId passthrough
                    error_response = {
                        'action': 'history_error',
                        'v': '1.1.0',
                        'requestId': data.get('requestId', ''),
                        'ts': '',
                        'payload': {
                            'code': 'UNKNOWN',
                            'message': str(e)
                        }
                    }
                    send_to_palette('history_error', error_response)
                    
                html_args.returnData = 'OK'
                return
            
            # ============================================
            # Component Info and Commands
            # ============================================
            if action == 'get_component_info':
                try:
                    get_selected_component_info()
                except Exception as e:
                    app.log(f'[Copilot] Error getting component info: {traceback.format_exc()}')
                html_args.returnData = 'OK'
                return
            
            if action == 'get_available_commands':
                try:
                    controller = get_controller()
                    commands = controller.discover_electronics_commands(limit=20)
                    command_list = []
                    for cmd_id in commands:
                        info = controller.get_command_info(cmd_id)
                        if info:
                            command_list.append(info)
                    send_to_palette('commands_list', {'commands': command_list})
                except Exception as e:
                    app.log(f'[Copilot] Error discovering commands: {traceback.format_exc()}')
                html_args.returnData = 'OK'
                return
            
            if action == 'execute_command':
                try:
                    command_id = data.get('command_id', '')
                    controller = get_controller()
                    if controller.execute_command(command_id):
                        send_to_palette('copilot_reply', {'message': f'Executed command: {command_id}'})
                    else:
                        send_to_palette('copilot_reply', {'message': f'Failed to execute command: {command_id}'})
                except Exception as e:
                    app.log(f'[Copilot] Error executing command: {traceback.format_exc()}')
                html_args.returnData = 'OK'
                return
            
            # ============================================
            # Existing Message Actions
            # ============================================
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
    message = data.get('message', '').strip()
    app.log(f'[Copilot] User message: {message}')
    # Handle /component_info command
    if message.lower() == '/component_info':
        try:
            get_selected_component_info()
        except Exception as e:
            app.log(f'[Copilot] Error: {traceback.format_exc()}')
            send_to_palette('show_component_info', {
                'name': '',
                'ref': '',
                'value': '',
                'footprint': '',
                'datasheet': '',
                'description': 'Error gathering component info. See log.'
            })
        return
    # Chat-triggered test
    if message.lower() in ("/add_resistor", "/test_resistor"):
        try:
            test_add_resistor()
            send_to_palette('copilot_reply', {"message": "OK. Tried to add a resistor at (10mm, 10mm)."})
        except Exception as e:
            send_to_palette('copilot_reply', {"message": f"Failed to add resistor.\n{traceback.format_exc()}"})
        return

    # Default behavior (existing)
    response = f"I received your message: '{message}'\n\nThis is a test response from the Fusion 360 add-in."
    send_to_palette('copilot_reply', {'message': response})



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
        app.log(f'[Copilot] Raw add-in path: {add_in_path}')
        
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
