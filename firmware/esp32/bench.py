"""Deterministic model-output and NXT doubles for the camera-side firmware."""

from controller import HOLD_TIMEOUT_MS, CameraController

TAP_MS = 60
CARD = ("Run command?", "printf test", "Allow Once")
MULTILINE = ("Run command?", "printf alpha", "printf bravo", "Allow Once")


class BrickSimulator:
    """One transaction per arming. Events model completed key movement."""

    def __init__(self, session):
        self.session = session
        self.state = "ready"
        self.deadline = 0
        self.keys = []

    def release(self):
        if self.state == "tapping":
            self.keys.append("Enter up")
        if self.state in ("held", "tapping"):
            self.keys.append("Option up")
        self.state = "done"

    def tick(self, now):
        if self.state in ("held", "tapping") and now >= self.deadline:
            self.release()

    def receive(self, now, packet):
        self.tick(now)
        if packet is None:
            return None
        command, session = packet
        if session != self.session or self.state == "done":
            return None
        if command == "release":
            self.release()
        elif command == "hold" and self.state == "ready":
            self.keys.append("Option down")
            self.state = "held"
            self.deadline = now + HOLD_TIMEOUT_MS
            return ("held", session)
        elif command == "tap" and self.state == "held":
            self.keys.append("Enter down")
            self.state = "tapping"
            self.deadline = now + TAP_MS
        return None


class Bench:
    """Run each input at its supplied virtual time. ACKs can be delayed or lost."""

    def __init__(self, cards=(CARD, MULTILINE), session=1):
        self.camera = CameraController(cards, session)
        self.brick = BrickSimulator(session)
        self.last_ack = None
        self.now = -1
        self.packets = []

    def event(self, now, kind, *args):
        if now < self.now:
            raise ValueError("Replay time must be nondecreasing")
        self.now = now
        self.brick.tick(now)
        packet = self.camera.tick(now)
        if packet is None:
            if kind == "frame":
                packet = self.camera.frame(now, *args)
            elif kind == "ack" and self.last_ack:
                packet = self.camera.held(now, self.last_ack[1])
            elif kind not in ("ack", "tick"):
                raise ValueError("Unknown replay event")
        if packet:
            self.packets.append(packet)
            self.last_ack = self.brick.receive(now, packet)
        return packet


def observe(bench, now, sequence, card=CARD, confidence=990, complete=True, captured=None):
    lines = [(word, confidence) for word in card]
    return bench.event(now, "frame", sequence, now if captured is None else captured, complete, lines)


def held_bench():
    bench = Bench()
    observe(bench, 10, 1)
    observe(bench, 20, 2)
    assert bench.brick.keys == ["Option down"]
    return bench


def exercise():
    full_chord = ["Option down", "Enter down", "Enter up", "Option up"]
    cancel = ["Option down", "Option up"]
    for card in (CARD, MULTILINE):
        bench = Bench()
        observe(bench, 10, 1, card)
        observe(bench, 20, 2, card, confidence=700)
        bench.event(30, "ack")
        observe(bench, 40, 3, card, captured=25)
        assert bench.brick.keys == ["Option down"]
        observe(bench, 50, 4, card)
        assert bench.brick.keys == full_chord[:2]
        bench.event(110, "tick")
        observe(bench, 120, 5, card)
        observe(bench, 130, 6, card)
        assert bench.brick.keys == full_chord
    print("PASS single/multiline, fresh post-hold frame, one chord per arming")

    for card, score, complete in ((CARD, 699, True), (CARD, 990, False), ((), 990, True),
                                  (MULTILINE[:-2] + ("printf delta", "Allow Once"), 990, True)):
        bench = Bench()
        observe(bench, 10, 1, card, score, complete)
        observe(bench, 20, 2, card, score, complete)
        assert bench.brick.keys == []
    print("PASS low confidence, incomplete card, missing card, changed final command line")

    bench = Bench()
    observe(bench, 10, 1)
    observe(bench, 20, 1)
    observe(bench, 21, 0)
    observe(bench, 3000, 2, captured=40)
    observe(bench, 3010, 3)
    assert bench.brick.keys == []
    print("PASS duplicate, reordered and stale observations")

    bench = held_bench()
    bench.event(30, "ack")
    observe(bench, 40, 3, MULTILINE)
    assert bench.brick.keys == cancel
    bench.brick.receive(50, ("tap", 1))
    assert bench.brick.keys == cancel
    print("PASS different approved card during hold cancels the pending tap")

    bench = held_bench()
    assert bench.camera.held(25, 99) is None
    observe(bench, 30, 3)
    assert bench.brick.keys == ["Option down"]
    bench.brick.tick(20 + HOLD_TIMEOUT_MS)
    assert bench.brick.keys == cancel
    assert bench.camera.tick(20 + HOLD_TIMEOUT_MS) == ("release", 1)
    print("PASS lost or wrong ACK, independent brick release on link loss")

    brick = BrickSimulator(2)
    brick.receive(0, ("hold", 1))
    brick.receive(1, ("tap", 2))
    assert brick.keys == []
    for i, command in enumerate(("hold", "hold", "tap", "tap")):
        brick.receive(10 + i, (command, 2))
    brick.tick(100)
    assert brick.keys == full_chord
    print("PASS wrong session, tap before hold and duplicate motor packets")
    print("ESP32 BENCH PASS")


if __name__ == "__main__":
    exercise()
