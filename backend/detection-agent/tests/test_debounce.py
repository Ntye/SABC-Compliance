"""Debounce logic — rapid successive events on the same path collapse."""
from __future__ import annotations

from agent import Debouncer


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make(window: float = 2.0) -> tuple[Debouncer, FakeClock]:
    clock = FakeClock()
    return Debouncer(window=window, clock=clock), clock


class TestDebounce:
    def test_event_held_until_window_elapses(self) -> None:
        d, clock = make()
        d.offer("/etc/passwd", "modified")
        assert d.pop_due() == []            # t=0: still inside the window
        clock.advance(1.9)
        assert d.pop_due() == []            # t=1.9: still quiet-period
        clock.advance(0.1)
        assert d.pop_due() == [("/etc/passwd", "modified")]  # t=2.0: released

    def test_burst_on_same_path_collapses_to_one(self) -> None:
        d, clock = make()
        for _ in range(10):
            d.offer("/etc/ssh/sshd_config", "modified")
            clock.advance(0.1)              # 10 events over 1 s
        clock.advance(2.0)
        due = d.pop_due()
        assert due == [("/etc/ssh/sshd_config", "modified")]
        assert d.pending_count() == 0

    def test_each_new_event_resets_the_timer(self) -> None:
        d, clock = make()
        d.offer("/etc/group", "modified")
        clock.advance(1.5)
        d.offer("/etc/group", "modified")   # resets the quiet period
        clock.advance(1.5)
        assert d.pop_due() == []            # only 1.5 s since the last event
        clock.advance(0.5)
        assert d.pop_due() == [("/etc/group", "modified")]

    def test_last_event_type_wins(self) -> None:
        d, clock = make()
        d.offer("/etc/sudoers", "created")
        clock.advance(0.5)
        d.offer("/etc/sudoers", "modified")
        clock.advance(0.5)
        d.offer("/etc/sudoers", "deleted")  # e.g. temp file dance ends in delete
        clock.advance(2.0)
        assert d.pop_due() == [("/etc/sudoers", "deleted")]

    def test_distinct_paths_do_not_interfere(self) -> None:
        d, clock = make()
        d.offer("/etc/passwd", "modified")
        clock.advance(1.0)
        d.offer("/etc/group", "modified")
        clock.advance(1.0)                  # passwd quiet 2.0s, group quiet 1.0s
        assert d.pop_due() == [("/etc/passwd", "modified")]
        clock.advance(1.0)
        assert d.pop_due() == [("/etc/group", "modified")]

    def test_released_event_is_not_repeated(self) -> None:
        d, clock = make()
        d.offer("/etc/passwd", "modified")
        clock.advance(2.5)
        assert len(d.pop_due()) == 1
        assert d.pop_due() == []
