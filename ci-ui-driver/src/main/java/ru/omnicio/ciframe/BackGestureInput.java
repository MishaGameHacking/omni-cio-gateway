package ru.omnicio.ciframe;

import android.app.UiAutomation;
import android.graphics.Rect;
import android.os.SystemClock;
import android.view.InputDevice;
import android.view.MotionEvent;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.io.IOException;

/** Test-only bounded edge gesture on the spatial or exact ready navigation fixtures. */
final class BackGestureInput implements AutoCloseable {
    static final int REQUEST_FLAG = 0x40000000;
    private static final String APP_PACKAGE = "ru.omnicio.app.debug";
    private final UiAutomation automation;
    private final WindowManager windows;
    private final BackGestureSequence sequence;
    private Rect display;

    BackGestureInput(UiAutomation automation, WindowManager windows) {
        this.automation = automation;
        this.windows = windows;
        sequence = new BackGestureSequence(new BackGestureSequence.Clock() {
            @Override public long now() { return SystemClock.uptimeMillis(); }
            @Override public void pause(long millis) { SystemClock.sleep(millis); }
        }, this::inject);
    }

    boolean isHeld() {
        return sequence.isHeld();
    }

    void perform(int operation, AccessibilityNodeInfo root) throws IOException {
        if (operation == 2) {
            // Cancellation must work even after focus loss or a failed frame.
            sequence.cancel();
            return;
        }
        if (operation != 1 && operation != 3 && operation != 4) {
            throw new IOException("Unknown Back gesture operation");
        }
        requireFixture(root);
        Rect current = windows.getMaximumWindowMetrics().getBounds();
        if (operation == 1) {
            if (current.left != 0 || current.top != 0) {
                throw new IOException("Back gesture requires the default display origin");
            }
            display = new Rect(current);
            sequence.hold(display.width(), display.height());
        } else {
            if (!current.equals(display)) {
                throw new IOException("Display changed during held Back touch");
            }
            if (operation == 3) sequence.commit();
            else sequence.advance();
        }
    }

    private void requireFixture(AccessibilityNodeInfo root) throws IOException {
        if (root == null || !APP_PACKAGE.contentEquals(root.getPackageName())) {
            throw new IOException("Back gesture root is not the Analyst AI app");
        }
        AccessibilityWindowInfo window = root.getWindow();
        if (window == null || !window.isActive() || !window.isFocused()
                || window.getType() != AccessibilityWindowInfo.TYPE_APPLICATION) {
            throw new IOException("Back gesture requires the focused app window");
        }
        if (!hasSpatialMarker(root, 0, new int[] {0}) && !hasAutomationNavigationMenu(root)) {
            throw new IOException("Back gestures are restricted to the reviewed synthetic fixtures");
        }
    }

    private static boolean hasSpatialMarker(AccessibilityNodeInfo node, int depth, int[] count)
            throws IOException {
        if (depth > 100 || ++count[0] > 5000) {
            throw new IOException("Back fixture search exceeds node budget");
        }
        if (!node.isVisibleToUser() || !APP_PACKAGE.contentEquals(node.getPackageName())) {
            return false;
        }
        CharSequence description = node.getContentDescription();
        if (description != null) {
            for (String part : description.toString().split(";")) {
                if ("probe-screen:spatial".equals(part)) {
                    return true;
                }
            }
        }
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            if (child != null && hasSpatialMarker(child, depth + 1, count)) {
                return true;
            }
        }
        return false;
    }

    private boolean hasAutomationNavigationMenu(AccessibilityNodeInfo root) throws IOException {
        NavigationBackFixture gate = new NavigationBackFixture();
        observeNavigationFixture(root, gate, windows.getMaximumWindowMetrics().getBounds(), 0, new int[] {0});
        return gate.allowed();
    }

    private static void observeNavigationFixture(AccessibilityNodeInfo node, NavigationBackFixture gate,
            Rect display, int depth, int[] count) throws IOException {
        if (depth > 100 || ++count[0] > 5000) {
            throw new IOException("Navigation Back fixture search exceeds node budget");
        }
        if (!node.isVisibleToUser() || !APP_PACKAGE.contentEquals(node.getPackageName())) return;
        gate.observeDescription(node.getContentDescription());
        if (node.isEnabled()) {
            Rect bounds = new Rect();
            node.getBoundsInScreen(bounds);
            if (bounds.intersect(display) && !bounds.isEmpty()) {
                String resource = node.getViewIdResourceName();
                String prefix = APP_PACKAGE + ":id/";
                if (resource != null && resource.startsWith(prefix)) resource = resource.substring(prefix.length());
                gate.observeVisibleResource(resource);
            }
        }
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            if (child != null) observeNavigationFixture(child, gate, display, depth + 1, count);
        }
    }

    private boolean inject(long downTime, long eventTime, int action, float x, float y) {
        MotionEvent.PointerProperties pointer = new MotionEvent.PointerProperties();
        pointer.id = 0;
        pointer.toolType = MotionEvent.TOOL_TYPE_FINGER;
        MotionEvent.PointerCoords position = new MotionEvent.PointerCoords();
        position.x = x;
        position.y = y;
        position.pressure = action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL
                ? 0f : 1f;
        position.size = 1f;
        MotionEvent event = MotionEvent.obtain(downTime, eventTime, action, 1,
                new MotionEvent.PointerProperties[] {pointer},
                new MotionEvent.PointerCoords[] {position},
                0, 0, 1f, 1f, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
        try {
            // UiAutomation's public overload routes an unspecified pointer display
            // to DEFAULT_DISPLAY. Never invoke the app's Back callback directly.
            return automation.injectInputEvent(event, true);
        } finally {
            event.recycle();
        }
    }

    @Override
    public void close() throws IOException {
        sequence.close();
    }
}
