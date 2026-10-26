package ru.omnicio.ciframe;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.Instrumentation;
import android.app.UiAutomation;
import android.graphics.Rect;
import android.hardware.display.DisplayManager;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.util.Xml;
import android.view.Display;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FilterOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import org.xmlpull.v1.XmlSerializer;

/**
 * One public UiAutomation connection for the whole disposable-emulator scenario.
 * A separate test-only package survives force-stop/restart of the app under test.
 * It reads fresh frames, scrolls exact lists and injects fixture-only Back gestures.
 */
public final class FrameInstrumentation extends Instrumentation {
    private static final int MAX_BYTES = 2 * 1024 * 1024;
    private static final int MAX_IME_WINDOWS = 8;
    private static final String APP_PACKAGE = "ru.omnicio.app.debug";
    private static final int ACTION_FLAG = 0x80000000;
    private static final int ACTION_START_FLAG = 0x10000000;
    private static final int ACTION_LIST_SHIFT = 24;
    private static final int ACTION_LIST_MASK = 0x0f;
    private static final int REQUEST_SEQUENCE_MASK = 0x00ffffff;
    private static final int ALLOWED_REQUEST_BITS = ACTION_FLAG
            | BackGestureInput.REQUEST_FLAG
            | NodeRevealAction.REQUEST_FLAG
            | ACTION_START_FLAG
            | (ACTION_LIST_MASK << ACTION_LIST_SHIFT)
            | REQUEST_SEQUENCE_MASK;
    private static final int LIST_PROFILE = 1;
    private static final int LIST_EDUCATION = 2;
    private static final int LIST_PORTFOLIO = 3;
    private static final int LIST_PROFILE_TABS = 4;
    private static final int LIST_WORKSPACE = 5;
    private static final int LIST_DOSSIER_TABS = 6;
    private static final int LIST_QUOTES_INTERVALS = 7;
    private static final int LIST_ASSISTANT_COMPOSER = 8;
    private static final int LIST_NAVIGATION_PANEL = 9;
    private static final String PROFILE_LIST = "profile-content";
    private static final String EDUCATION_LIST = "education-content";
    private static final String PORTFOLIO_LIST = "portfolio-content";
    private static final String PROFILE_TABS = "profile-tabs";
    private static final String WORKSPACE_LIST = "workspace-content";
    private static final String DOSSIER_TABS = "dossier-tabs";
    private static final String QUOTES_INTERVALS = "quotes-intervals";
    private static final String ASSISTANT_COMPOSER = "assistant-composer";
    private static final String NAVIGATION_PANEL = "navigation-panel-content";

    private String socketName;
    private byte[] token;
    private WindowManager windows;

    @Override
    public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        String session = arguments.getString("session", "");
        String secret = arguments.getString("token", "");
        if (!session.matches("[a-f0-9]{32}") || !secret.matches("[a-f0-9]{64}")) {
            finish(1, new Bundle());
            return;
        }
        socketName = "analyst-ci-frame-" + session;
        token = secret.getBytes(StandardCharsets.US_ASCII);
        start();
    }

    @Override
    public void onStart() {
        Bundle result = new Bundle();
        int code = 1;
        try (LocalServerSocket server = new LocalServerSocket(socketName)) {
            UiAutomation automation = getUiAutomation(
                    UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES);
            if (automation == null) {
                throw new IOException("UiAutomation did not connect");
            }
            AccessibilityServiceInfo info = automation.getServiceInfo();
            info.flags |= AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                    | AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                    | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS;
            automation.setServiceInfo(info);
            Display screen = getContext().getSystemService(DisplayManager.class)
                    .getDisplay(Display.DEFAULT_DISPLAY);
            if (screen == null) {
                throw new IOException("Default display is unavailable");
            }
            windows = getContext().createWindowContext(
                    screen,
                    WindowManager.LayoutParams.TYPE_APPLICATION,
                    null)
                    .getSystemService(WindowManager.class);
            try (LocalSocket client = server.accept()) {
                client.setSoTimeout(120_000);
                serve(client, automation);
            }
            code = 0;
        } catch (IOException | RuntimeException error) {
            Log.e("AnalystCiFrames", "Persistent frame session failed", error);
            result.putString(
                    "frame_error",
                    error.getClass().getSimpleName() + ": " + error.getMessage());
        } finally {
            // Instrumentation owns disconnect; no hidden API or new session per frame.
            finish(code, result);
        }
    }

    private void serve(LocalSocket client, UiAutomation automation) throws IOException {
        DataInputStream input = new DataInputStream(client.getInputStream());
        DataOutputStream output = new DataOutputStream(client.getOutputStream());
        byte[] supplied = new byte[64];
        input.readFully(supplied);
        if (!MessageDigest.isEqual(token, supplied)) {
            throw new IOException("Session authentication failed");
        }
        output.writeInt(2);
        output.flush();
        try (BackGestureInput gesture = new BackGestureInput(automation, windows)) {
            serveRequests(client, input, output, automation, gesture);
        }
    }

    private void serveRequests(LocalSocket client, DataInputStream input, DataOutputStream output,
            UiAutomation automation, BackGestureInput gesture) throws IOException {
        int previous = 0;
        while (true) {
            client.setSoTimeout(gesture.isHeld() ? 20_000 : 120_000);
            int rawRequest = input.readInt();
            if (rawRequest == 0) {
                return;
            }
            if ((rawRequest & ~ALLOWED_REQUEST_BITS) != 0) {
                throw new IOException("Unknown request flags");
            }
            int request = rawRequest & REQUEST_SEQUENCE_MASK;
            if (request <= previous) {
                throw new IOException("Non-monotonic frame request");
            }
            previous = request;
            if (!automation.clearCache()) {
                throw new IOException("Could not invalidate accessibility cache");
            }
            AccessibilityNodeInfo root = automation.getRootInActiveWindow();
            boolean actionRequest = (rawRequest & ACTION_FLAG) != 0;
            boolean backRequest = (rawRequest & BackGestureInput.REQUEST_FLAG) != 0;
            boolean revealRequest = (rawRequest & NodeRevealAction.REQUEST_FLAG) != 0;
            if (backRequest) {
                if (actionRequest || revealRequest || (rawRequest & ACTION_START_FLAG) != 0) {
                    throw new IOException("Back request contains unrelated action flags");
                }
                gesture.perform((rawRequest >>> ACTION_LIST_SHIFT) & ACTION_LIST_MASK, root);
                output.writeInt(request);
                output.writeInt(4);
                output.writeInt(0);
                output.flush();
            } else if (revealRequest) {
                if (actionRequest || (rawRequest & ACTION_START_FLAG) != 0 || gesture.isHeld()) {
                    throw new IOException("Native reveal contains unrelated flags or held touch");
                }
                client.setSoTimeout(12_000);
                String targetId = NodeRevealAction.readTarget(input);
                int listCode = (rawRequest >>> ACTION_LIST_SHIFT) & ACTION_LIST_MASK;
                boolean performed = NodeRevealAction.perform(root, listResourceId(listCode),
                        targetId, windows.getMaximumWindowMetrics().getBounds());
                output.writeInt(request);
                output.writeInt(performed ? 5 : 6);
                output.writeInt(0);
                output.flush();
            } else if (actionRequest) {
                if (gesture.isHeld()) {
                    throw new IOException("Cannot scroll during a held Back touch");
                }
                int listCode = (rawRequest >>> ACTION_LIST_SHIFT) & ACTION_LIST_MASK;
                boolean towardStart = (rawRequest & ACTION_START_FLAG) != 0;
                boolean performed = scrollExactList(root, listCode, towardStart);
                output.writeInt(request);
                // A semantic boundary is an acknowledged, non-performed action,
                // not a broken transport. The caller still has to read a fresh
                // frame and prove that the target is visible or fail normally.
                output.writeInt(performed ? 2 : 3);
                output.writeInt(0);
                output.flush();
            } else {
                if ((rawRequest & ~REQUEST_SEQUENCE_MASK) != 0) {
                    throw new IOException("Frame request contains action flags");
                }
                byte[] frame = root == null ? new byte[0] : encodeTree(root, automation);
                output.writeInt(request);
                output.writeInt(root == null ? 0 : 1);
                output.writeInt(frame.length);
                output.write(frame);
                output.flush();
            }
        }
    }

    private boolean scrollExactList(
            AccessibilityNodeInfo root,
            int listCode,
            boolean towardStart) throws IOException {
        String resourceId = listResourceId(listCode);
        if (resourceId == null) {
            throw new IOException("Unknown semantic scroll list");
        }
        if (root == null || !APP_PACKAGE.contentEquals(root.getPackageName())) {
            throw new IOException("Semantic scroll root is not the Analyst AI app");
        }
        List<AccessibilityNodeInfo> matches = new ArrayList<>();
        findList(root, resourceId, matches, 0, new int[] {0});
        if (matches.size() != 1) {
            throw new IOException("Expected one exact visible app list");
        }
        AccessibilityNodeInfo list = matches.get(0);
        Rect bounds = new Rect();
        list.getBoundsInScreen(bounds);
        if (!bounds.intersect(windows.getMaximumWindowMetrics().getBounds())
                || bounds.isEmpty()) {
            throw new IOException("Semantic scroll list is outside the app window");
        }
        AccessibilityNodeInfo.AccessibilityAction action = towardStart
                ? AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_BACKWARD
                : AccessibilityNodeInfo.AccessibilityAction.ACTION_SCROLL_FORWARD;
        if (!list.getActionList().contains(action)) {
            return false;
        }
        // Dispatch through the actual Compose accessibility action. This never
        // injects a coordinate drag over a clickable card. False is a normal
        // boundary result; the next fresh frame determines whether the target
        // is already safely visible.
        return list.performAction(action.getId());
    }

    private static String listResourceId(int listCode) {
        return switch (listCode) {
            case LIST_PROFILE -> PROFILE_LIST;
            case LIST_EDUCATION -> EDUCATION_LIST;
            case LIST_PORTFOLIO -> PORTFOLIO_LIST;
            case LIST_PROFILE_TABS -> PROFILE_TABS;
            case LIST_WORKSPACE -> WORKSPACE_LIST;
            case LIST_DOSSIER_TABS -> DOSSIER_TABS;
            case LIST_QUOTES_INTERVALS -> QUOTES_INTERVALS;
            case LIST_ASSISTANT_COMPOSER -> ASSISTANT_COMPOSER;
            case LIST_NAVIGATION_PANEL -> NAVIGATION_PANEL;
            default -> null;
        };
    }

    private static void findList(
            AccessibilityNodeInfo node,
            String resourceId,
            List<AccessibilityNodeInfo> matches,
            int depth,
            int[] count) throws IOException {
        if (depth > 100 || ++count[0] > 5000) {
            throw new IOException("Scroll search exceeds node budget");
        }
        String id = node.getViewIdResourceName();
        boolean exactId = resourceId.equals(id)
                || (APP_PACKAGE + ":id/" + resourceId).equals(id);
        if (exactId
                && APP_PACKAGE.contentEquals(node.getPackageName())
                && node.isVisibleToUser()
                && node.isEnabled()
                && node.isScrollable()) {
            matches.add(node);
        }
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            if (child != null && child.isVisibleToUser()) {
                findList(child, resourceId, matches, depth + 1, count);
            }
        }
    }

    private byte[] encodeTree(AccessibilityNodeInfo root, UiAutomation automation) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        XmlSerializer xml = Xml.newSerializer();
        xml.setOutput(new BoundedOutput(bytes), "UTF-8");
        xml.startDocument("UTF-8", true);
        xml.startTag(null, "hierarchy");
        Rect display = windows.getMaximumWindowMetrics().getBounds();
        long observationStart = SystemClock.elapsedRealtime();
        WindowObservation observation = observeWindows(automation.getWindows(), display, root.getWindowId());
        long observationEnd = SystemClock.elapsedRealtime();
        attr(xml, "display-width", Integer.toString(display.width()));
        attr(xml, "display-height", Integer.toString(display.height()));
        attr(xml, "display-bounds", display.flattenToString());
        attr(xml, "display-id", Integer.toString(Display.DEFAULT_DISPLAY));
        attr(xml, "active-window-id", Integer.toString(root.getWindowId()));
        attr(xml, "keyboard-visible", Boolean.toString(observation.keyboardVisible()));
        attr(xml, "window-observation-start-ms", Long.toString(observationStart));
        attr(xml, "window-observation-end-ms", Long.toString(observationEnd));
        attr(xml, "interactive-window-count", Integer.toString(observation.windowCount()));
        attr(xml, "root-window-present", Boolean.toString(observation.rootPresent()));
        attr(xml, "root-window-focused", Boolean.toString(observation.rootFocused()));
        attr(xml, "ime-window-count", Integer.toString(observation.imeCount()));
        attr(xml, "ime-windows-truncated", Boolean.toString(observation.imeCount() > MAX_IME_WINDOWS));
        attr(xml, "ime-windows", observation.imeWindows());
        writeNode(xml, root, display, 0, new int[] {0});
        xml.endTag(null, "hierarchy");
        xml.endDocument();
        if (bytes.size() > MAX_BYTES) {
            throw new IOException("Accessibility tree exceeds byte budget");
        }
        return bytes.toByteArray();
    }

    private record WindowObservation(boolean keyboardVisible, int windowCount, int imeCount,
            boolean rootPresent, boolean rootFocused, String imeWindows) {}

    private static WindowObservation observeWindows(
            List<AccessibilityWindowInfo> windows, Rect display, int rootWindowId) {
        boolean visible = false;
        boolean rootPresent = false;
        boolean rootFocused = false;
        int count = 0;
        StringBuilder metadata = new StringBuilder("[");
        for (AccessibilityWindowInfo window : windows) {
            if (window.getId() == rootWindowId) {
                rootPresent = true;
                rootFocused = window.isFocused();
            }
            if (window.getType() == AccessibilityWindowInfo.TYPE_INPUT_METHOD) {
                Rect bounds = new Rect();
                window.getBoundsInScreen(bounds);
                boolean intersects = !bounds.isEmpty() && Rect.intersects(bounds, display);
                // Preserve the original visibility predicate, including windows
                // beyond the diagnostic cap. Metadata never controls readiness.
                visible |= intersects;
                if (count < MAX_IME_WINDOWS) {
                    if (count != 0) metadata.append(',');
                    // Numeric/boolean fields only: never titles, text or extras.
                    metadata.append('[').append(window.getId()).append(',')
                            .append(window.getDisplayId()).append(',').append(window.getType()).append(',')
                            .append(bounds.left).append(',').append(bounds.top).append(',')
                            .append(bounds.right).append(',').append(bounds.bottom).append(',')
                            .append(window.isActive()).append(',').append(window.isFocused()).append(',')
                            .append(intersects).append(']');
                }
                count++;
            }
        }
        return new WindowObservation(visible, windows.size(), count, rootPresent,
                rootFocused, metadata.append(']').toString());
    }

    private static void writeNode(
            XmlSerializer xml,
            AccessibilityNodeInfo node,
            Rect display,
            int depth,
            int[] count) throws IOException {
        if (depth > 100 || ++count[0] > 5000) {
            throw new IOException("Accessibility tree exceeds node budget");
        }
        Rect bounds = new Rect();
        node.getBoundsInScreen(bounds);
        if (!bounds.intersect(display)) {
            bounds.setEmpty();
        }
        xml.startTag(null, "node");
        attr(xml, "package", node.getPackageName());
        attr(xml, "class", node.getClassName());
        attr(xml, "resource-id", node.getViewIdResourceName());
        attr(xml, "text", node.getText());
        attr(xml, "content-desc", node.getContentDescription());
        attr(xml, "state-description", node.getStateDescription());
        attr(
                xml,
                "bounds",
                "[" + bounds.left + "," + bounds.top + "]["
                        + bounds.right + "," + bounds.bottom + "]");
        attr(xml, "visible-to-user", Boolean.toString(node.isVisibleToUser()));
        attr(xml, "clickable", Boolean.toString(node.isClickable()));
        attr(xml, "enabled", Boolean.toString(node.isEnabled()));
        attr(xml, "selected", Boolean.toString(node.isSelected()));
        attr(xml, "scrollable", Boolean.toString(node.isScrollable()));
        attr(
                xml,
                "checked",
                Boolean.toString(checkedState(node)));
        attr(xml, "checkable", Boolean.toString(node.isCheckable()));
        attr(xml, "focusable", Boolean.toString(node.isFocusable()));
        attr(xml, "focused", Boolean.toString(node.isFocused()));
        attr(xml, "accessibility-focused", Boolean.toString(node.isAccessibilityFocused()));
        attr(xml, "editable", Boolean.toString(node.isEditable()));
        attr(xml, "selection-start", Integer.toString(node.getTextSelectionStart()));
        attr(xml, "selection-end", Integer.toString(node.getTextSelectionEnd()));
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            if (child != null && child.isVisibleToUser()) {
                writeNode(xml, child, display, depth + 1, count);
            }
        }
        xml.endTag(null, "node");
    }

    private static boolean checkedState(AccessibilityNodeInfo node) {
        return node.getChecked() == AccessibilityNodeInfo.CHECKED_STATE_TRUE;
    }

    private static final class BoundedOutput extends FilterOutputStream {
        private int count;

        BoundedOutput(OutputStream output) {
            super(output);
        }

        @Override
        public void write(int value) throws IOException {
            reserve(1);
            out.write(value);
        }

        @Override
        public void write(byte[] data, int offset, int length) throws IOException {
            reserve(length);
            out.write(data, offset, length);
        }

        private void reserve(int length) throws IOException {
            if (length > MAX_BYTES - count) {
                throw new IOException("Accessibility tree exceeds byte budget");
            }
            count += length;
        }
    }

    private static void attr(XmlSerializer xml, String name, CharSequence value)
            throws IOException {
        // Preserve text exactly; XmlSerializer escapes markup. Invalid XML characters
        // fail the frame rather than silently altering a financial label or test target.
        String text = value == null ? "" : value.toString();
        if (text.length() > 32768) {
            throw new IOException("Accessibility attribute exceeds budget");
        }
        xml.attribute(null, name, text);
    }
}

