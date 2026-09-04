"""Normalising three platform vocabularies into one.

The same idea as :mod:`use_computer.keys`: an agent learns one spelling and it works everywhere.
AT-SPI's ``push button``, UIA's ``ButtonControl`` and macOS's ``AXButton`` are all ``button``.

This module is pure -- it maps strings, and never imports a binding.
"""

from __future__ import annotations

#: Canonical action names. These are the action set members that operate an element.
CLICK = "click"
FOCUS = "focus"
TOGGLE = "toggle"
EXPAND = "expand"
COLLAPSE = "collapse"
SELECT = "select"
SET_VALUE = "set_value"
SHOW_MENU = "show_menu"

ELEMENT_ACTIONS = (CLICK, FOCUS, TOGGLE, EXPAND, COLLAPSE, SELECT, SET_VALUE, SHOW_MENU)

_ATSPI_ROLES = {
    "push button": "button",
    "toggle button": "toggle",
    "check box": "checkbox",
    "check menu item": "menuitem",
    "radio button": "radio",
    "radio menu item": "menuitem",
    "combo box": "combobox",
    "list box": "list",
    "list item": "listitem",
    "menu item": "menuitem",
    "page tab": "tab",
    "page tab list": "tablist",
    "text": "text",
    "entry": "text",
    "password text": "text",
    "spin button": "spinner",
    "progress bar": "progressbar",
    "tool bar": "toolbar",
    "scroll bar": "scrollbar",
    "status bar": "statusbar",
    "table row": "row",
    "table cell": "cell",
    "table column header": "columnheader",
    "tree item": "treeitem",
    "tree table": "table",
    "document frame": "document",
    "document web": "document",
    "frame": "window",
    "filler": "panel",
    "section": "panel",
    "static": "label",
    "label": "label",
    "link": "link",
    "image": "image",
    "icon": "image",
    "dialog": "dialog",
    "alert": "dialog",
    "window": "window",
    "menu": "menu",
    "menu bar": "menubar",
    "panel": "panel",
    "slider": "slider",
    "separator": "separator",
    "heading": "heading",
    "application": "application",
}

_UIA_ROLES = {
    "button": "button",
    "calendar": "calendar",
    "checkbox": "checkbox",
    "combobox": "combobox",
    "custom": "panel",
    "dataitem": "listitem",
    "datagrid": "table",
    "document": "document",
    "edit": "text",
    "group": "panel",
    "header": "columnheader",
    "headeritem": "columnheader",
    "hyperlink": "link",
    "image": "image",
    "list": "list",
    "listitem": "listitem",
    "menu": "menu",
    "menubar": "menubar",
    "menuitem": "menuitem",
    "pane": "panel",
    "progressbar": "progressbar",
    "radiobutton": "radio",
    "scrollbar": "scrollbar",
    "separator": "separator",
    "slider": "slider",
    "spinner": "spinner",
    "splitbutton": "button",
    "statusbar": "statusbar",
    "tab": "tablist",
    "tabitem": "tab",
    "table": "table",
    "text": "label",
    "thumb": "slider",
    "titlebar": "titlebar",
    "toolbar": "toolbar",
    "tooltip": "tooltip",
    "tree": "tree",
    "treeitem": "treeitem",
    "window": "window",
}

_AX_ROLES = {
    "button": "button",
    "cell": "cell",
    "checkbox": "checkbox",
    "combobox": "combobox",
    "disclosuretriangle": "toggle",
    "group": "panel",
    "image": "image",
    "incrementor": "spinner",
    "link": "link",
    "list": "list",
    "menu": "menu",
    "menubar": "menubar",
    "menubaritem": "menuitem",
    "menuitem": "menuitem",
    "outline": "tree",
    "popupbutton": "combobox",
    "progressindicator": "progressbar",
    "radiobutton": "radio",
    "row": "row",
    "scrollarea": "panel",
    "scrollbar": "scrollbar",
    "sheet": "dialog",
    "slider": "slider",
    "splitgroup": "panel",
    "statictext": "label",
    "tabgroup": "tablist",
    "table": "table",
    "textarea": "text",
    "textfield": "text",
    "toolbar": "toolbar",
    "window": "window",
}

_STATES = {
    "sensitive": "enabled",
    "enabled": "enabled",
    "focusable": "focusable",
    "focused": "focused",
    "editable": "editable",
    "showing": "showing",
    "visible": "showing",
    "selected": "selected",
    "selectable": "selectable",
    "checked": "checked",
    "expanded": "expanded",
    "collapsed": "collapsed",
    "expandable": "expandable",
    "read only": "readonly",
    "readonly": "readonly",
    "offscreen": "offscreen",
    "invalid": "invalid",
    "busy": "busy",
    "modal": "modal",
}

#: AT-SPI action names are chosen by the toolkit, so several spellings mean the same thing.
_ATSPI_ACTIONS = {
    "click": CLICK,
    "press": CLICK,
    "activate": CLICK,
    "jump": CLICK,
    "open": CLICK,
    "toggle": TOGGLE,
    "check": TOGGLE,
    "expand or contract": EXPAND,
    "expand": EXPAND,
    "collapse": COLLAPSE,
    "select": SELECT,
    "menu": SHOW_MENU,
    "show menu": SHOW_MENU,
}

_AX_ACTIONS = {
    "axpress": CLICK,
    "axopen": CLICK,
    "axconfirm": CLICK,
    "axpick": SELECT,
    "axshowmenu": SHOW_MENU,
    "axincrement": EXPAND,
    "axdecrement": COLLAPSE,
}


def _slug(raw: str) -> str:
    return raw.strip().lower().replace("_", " ").replace("-", " ")


def atspi_role(raw: str) -> str:
    return _ATSPI_ROLES.get(_slug(raw), _slug(raw).replace(" ", ""))


def uia_role(raw: str) -> str:
    name = _slug(raw).replace(" ", "")
    if name.endswith("control"):
        name = name[: -len("control")]
    return _UIA_ROLES.get(name, name)


def ax_role(raw: str) -> str:
    name = _slug(raw).replace(" ", "")
    if name.startswith("ax"):
        name = name[2:]
    return _AX_ROLES.get(name, name)


def state(raw: str) -> str:
    return _STATES.get(_slug(raw), _slug(raw).replace(" ", ""))


def atspi_action(raw: str) -> str | None:
    """Canonical name for a toolkit-chosen AT-SPI action, or None if it is not one of ours."""
    return _ATSPI_ACTIONS.get(_slug(raw))


def ax_action(raw: str) -> str | None:
    return _AX_ACTIONS.get(_slug(raw).replace(" ", ""))


__all__ = [
    "CLICK",
    "COLLAPSE",
    "ELEMENT_ACTIONS",
    "EXPAND",
    "FOCUS",
    "SELECT",
    "SET_VALUE",
    "SHOW_MENU",
    "TOGGLE",
    "atspi_action",
    "atspi_role",
    "ax_action",
    "ax_role",
    "state",
    "uia_role",
]
