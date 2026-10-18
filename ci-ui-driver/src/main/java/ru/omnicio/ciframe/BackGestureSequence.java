package ru.omnicio.ciframe;

import java.io.IOException;

/** One continuous test touch stream. No app callback, shell process, or synthetic progress. */
final class BackGestureSequence implements AutoCloseable {
    static final int DOWN = 0;
    static final int UP = 1;
    static final int MOVE = 2;
    static final int CANCEL = 3;
    private static final int STEPS = 12;
    private static final long STEP_MS = 16;

    interface Clock {
        long now();
        void pause(long millis);
    }

    interface Sink {
        boolean inject(long downTime, long eventTime, int action, float x, float y)
                throws IOException;
    }

    private final Clock clock;
    private final Sink sink;
    private long downTime = -1;
    private long lastTime;
    private float x;
    private float y;
    private int width;
    private int advances;

    BackGestureSequence(Clock clock, Sink sink) {
        this.clock = clock;
        this.sink = sink;
    }

    boolean isHeld() {
        return downTime >= 0;
    }

    void hold(int displayWidth, int displayHeight) throws IOException {
        if (isHeld()) {
            throw new IOException("A Back touch is already held");
        }
        if (displayWidth < 128 || displayWidth > 8192
                || displayHeight < 128 || displayHeight > 8192) {
            throw new IOException("Invalid measured Back display bounds");
        }
        width = displayWidth;
        advances = 0;
        x = 1f;
        y = displayHeight / 2f;
        downTime = clock.now();
        lastTime = downTime;
        if (downTime < 0) {
            throw new IOException("Invalid touch clock");
        }
        // Keep the same downTime and pointer until CANCEL or UP. Generate MOVE
        // events in this process, without shell startup delays between samples.
        emit(DOWN);
        moveTo(width * .3f);
    }

    void advance() throws IOException {
        requireHeld();
        if (advances >= 16) {
            throw new IOException("Back touch reached its bounded advance limit");
        }
        advances++;
        clock.pause(STEP_MS);
        x = width * (.3f + advances * .015f);
        emit(MOVE);
    }

    void cancel() throws IOException {
        requireHeld();
        emit(CANCEL);
        downTime = -1;
    }

    void commit() throws IOException {
        requireHeld();
        moveTo(width * .75f);
        emit(UP);
        downTime = -1;
    }

    private void requireHeld() throws IOException {
        if (!isHeld()) {
            throw new IOException("No Back touch is held");
        }
    }

    private void moveTo(float target) throws IOException {
        float start = x;
        for (int index = 1; index <= STEPS; index++) {
            clock.pause(STEP_MS);
            x = start + (target - start) * index / STEPS;
            emit(MOVE);
        }
    }

    private void emit(int action) throws IOException {
        long eventTime = clock.now();
        if (eventTime < lastTime) {
            throw new IOException("Touch clock moved backwards");
        }
        lastTime = eventTime;
        if (!sink.inject(downTime, eventTime, action, x, y)) {
            throw new IOException("Android rejected the Back touch event");
        }
    }

    @Override
    public void close() throws IOException {
        if (isHeld()) {
            cancel();
        }
    }
}
