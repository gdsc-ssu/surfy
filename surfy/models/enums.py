from enum import Enum


class TaskStatus(str, Enum):
    NEW = "NEW"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    EXIT = "EXIT"


class ActionType(str, Enum): # TODO: 변경될 수 있음
    CLICK = "CLICK"
    TYPE = "TYPE"
    SCROLL = "SCROLL"
    HOVER = "HOVER"
    SELECT_OPTION = "SELECT_OPTION"
    PRESS_KEY = "PRESS_KEY"
    WAIT = "WAIT"
    GO_TO_URL = "GO_TO_URL"
    GO_BACK = "GO_BACK"


class ExecutorType(str, Enum):
    AGENT = "AGENT"
    HUMAN = "HUMAN"

