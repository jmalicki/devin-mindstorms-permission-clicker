"""Camera-side, one-shot controller. Runs unchanged on ESP32 MicroPython and CPython."""

# Times in this interface are nondecreasing milliseconds since arming. The camera
# adapter maps acquisition timestamps into this clock domain before delivery.
MAX_FRAME_AGE_MS = 2000
HOLD_TIMEOUT_MS = 2000
MIN_CONFIDENCE_PER_MILLE = 700


class CameraController:
    def __init__(self, allowed, session):
        if not session or not allowed:
            raise ValueError("Arming requires a session token and configured card lines")
        self.allowed = {tuple(card) for card in allowed}
        if any(len(card) < 3 or not all(card) for card in self.allowed):
            raise ValueError("Each card must include heading, command and approval label")
        self.session = session
        self.state = "watch"
        self.candidate = None
        self.sequence = -1
        self.captured = -1
        self.deadline = 0
        self.held_at = -1

    def abort(self):
        self.state = "done"
        return ("release", self.session)

    def tick(self, now):
        if self.state in ("await_hold", "confirm") and now >= self.deadline:
            return self.abort()
        return None

    def held(self, now, session):
        expired = self.tick(now)
        if expired:
            return expired
        if self.state == "await_hold" and session == self.session:
            self.state = "confirm"
            self.held_at = now
        return None

    def frame(self, now, sequence, captured, complete, lines):
        expired = self.tick(now)
        if expired or self.state == "done":
            return expired
        # A duplicate or out-of-order packet is never a new observation.
        if sequence <= self.sequence:
            return None
        self.sequence = sequence
        previous_time = self.captured
        fresh = previous_time < captured <= now and now - captured <= MAX_FRAME_AGE_MS
        if fresh:
            self.captured = captured
        card = None
        if fresh and complete and lines:
            if all(MIN_CONFIDENCE_PER_MILLE <= score <= 1000 for _, score in lines):
                observed = tuple(text for text, _ in lines)
                if observed in self.allowed:
                    card = observed

        if self.state == "watch":
            stable = card is not None and card == self.candidate and captured - previous_time <= MAX_FRAME_AGE_MS
            self.candidate = card
            if stable:
                self.state = "await_hold"
                self.deadline = now + HOLD_TIMEOUT_MS
                return ("hold", self.session)
            return None

        if card != self.candidate:
            return self.abort()
        if self.state == "confirm" and captured > self.held_at:
            self.state = "done"
            return ("tap", self.session)
        return None
