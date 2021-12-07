#Author-Thomas Axelsson, ZXYNINE
#Description-Blocks Component Dragging in parametric mode
#
# Copyright (c) 2021 Thomas Axelsson, ZXYNINE
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# This file is part of NoComponentDrag, a Fusion 360 add-in for blocking
# component dragging.


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
import adsk.core, adsk.fusion, adsk.cam
import os

# Import relative path to avoid namespace pollution
from .thomasa88lib import utils, events, manifest, error
utils.ReImport_List(events, manifest, error, utils)

NAME = 'NoComponentDrag'
VERSION = str(manifest.read()["version"])
FILE_DIR = os.path.dirname(os.path.realpath(__file__))
ENABLE_CMD_ID = 'thomasa88_NoComponentDrag_Enable'
VERSION_INFO = f'({NAME} v {VERSION})'
CMD_DESCRIPTION = 'Enables or disables the movement of components by dragging in the canvas.'
COMMAND_DATA = CMD_DESCRIPTION + '\n\n' + VERSION_INFO + '\n'

FUSION_CMD_ID = 'FusionDragComponentsCommand'
FUSION_CTRL_ID = 'FusionDragCompControlsCmd'

ui_:adsk.core.UserInterface = None
app_:adsk.core.Application = None 
error_catcher_ = error.ErrorCatcher()
events_manager_ = events.EventsManager(error_catcher_)
enable_ctrl_def_ : adsk.core.CheckBoxControlDefinition = None
select_panel_controls : adsk.core.ToolbarControls = None
parametric_environment_ = True
addin_updating_checkbox_ = False
fusion_drag_controls_def_ : adsk.core.CheckBoxControlDefinition = None


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# This will fire at the start of fusion but not until the workspace is ready which fixes the other problem
#This event removes itself on its first call to prevent useles events being queued
def workspace_activated_handler(args: adsk.core.WorkspaceEventArgs):
	events_manager_.remove_handler_by_event(ui_.workspaceActivated)
	check_environment()


#This is fired whenever any command is starting up and checks if that command should be blocked
def command_starting_handler(args: adsk.core.ApplicationCommandEventArgs):	# Should we block?
	if parametric_environment_ and args.commandId == FUSION_CMD_ID and not get_drag_enabled():
		args.isCanceled = True

#This is fired any time the command gets disabled
def command_terminated_handler(args: adsk.core.ApplicationCommandEventArgs):
	# Detect if user toggles Direct Edit or enters/leaves a Base Feature
	# Undo/Redo triggers the ActivateEnvironmentCommand instead.
	if (args.commandId in ('ActivateEnvironmentCommand') or
		(args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason and
		 args.commandId in ('Undo', 'Redo','ConvertToPMDesignCommand', 'ConvertToDMDesignCommand',
							'BaseFeatureActivate', 'BaseFeatureStop', 'BaseFeatureCreationCommand'))):
		check_environment()

#This is fired when the checkbox changes value
def enable_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
	global addin_updating_checkbox_
	# Check if we are updating the checkbox programmatically, to avoid infinite event recursion
	if addin_updating_checkbox_: return
	checkbox_def: adsk.core.CheckBoxControlDefinition = args.command.parentCommandDefinition.controlDefinition
	set_drag_enabled(checkbox_def.isChecked)

#This is fired whenever the active document is switched
def document_activated_handler(args: adsk.core.WorkspaceEventArgs):
	check_environment()
	
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Gets the value of Fusion's "Component Drag" checkbox
def get_drag_enabled(): return fusion_drag_controls_def_.isChecked	
#Sets the Fusion's "Component Drag" checkbox to the given value
def set_drag_enabled(value:bool): fusion_drag_controls_def_.isChecked = value

def update_checkbox():
	# Only set the checkbox value (triggering a command creation), if the
	# direct edit value has actually changed
	global addin_updating_checkbox_
	direct_edit_drag_ = get_drag_enabled()
	if enable_ctrl_def_.isChecked != direct_edit_drag_:
		addin_updating_checkbox_ = True
		enable_ctrl_def_.isChecked = direct_edit_drag_
		addin_updating_checkbox_ = False

def check_environment():
	global enable_ctrl_def_, parametric_environment_
	# Checking workspace type in DocumentActivated handler fails since Fusion 360 v2.0.10032
	# UserInterface.ActiveWorkspace throws when it is called from DocumentActivatedHandler
	# during Fusion 360 start-up(?). Checking for app_.isStartupComplete does not help.
	is_parametric = bool(utils.is_parametric_mode())
	if parametric_environment_ == is_parametric: return # Environment did not change
	# Hide/show our menu command to avoid showing to Component Drag menu items in direct edit mode (Our command + Fusion's command).
	enable_ctrl_def_.isVisible = parametric_environment_ = is_parametric
	# We only need to update checkbox in parametric mode, as it will not be seen in direct edit mode.
	# Fusion crashes if we change isChecked from (one of?) the event handlers, so we put the update at the end of the event queue.
	if is_parametric and enable_ctrl_def_.isChecked != get_drag_enabled():
		events_manager_.delay(update_checkbox)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def run(context):
	#Expose global variables inside of function
	global app_, ui_, enable_ctrl_def_, select_panel_controls, fusion_drag_controls_def_
	with error_catcher_:
		app_, ui_ = utils.AppObjects()
		fusion_drag_controls_def_ = ui_.commandDefinitions.itemById(FUSION_CTRL_ID).controlDefinition
		# There are multiple select panels. Pick the right one
		select_panel_controls = ui_.toolbarPanelsByProductType('DesignProductType').itemById('SelectPanel').controls

		# Clearing any previous enable_cmd_def  # Removing the old control
		utils.clear_ui_items(ui_.commandDefinitions.itemById(ENABLE_CMD_ID), select_panel_controls.itemById(ENABLE_CMD_ID))

		# Use a Command to get a transaction when renaming
		enable_cmd_def_ = ui_.commandDefinitions.addCheckBoxDefinition(ENABLE_CMD_ID, 'Component Drag', COMMAND_DATA, get_drag_enabled())
		select_panel_controls.addCommand(enable_cmd_def_, FUSION_CTRL_ID, False) #Adding in the fresh control
		enable_ctrl_def_ = enable_cmd_def_.controlDefinition

		#Adds all needed handlers to the event manager
		events_manager_.add_handler(enable_cmd_def_.commandCreated, callback=enable_cmd_created_handler)
		events_manager_.add_handler(ui_.commandStarting, callback=command_starting_handler)
		events_manager_.add_handler(ui_.commandTerminated, callback=command_terminated_handler)
		events_manager_.add_handler(app_.documentActivated, callback=document_activated_handler)
		
		# Workspace is not ready when starting (?)
		# Create a workspace activated handler to wait untill it is ready.
		if not bool(context['IsApplicationStartup']): check_environment()
		else: events_manager_.add_handler(ui_.workspaceActivated, callback=workspace_activated_handler)


def stop(context):
	with error_catcher_: events_manager_.clean_up(select_panel_controls.itemById(ENABLE_CMD_ID))


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
