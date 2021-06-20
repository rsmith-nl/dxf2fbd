Converting DXF scetches to CalculiX FBD format
##############################################

:date: 2021-06-20
:tags: CalculiX, DXF
:author: Roland Smith

.. Last modified: 2021-06-20T17:47:04+0200
.. vim:spelllang=en

Introduction
============

The author regularly creates extrusions (using “swep”) in CalculiX Graphics.
Doing this manually is a relatively time-consuming process.

For a non-parametric part, it is easier to scetch the geometry in a 2D CAD
program like LibreCAD_, and then convert that scetch to instructions for
CalculiX Graphics.

.. _LibreCAD: https://librecad.org/

This is what ``dxf2fbd.py`` does.

.. PELICAN_END_SUMMARY

What it does
============

It looks in the layer named “contour” in the DXF files, and extracts LINE and
ARC entities. *Other entities and layers are ignored.*

It outputs CalculiX Graphics commands for creating these points, lines and
arcs.
The XY plane in the DXF file is thereby converted in the YZ plane in CalculiX.
*Any Z values in the DXF entities are ignored*.

The distance between coordinates that should not be considered identical in
set in the global ``EPS`` value.
The scaling factor for point coordinates is set in the global ``SCALE`` value.
Currently it is set to convert millimeters in DXF to meters in CalculiX.

The program looks for sets of four lines that form a closed loop.
Those will be defined as surfaces.

What it doesn't do
==================

* Set line divisions
* Create sets

In the view of the author, these are best left to the operator.


Requirements
============

This program requires at least Python 3.6.
It has no library requirments outside of the Python standard library.
This version was developed and tested using Python 3.7 and 3.9.


Installation
------------

To install it for the local user, run::

    python setup.py install

This will install it in the user path for Python scripts.
For POSIX operating systems this is ususally ``~/.local/bin``.
For ms-windows this is the ``Scripts`` directory of your Python installation
or another local directory.
Make sure that this directory is in your ``$PATH`` environment variable.
