#Author-Thomas Axelsson, ZXYNINE
#Description-Blocks Component Dragging in parametric mode

# This file is part of NoComponentDrag, a Fusion 360 add-in for blocking
# component dragging.

import adsk.core, adsk.fusion, adsk.cam, traceback
import math, os, operator, time
from collections import deque

# Import relative path to avoid namespace pollution
from .thomasa88lib import utils, events, manifest, error
utils.ReImport_List(events, manifest, error, utils)

NAME = 'NoComponentDrag'
VERSION = str(manifest.read()["version"])
FILE_DIR = os.path.dirname(os.path.realpath(__file__))
ENABLE_CMD_ID = 'thomasa88_NoComponentDrag_Enable'
VERSION_INFO = f'({NAME} v {VERSION})'
CMD_DESCRIPTION = 'Enables or disables the movement of components by dragging in the canvas.'

app_ = ui_ = None
error_catcher_ = error.ErrorCatcher()
events_manager_ = events.EventsManager(error_catcher_)

select_panel_ = None
enable_cmd_def_ = None
parametric_environment_ = True
addin_updating_checkbox_ = False
fusion_drag_controls_cmd_def_ = None



def command_starting_handler(args: adsk.core.ApplicationCommandEventArgs):
	# Should we block?
	if parametric_environment_ and args.commandId == 'FusionDragComponentsCommand' and not get_direct_edit_drag_enabled():
		args.isCanceled = True

# Fusion bug: DocumentActivated is not called when switching to/from Drawing.
# https://forums.autodesk.com/t5/fusion-360-api-and-scripts/api-bug-application-documentactivated-event-do-not-raise/m-p/9020750
def document_activated_handler(args: adsk.core.WorkspaceEventArgs):
	check_environment()

def set_direct_edit_drag_enabled(value):
	'''Sets the Fusion's "Component Drag" checkbox to the given value'''
	fusion_drag_controls_cmd_def_.controlDefinition.isChecked = value
# Gets the value of Fusion's "Component Drag" checkbox
get_direct_edit_drag_enabled = lambda : fusion_drag_controls_cmd_def_.controlDefinition.isChecked


def command_terminated_handler(args: adsk.core.ApplicationCommandEventArgs):
	# Detect if user toggles Direct Edit or enters/leaves a Base Feature
	# Undo/Redo triggers the ActivateEnvironmentCommand instead.
	# PLM360OpenAttachmentCommand, CurrentlyOpenDocumentsCommand are workarounds for DocumentActivated with Drawings bug.
	# https://forums.autodesk.com/t5/fusion-360-api-and-scripts/api-bug-application-documentactivated-event-do-not-raise/m-p/9020750
	if (args.commandId in ('ActivateEnvironmentCommand', 'PLM360OpenAttachmentCommand', 'CurrentlyOpenDocumentsCommand') or
		(args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason and
		 args.commandId in ('Undo', 'Redo','ConvertToPMDesignCommand', 'ConvertToDMDesignCommand',
							'BaseFeatureActivate', 'BaseFeatureStop', 'BaseFeatureCreationCommand'))):
		check_environment()

def enable_cmd_created_handler(args: adsk.core.CommandCreatedEventArgs):
	global addin_updating_checkbox_
	# Check if we are updating the checkbox programmatically, to avoid infinite event recursion
	if addin_updating_checkbox_: return
	checkbox_def: adsk.core.CheckBoxControlDefinition = args.command.parentCommandDefinition.controlDefinition
	set_direct_edit_drag_enabled(checkbox_def.isChecked)


def check_environment():
	global enable_cmd_def_, parametric_environment_
	# Checking workspace type in DocumentActivated handler fails since Fusion 360 v2.0.10032
	# UserInterface.ActiveWorkspace throws when it is called from DocumentActivatedHandler
	# during Fusion 360 start-up(?). Checking for app_.isStartupComplete does not help.
	is_parametric = utils.is_parametric_mode()
	if parametric_environment_ == is_parametric: return # Environment did not change
	parametric_environment_ = is_parametric

	# Hide/show our menu command to avoid showing to Component Drag menu items in direct edit mode (Our command + Fusion's command).
	enable_cmd_def_.controlDefinition.isVisible = is_parametric

	# We only need to update checkbox in parametric mode, as it will not be seen in direct edit mode.
	if is_parametric and enable_cmd_def_.controlDefinition.isChecked != get_direct_edit_drag_enabled():
		# Fusion crashes if we change isChecked from (one of?) the event handlers, so we put the update at the end of the event queue.
		events_manager_.delay(update_checkbox)

def update_checkbox():
	global addin_updating_checkbox_
	# Only set the checkbox value (triggering a command creation), if the
	# direct edit value has actually changed
	direct_edit_drag_ = get_direct_edit_drag_enabled()
	if enable_cmd_def_.controlDefinition.isChecked != direct_edit_drag_:
		addin_updating_checkbox_ = True
		enable_cmd_def_.controlDefinition.isChecked = direct_edit_drag_
		addin_updating_checkbox_ = False

def run(context):
	#Expose global variables inside of function
	global app_, ui_, enable_cmd_def_, select_panel_, fusion_drag_controls_cmd_def_, events_manager_
	FUSION_DRAG_ID = 'FusionDragCompControlsCmd'
	with error_catcher_:
		app_, ui_ = utils.AppObjects()
		fusion_drag_controls_cmd_def_ = ui_.commandDefinitions.itemById(FUSION_DRAG_ID)

		# Clearing any previous enable_cmd_def
		utils.clear_ui_items(ui_.commandDefinitions.itemById(ENABLE_CMD_ID))

		# There are multiple select panels. Pick the right one
		select_panel_ = ui_.toolbarPanelsByProductType('DesignProductType').itemById('SelectPanel')
		enabled = get_direct_edit_drag_enabled()

		# Use a Command to get a transaction when renaming
		enable_cmd_def_ = ui_.commandDefinitions.addCheckBoxDefinition(	ENABLE_CMD_ID,
																		'Component Drag',
																		CMD_DESCRIPTION + '\n\n'
																		+ VERSION_INFO + '\n',
																		enabled)
		utils.clear_ui_items(select_panel_.controls.itemById(ENABLE_CMD_ID)) # Removing the old control
		select_panel_.controls.addCommand(enable_cmd_def_, FUSION_DRAG_ID, False) #Adding in the fresh control
		
		#Adds all needed handlers to the event manager
		events_manager_.add_handler(enable_cmd_def_.commandCreated, callback=enable_cmd_created_handler)
		events_manager_.add_handler(ui_.commandStarting, callback=command_starting_handler)
		events_manager_.add_handler(ui_.commandTerminated, callback=command_terminated_handler)
		events_manager_.add_handler(app_.documentActivated, callback=document_activated_handler)

		# Workspace is not ready when starting (?)
		if app_.isStartupComplete: check_environment()
		# Put a check at the end of the event queue instead.
		events_manager_.delay(check_environment)

def stop(context):
	with error_catcher_:
		events_manager_.clean_up(select_panel_.controls.itemById(ENABLE_CMD_ID))

