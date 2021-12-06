# Event managing.
# 
# Allows catching events with functions instead of classes.
# Tracks registered events and allows clean-up with one function call.
# All event callbacks are also wrapped in an error.ErrorCatcher().
#
# This file is part of thomasa88lib, a library of useful Fusion 360
# add-in/script functions.
#
# Copyright (c) 2020 Thomas Axelsson
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

import adsk.core, adsk.fusion, adsk.cam
import sys, time
import threading
from typing import List, Tuple
# Avoid Fusion namespace pollution
from . import error, utils

# Try to resolve base class automatically
AUTO_HANDLER_CLASS = None

class EventsManager:
	def __init__(self, error_catcher=None):
		#Declared in init to allow multiple commands to use a single lib
		self.handlers: List[Tuple(type, adsk.core.CommandEvent)] = []
		self.custom_event_names = []
		self.app, self.ui = utils.AppObjects()

		self.next_delay_id = 0
		self.delayed_funcs = {}
		self.delayed_event = None
		self.delayed_event_id = utils.get_caller_path() + '_delay_event'
		self.error_catcher = error_catcher if error_catcher != None else error.ErrorCatcher()
	
	#Assigning
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def add_handler(self, event:adsk.core.CommandEvent, base_class=AUTO_HANDLER_CLASS, callback=None):
		"""`AUTO_HANDLER_CLASS` results in:
		  1: Getting the classType
		  2: Adding 'Handler' to the end
		  3: Splitting at '::'
		  4: Getting the module using the first segment
		  5: sets baseClass to the return of getattr using the base and all subsequent segments (should be 1)"""
		if base_class == AUTO_HANDLER_CLASS:
			handler_classType_name :str = event.classType() + 'Handler'
			handler_class_parts = handler_classType_name.split('::')
			base_class = sys.modules[handler_class_parts[0]]
			for cls in handler_class_parts[1:]: base_class = getattr(base_class, cls)

		handler_name = base_class.__name__ + '_' + callback.__name__
		handler_class = type(handler_name, (base_class,), {"notify": error._error_catcher_wrapper(self, callback)})
		handler_class.__init__ = lambda self: super(handler_class, self).__init__()
		handler = handler_class()
		result = event.add(handler)
		if not result: raise Exception('Failed to add handler ' + callback.__name__)


		handler_info = (handler, event)
		self.handlers.append(handler_info)# Avoid garbage collection
		return handler_info
	
	def register_event(self, name):
		# Clears and then starts the event (makes sure there is not an old event registered due to a bad stop)
		self.app.unregisterCustomEvent(name)
		event = self.app.registerCustomEvent(name)
		if event: self.custom_event_names.append(name)
		return event

	#Timing
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def delay(self, func, secs=0):
		'''Puts a function at the end of the event queue, and optionally delays it. '''
		if self.delayed_event is None:# Register the event. Will be removed when user runs clean_up()
			self.delayed_event = self.register_event(self.delayed_event_id)
			self.add_handler(self.delayed_event, callback=self._delayed_event_handler)
		delay_id = self.next_delay_id
		self.next_delay_id += 1

		def waiter():
			time.sleep(secs)
			self.app.fireCustomEvent(self.delayed_event_id, str(delay_id))
		self.delayed_funcs[delay_id] = func

		if secs > 0:
			thread = threading.Thread(target=waiter)
			thread.isDaemon = True
			thread.start()
		else: self.app.fireCustomEvent(self.delayed_event_id, str(delay_id))    

	def _delayed_event_handler(self, args: adsk.core.CustomEventArgs):
		delay_id = int(args.additionalInfo)
		func = self.delayed_funcs.pop(delay_id, None)
		func()


	#Removing
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def remove_handler(self, handler_info):
		handler, event = handler_info
		self.handlers.remove(handler_info)
		event.remove(handler)
		return None # Let user assign their handle with the return value

	def remove_all_handlers(self):
		for handler, event in self.handlers:
			try:event.remove(handler)
			except:pass
		self.handlers.clear()

	def unregister_all_events(self):
		for event_name in self.custom_event_names:
			self.app.unregisterCustomEvent(event_name)
		self.custom_event_names.clear()

	def clean_up(self, oldControl = None):
		"""`oldControl` is an optional variable that, if/when provided, the function: \\
		`utils.clear_ui_items(oldControl)`  is called, which attempts to remove the control after cleanup"""
		self.remove_all_handlers()
		self.unregister_all_events()
		if oldControl is not None: utils.clear_ui_items(oldControl)

	def find_handler_by_event(self, findevent):
		eventName = findevent.name
		for handler, event in self.handlers:
			if eventName == event.name: 
				return handler






  
# # Event managing.
# # 
# # Allows catching events with functions instead of classes.
# # Tracks registered events and allows clean-up with one function call.
# # All event callbacks are also wrapped in an error.ErrorCatcher().
# #
# # This file is part of thomasa88lib, a library of useful Fusion 360
# # add-in/script functions.
# #
# # Copyright (c) 2020 Thomas Axelsson
# # 
# # Permission is hereby granted, free of charge, to any person obtaining a copy
# # of this software and associated documentation files (the "Software"), to deal
# # in the Software without restriction, including without limitation the rights
# # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# # copies of the Software, and to permit persons to whom the Software is
# # furnished to do so, subject to the following conditions:
# # 
# # The above copyright notice and this permission notice shall be included in all
# # copies or substantial portions of the Software.
# # 
# # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# # SOFTWARE.

# import adsk.core, adsk.fusion, adsk.cam, traceback

# import sys
# import threading
# import time

# # Avoid Fusion namespace pollution
# from . import error
# from . import utils

# # Try to resolve base class automatically
# AUTO_HANDLER_CLASS = None

# class EventsManager:
#     def __init__(self, error_catcher=None):
#         self.handlers = []
#         self.custom_event_names = []

#         self.next_delay_id = 0
#         self.delayed_funcs = {}
#         self.delayed_event = None
#         self.delayed_event_id = utils.get_caller_path() + '_delay_event'

#         self.app = adsk.core.Application.get()
#         self.ui = self.app.userInterface

#         if not error_catcher:
#             error_catcher = error.ErrorCatcher()
#         self.error_catcher = error_catcher
    
#     def clean_up(self):
#         self.remove_all_handlers()
#         self.unregister_all_events()
    
#     def add_handler(self, event, base_class=AUTO_HANDLER_CLASS, callback=None):
#         if base_class == AUTO_HANDLER_CLASS:
#             handler_class_typename = event.classType() + 'Handler'
#             handler_class_parts = handler_class_typename.split('::')
#             base_class = sys.modules[handler_class_parts[0]]
#             for cls in handler_class_parts[1:]:
#                 base_class = getattr(base_class, cls)
#         handler_name = base_class.__name__ + '_' + callback.__name__
#         handler_class = type(handler_name, (base_class,),
#                             { "notify": self._error_catcher_wrapper(callback) })
#         handler_class.__init__ = lambda self: super(handler_class, self).__init__()
#         handler = handler_class()
#         handler_info = (handler, event)

#         result = event.add(handler)
#         if not result:
#             raise Exception('Failed to add handler ' + callback.__name__)
        
#         # Avoid garbage collection
#         self.handlers.append(handler_info)
#         return handler_info

#     def remove_handler(self, handler_info):
#         handler, event = handler_info
#         self.handlers.remove(handler_info)
#         event.remove(handler)
#         # Let user assign their handle with the return value
#         return None

#     def remove_all_handlers(self):
#         for handler, event in self.handlers:
#             event.remove(handler)
#         self.handlers.clear()
    
#     def register_event(self, name):
#         # Make sure there is not an old event registered due to a bad stop
#         self.app.unregisterCustomEvent(name)

#         event = self.app.registerCustomEvent(name)
#         if event:
#             self.custom_event_names.append(name)
#         return event

#     def unregister_all_events(self):
#         for event_name in self.custom_event_names:
#             self.app.unregisterCustomEvent(event_name)
#         self.custom_event_names.clear()

#     def delay(self, func, secs=0):
#         '''Puts a function at the end of the event queue,
#         and optionally delays it.
#         '''

#         if self.delayed_event is None:
#             # Register the event. Will be removed when user runs clean_up()
#             self.delayed_event = self.register_event(self.delayed_event_id)
#             self.add_handler(self.delayed_event,
#                              callback=self._delayed_event_handler)

#         delay_id = self.next_delay_id
#         self.next_delay_id += 1

#         def waiter():
#             time.sleep(secs)
#             self.app.fireCustomEvent(self.delayed_event_id, str(delay_id))

#         self.delayed_funcs[delay_id] = func

#         if secs > 0:
#             thread = threading.Thread(target=waiter)
#             thread.isDaemon = True
#             thread.start()
#         else:
#             self.app.fireCustomEvent(self.delayed_event_id, str(delay_id))    

#     def _error_catcher_wrapper(class_self, func):
#         def catcher(func_self, args):
#             with class_self.error_catcher:
#                 func(args)
#         return catcher

#     def _delayed_event_handler(self, args: adsk.core.CustomEventArgs):
#         delay_id = int(args.additionalInfo)
#         func = self.delayed_funcs.pop(delay_id, lambda: None)
#         func()
