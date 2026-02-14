"""Sample script for testing."""
__title__ = "My Button"
__author__ = "Test"
__doc__ = "A test button"

# Unused import
import os

from Autodesk.Revit.DB import Document

def main():
    doc = __revit__.ActiveUIDocument.Document
    print(doc.Title)
