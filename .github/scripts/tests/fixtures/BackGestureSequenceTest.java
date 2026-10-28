package ru.omnicio.ciframe;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/** Host tests of the same event sequence used by the Android test-only driver. */
public final class BackGestureSequenceTest {
    private record Event(long down, long time, int action, float x, float y) {}
    private static final class Clock implements BackGestureSequence.Clock {
        long time = 1000;
        @Override public long now() { return time; }
        @Override public void pause(long millis) { time += millis; }
    }
    private interface Checked { void run() throws IOException; }
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("Gesture sequence contract");
    }
    private static void rejected(Checked operation) throws IOException {
        try {
            operation.run();
        } catch (IOException expected) {
            return;
        }
        throw new AssertionError("Invalid gesture operation accepted");
    }
    private static BackGestureSequence sequence(Clock clock, List<Event> events) {
        return new BackGestureSequence(clock, (down, time, action, x, y) -> {
            events.add(new Event(down, time, action, x, y));
            return true;
        });
    }
    private static void cancelAndCommit() throws IOException {
        Clock clock = new Clock();
        List<Event> events = new ArrayList<>();
        try (BackGestureSequence touch = sequence(clock, events)) {
            touch.hold(320, 640);
            check(touch.isHeld());
            rejected(() -> touch.hold(320, 640));
            touch.cancel();
            check(!touch.isHeld());
            rejected(touch::commit);
            check(events.size() == 14);
            check(events.get(0).action == BackGestureSequence.DOWN);
            check(events.get(13).action == BackGestureSequence.CANCEL);
            long previous = 1000;
            for (Event event : events) {
                check(event.down == 1000 && event.time >= previous && event.y == 320f);
                previous = event.time;
                check(event.action != BackGestureSequence.UP);
            }
            check(events.get(1).time - 1000 == 16);
            check(events.get(12).time - 1000 == 192);
            clock.time += 100;
            touch.hold(720, 1280);
            long nextDown = events.get(14).down;
            check(nextDown > 1000);
            touch.commit();
            check(!touch.isHeld());
            check(events.get(events.size() - 1).action == BackGestureSequence.UP);
            check(events.stream().filter(e -> e.action == BackGestureSequence.UP).count() == 1);
            for (Event event : events.subList(14, events.size())) {
                check(event.down == nextDown && event.y == 640f);
            }
        }
    }
    private static void closeCancelsOnlyHeldTouch() throws IOException {
        Clock clock = new Clock();
        List<Event> events = new ArrayList<>();
        BackGestureSequence touch = sequence(clock, events);
        touch.close();
        check(events.isEmpty());
        touch.hold(640, 320);
        touch.close();
        touch.close();
        check(events.size() == 14 && events.get(13).action == BackGestureSequence.CANCEL);
    }
    private static void failedInjectionIsNotSuccess() throws IOException {
        Clock clock = new Clock();
        List<Event> events = new ArrayList<>();
        BackGestureSequence touch = new BackGestureSequence(clock, (down, time, action, x, y) -> {
            events.add(new Event(down, time, action, x, y));
            return action != BackGestureSequence.MOVE;
        });
        rejected(() -> touch.hold(320, 640));
        check(touch.isHeld());
        touch.close();
        check(events.size() == 3 && events.get(2).action == BackGestureSequence.CANCEL);
        check(events.stream().allMatch(e -> e.down == 1000));
    }
    private static void failedTerminalEventKeepsCleanupState() throws IOException {
        Clock clock = new Clock();
        List<Event> events = new ArrayList<>();
        BackGestureSequence touch = new BackGestureSequence(clock, (down, time, action, x, y) -> {
            events.add(new Event(down, time, action, x, y));
            return action != BackGestureSequence.UP;
        });
        touch.hold(320, 640);
        rejected(touch::commit);
        check(touch.isHeld());
        touch.close();
        check(events.get(events.size() - 1).action == BackGestureSequence.CANCEL);
    }
    private static void invalidGeometryAndClock() throws IOException {
        Clock clock = new Clock();
        List<Event> events = new ArrayList<>();
        BackGestureSequence touch = sequence(clock, events);
        for (int width : new int[] {-1, 0, 127, 8193}) {
            rejected(() -> touch.hold(width, 640));
        }
        rejected(() -> touch.hold(320, 0));
        rejected(touch::cancel);
        rejected(touch::commit);
        check(events.isEmpty());
        touch.hold(320, 640);
        clock.time = 1;
        rejected(touch::cancel);
        check(events.size() == 13 && touch.isHeld());
        clock.time = 2000;
        touch.close();
    }
    private static void lateStartKeepsBoundedContinuousMovement() throws IOException {
        Clock clock = new Clock();
        List<Event> events = new ArrayList<>();
        try (BackGestureSequence touch = sequence(clock, events)) {
            touch.hold(320, 640);
            for (int index = 0; index < 16; index++) touch.advance();
            rejected(touch::advance);
            check(events.size() == 29);
            check(events.get(28).x <= 320f * .55f);
            check(events.stream().allMatch(e -> e.down == 1000));
            check(events.stream().filter(e -> e.action == BackGestureSequence.DOWN).count() == 1);
            touch.cancel();
        }
    }

    public static void main(String[] args) throws IOException {
        lateStartKeepsBoundedContinuousMovement();
        cancelAndCommit();
        closeCancelsOnlyHeldTouch();
        failedInjectionIsNotSuccess();
        failedTerminalEventKeepsCleanupState();
        invalidGeometryAndClock();
        System.out.println("BACK_SEQUENCE_CASES=6");
    }
}
