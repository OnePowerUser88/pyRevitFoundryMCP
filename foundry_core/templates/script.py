# -*- coding: utf-8 -*-
"""{{title}} - pyRevit script template."""

__title__ = "{{title}}"
__author__ = "{{author}}"
__doc__ = "{{doc}}"

# Imports
from Autodesk.Revit.DB import *
from pyrevit import revit, forms

# Variables
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application

# Main
if __name__ == "__main__":
    # START CODE HERE
    print("{{title}}")
