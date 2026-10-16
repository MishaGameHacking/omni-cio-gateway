package ru.omnicio.ciframe;

import android.accessibilityservice.AccessibilityServiceInfo;
import android.app.Instrumentation;
import android.app.UiAutomation;
import android.graphics.Rect;
import android.hardware.display.DisplayManager;
import android.view.Display;
import android.net.LocalServerSocket;
import android.net.LocalSocket;
import android.os.Bundle;
import android.util.Xml;
import android.util.Log;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FilterOutputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.xmlpull.v1.XmlSerializer;

/** One public UiAutomation connection for the whole disposable-emulator scenario.
 * A separate test-only package survives force-stop/restart of the app under test.
 * The only operation exposed is reading a fresh accessibility tree, not commands.
 */
public final class FrameInstrumentation extends Instrumentation {
    private static final int MAX_BYTES = 2 * 1024 * 1024;
    private String socketName;
    private byte[] token;
    private WindowManager windows;

    @Override public void onCreate(Bundle arguments) {
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

    @Override public void onStart() {
        Bundle result = new Bundle();
        int code = 1;
        try (LocalServerSocket server = new LocalServerSocket(socketName)) {
            UiAutomation automation = getUiAutomation(UiAutomation.FLAG_DONT_SUPPRESS_ACCESSIBILITY_SERVICES);
            if (automation == null) throw new IOException("UiAutomation did not connect");
            AccessibilityServiceInfo info = automation.getServiceInfo();
            info.flags |= AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS
                    | AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS;
            automation.setServiceInfo(info);
            Display screen = getTargetContext().getSystemService(DisplayManager.class)
                    .getDisplay(Display.DEFAULT_DISPLAY);
            windows = getTargetContext().createWindowContext(
                    screen, WindowManager.LayoutParams.TYPE_APPLICATION, null)
                    .getSystemService(WindowManager.class);
            try (LocalSocket client = server.accept()) {
                client.setSoTimeout(120_000);
                serve(client, automation);
            }
            code = 0;
        } catch (IOException | RuntimeException error) {
            Log.e("AnalystCiFrames", "Persistent frame session failed", error);
            result.putString("frame_error", error.getClass().getSimpleName() + ": " + error.getMessage());
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
        if (!MessageDigest.isEqual(token, supplied)) throw new IOException("Session authentication failed");
        output.writeInt(1); // Protocol version, sent only after UiAutomation is connected.
        output.flush();
        int previous = 0;
        while (true) {
            int request = input.readInt();
            if (request == 0) return;
            if (request <= previous) throw new IOException("Non-monotonic frame request");
            previous = request;
            if (!automation.clearCache()) throw new IOException("Could not invalidate accessibility cache");
            AccessibilityNodeInfo root = automation.getRootInActiveWindow();
            byte[] frame = root == null ? new byte[0] : encodeTree(root);
            output.writeInt(request);
            output.writeInt(root == null ? 0 : 1);
            output.writeInt(frame.length);
            output.write(frame);
            output.flush();
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
        if (bytes.size() > MAX_BYTES) throw new IOException("Accessibility tree exceeds byte budget");
        return bytes.toByteArray();
    }

    private static void writeNode(XmlSerializer xml, AccessibilityNodeInfo node, Rect display,
            int depth, int[] count) throws IOException {
        if (depth > 100 || ++count[0] > 5000) throw new IOException("Accessibility tree exceeds node budget");
        Rect bounds = new Rect();
        node.getBoundsInScreen(bounds);
        if (!bounds.intersect(display)) bounds.setEmpty();
        xml.startTag(null, "node");
        attr(xml, "package", node.getPackageName());
        attr(xml, "class", node.getClassName());
        attr(xml, "resource-id", node.getViewIdResourceName());
        attr(xml, "text", node.getText());
        attr(xml, "content-desc", node.getContentDescription());
        attr(xml, "bounds", "[" + bounds.left + "," + bounds.top + "][" + bounds.right + "," + bounds.bottom + "]");
        attr(xml, "visible-to-user", Boolean.toString(node.isVisibleToUser()));
        attr(xml, "clickable", Boolean.toString(node.isClickable()));
        attr(xml, "enabled", Boolean.toString(node.isEnabled()));
        attr(xml, "selected", Boolean.toString(node.isSelected()));
        attr(xml, "scrollable", Boolean.toString(node.isScrollable()));
        attr(xml, "checked", Boolean.toString(node.isChecked()));
        attr(xml, "checkable", Boolean.toString(node.isCheckable()));
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            if (child != null && child.isVisibleToUser()) writeNode(xml, child, display, depth + 1, count);
        }
        xml.endTag(null, "node");
    }

    private static final class BoundedOutput extends FilterOutputStream {
        private int count;
        BoundedOutput(OutputStream output) { super(output); }
        @Override public void write(int value) throws IOException {
            reserve(1);
            out.write(value);
        }
        @Override public void write(byte[] data, int offset, int length) throws IOException {
            reserve(length);
            out.write(data, offset, length);
        }
        private void reserve(int length) throws IOException {
            if (length > MAX_BYTES - count) throw new IOException("Accessibility tree exceeds byte budget");
            count += length;
        }
    }

    private static void attr(XmlSerializer xml, String name, CharSequence value) throws IOException {
        // Preserve text exactly; XmlSerializer escapes markup. Invalid XML characters
        // fail the frame rather than silently altering a financial label or test target.
        String text = value == null ? "" : value.toString();
        if (text.length() > 32768) throw new IOException("Accessibility attribute exceeds budget");
        xml.attribute(null, name, text);
    }
}
