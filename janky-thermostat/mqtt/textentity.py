from typing import Any, Callable, Dict, Optional

from .device import MQTTDevice
from .entity import MQTTEntity


class TextEntity(MQTTEntity):
    def __init__(
        self,
        object_id: str,
        name: str,
        *,
        value: str = "",
        min_length: int = 0,
        max_length: int = 255,
        pattern: Optional[str] = None,
        mode: str = "text",
        entity_category: Optional[str] = None,
        retain: bool = True,
        on_command: Callable[[str], None],
    ):
        super().__init__(
            domain="text",
            object_id=object_id,
            name=name,
            value=value,
            entity_category=entity_category,
            retain=retain,
            on_command=on_command,
        )
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.mode = mode

    def discovery_payload(self, device: MQTTDevice) -> Dict[str, Any]:
        payload = super().discovery_payload(device)
        payload.update(
            {
                "min": self.min_length,
                "max": self.max_length,
                "mode": self.mode,
            }
        )
        if self.pattern:
            payload["pattern"] = self.pattern
        return payload
