package ru.omnicio.ciframe;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.Instrumentation;
import android.app.UiAutomation;
import android.graphics.Rect;
import android.hardware.display.DisplayManager;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.util.Xml;
import android.view.Display;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;
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
 * It reads fresh frames and performs only exact whitelisted list scroll actions.
 */
public final class FrameInstrumentation extends Instrumentation {
    private static final int MAX_BYTES = 2 * 1024 * 1024;
    private static final String APP_PACKAGE = "ru.omnicio.app.debug";
    private static final int ACTION_FLAG = 0x80000000;
    private static final int ACTION_START_FLAG = 0x10000000;
    private static final int ACTION_LIST_SHIFT = 24;
    private static final int ACTION_LIST_MASK = 0x0f;
    private static final int REQUEST_SEQUENCE_MASK = 0x00ffffff;
    private static final int ALLOWED_REQUEST_BITS = ACTION_FLAG
            | ACTION_START_FLAG
            | (ACTION_LIST_MASK << ACTION_LIST_SHIFT)
            | REQUEST_SEQUENCE_MASK;
    private static final int LIST_PROFILE = 1;
    private static final int LIST_EDUCATION = 2;
    private static final int LIST_PORTFOLIO = 3;
    private static final int LIST_PROFILE_TABS = 4;
    private static final int LIST_WORKSPACE = 5;
    private static final String PROFILE_LIST = "profile-content";
    private static final String EDUCATION_LIST = "education-content";
    private static final String PORTFOLIO_LIST = "portfolio-content";
    private static final String PROFILE_TABS = "profile-tabs";
    private static final String WORKSPACE_LIST = "workspace-content";

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
        int previous = 0;
        while (true) {
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
            if (actionRequest) {
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
                byte[] frame = root == null ? new byte[0] : encodeTree(root);
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

    private byte[] encodeTree(AccessibilityNodeInfo root) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        XmlSerializer xml = Xml.newSerializer();
        xml.setOutput(new BoundedOutput(bytes), "UTF-8");
        xml.startDocument("UTF-8", true);
        xml.startTag(null, "hierarchy");
        Rect display = windows.getMaximumWindowMetrics().getBounds();
        writeNode(xml, root, display, 0, new int[] {0});
        xml.endTag(null, "hierarchy");
        xml.endDocument();
        if (bytes.size() > MAX_BYTES) {
            throw new IOException("Accessibility tree exceeds byte budget");
        }
        return bytes.toByteArray();
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
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            if (child != null && child.isVisibleToUser()) {
                writeNode(xml, child, display, depth + 1, count);
            }
        }
        xml.endTag(null, "node");
    }

    @SuppressWarnings("deprecation")
    private static boolean checkedState(AccessibilityNodeInfo node) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.BAKLAVA) {
            return node.getChecked() == AccessibilityNodeInfo.CHECKED_STATE_TRUE;
        }
        // Public API35 contract; getChecked() only exists from API36.
        return node.isChecked();
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

