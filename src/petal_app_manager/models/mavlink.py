from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RebootStatusCode(str, Enum):
    # Success
    OK_ACK_ACCEPTED = "OK_ACK_ACCEPTED"
    OK_REBOOT_CONFIRMED_NO_ACK = "OK_REBOOT_CONFIRMED_NO_ACK"

    # Failures
    FAIL_ACK_DENIED = "FAIL_ACK_DENIED"
    FAIL_ACK_TEMPORARILY_REJECTED = "FAIL_ACK_TEMPORARILY_REJECTED"
    FAIL_ACK_UNSUPPORTED = "FAIL_ACK_UNSUPPORTED"
    FAIL_ACK_FAILED = "FAIL_ACK_FAILED"
    FAIL_ACK_IN_PROGRESS = "FAIL_ACK_IN_PROGRESS"
    FAIL_ACK_CANCELLED = "FAIL_ACK_CANCELLED"
    FAIL_NO_ACK_MATCH = "FAIL_NO_ACK_MATCH"
    FAIL_NO_HEARTBEAT_TRACKING = "FAIL_NO_HEARTBEAT_TRACKING"
    FAIL_REBOOT_NOT_CONFIRMED_NO_HB_DROP = "FAIL_REBOOT_NOT_CONFIRMED_NO_HB_DROP"
    FAIL_REBOOT_NOT_CONFIRMED_HB_NO_RETURN = "FAIL_REBOOT_NOT_CONFIRMED_HB_NO_RETURN"
    FAIL_ACK_UNKNOWN = "FAIL_ACK_UNKNOWN"


class RebootAutopilotResponse(BaseModel):
    """
    Response model for reboot_autopilot().

    - success: True if reboot was accepted or confirmed by heartbeat drop+return.
    - status_code: Machine-friendly status describing the outcome.
    - reason: Human-friendly explanation for logs/UI.
    - ack_result: MAVLink COMMAND_ACK result code (if received).
    """
    success: bool = Field(..., description="Whether reboot was successful/confirmed.")
    status_code: RebootStatusCode = Field(..., description="Machine-friendly outcome code.")
    reason: str = Field(..., description="Human-friendly explanation of the outcome.")
    ack_result: Optional[int] = Field(
        None,
        description="MAVLink COMMAND_ACK result value when an ACK was received; otherwise None.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "status_code": "OK_ACK_ACCEPTED",
                    "reason": "Autopilot acknowledged the reboot command (ACCEPTED).",
                    "ack_result": 0,
                },
                {
                    "success": False,
                    "status_code": "FAIL_ACK_DENIED",
                    "reason": "Autopilot rejected the reboot command: DENIED.",
                    "ack_result": 2,
                },
                {
                    "success": True,
                    "status_code": "OK_REBOOT_CONFIRMED_NO_ACK",
                    "reason": "No ACK received, but reboot confirmed via heartbeat drop + return.",
                    "ack_result": None,
                },
            ]
        }
    }
