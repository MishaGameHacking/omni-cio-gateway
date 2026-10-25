package ru.omnicio.ciframe;

import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** Test-only public minimal scroll; never a click or an application-state mutation. */
final class NodeRevealAction {
    static final int REQUEST_FLAG = 0x20000000;
    private static final String APP_PACKAGE = "ru.omnicio.app.debug";

    private NodeRevealAction() {}

    static String readTarget(DataInputStream input) throws IOException {
        int length = input.readUnsignedShort();
        if (length < 1 || length > 96) {
            throw new IOException("Native reveal target exceeds byte budget");
        }
        byte[] bytes = new byte[length];
        input.readFully(bytes);
        String target = new String(bytes, StandardCharsets.US_ASCII);
        if (!target.matches("[a-z][a-z0-9-]{0,95}")) {
            throw new IOException("Invalid native reveal resource id");
        }
        return target;
    }

    static boolean perform(AccessibilityNodeInfo root, String listId, String targetId,
            Rect display) throws IOException {
        if (listId == null || root == null || !APP_PACKAGE.contentEquals(root.getPackageName())) {
            throw new IOException("Native reveal requires an exact Analyst AI list");
        }
        AccessibilityWindowInfo window = root.getWindow();
        if (window == null || !window.isActive() || !window.isFocused()
                || window.getType() != AccessibilityWindowInfo.TYPE_APPLICATION) {
            throw new IOException("Native reveal requires the focused app window");
        }
        List<AccessibilityNodeInfo> lists = new ArrayList<>();
        find(root, listId, true, lists, 0, new int[] {0});
        if (lists.size() != 1) {
            throw new IOException("Native reveal list is absent or ambiguous");
        }
        AccessibilityNodeInfo list = lists.get(0);
        Rect viewport = new Rect();
        list.getBoundsInScreen(viewport);
        if (!viewport.intersect(display) || viewport.isEmpty()) {
            throw new IOException("Native reveal list is outside the display");
        }
        List<AccessibilityNodeInfo> targets = new ArrayList<>();
        find(list, targetId, false, targets, 0, new int[] {0});
        if (targets.size() != 1 || targets.get(0).equals(list)) {
            throw new IOException("Native reveal needs one visible enabled descendant");
        }
        AccessibilityNodeInfo target = targets.get(0);
        Rect bounds = new Rect();
        target.getBoundsInScreen(bounds);
        if (!bounds.intersect(viewport) || bounds.isEmpty()) {
            throw new IOException("Native reveal target does not intersect its list");
        }
        AccessibilityNodeInfo.AccessibilityAction action =
                AccessibilityNodeInfo.AccessibilityAction.ACTION_SHOW_ON_SCREEN;
        // Standard native handlers need not enumerate this action in metadata.
        // Its result and the next fresh geometry remain independent requirements.
        return target.performAction(action.getId());
    }

    private static void find(AccessibilityNodeInfo node, String resourceId,
            boolean scrollable, List<AccessibilityNodeInfo> matches,
            int depth, int[] count) throws IOException {
        if (depth > 100 || ++count[0] > 5000) {
            throw new IOException("Native reveal search exceeds node budget");
        }
        if (!APP_PACKAGE.contentEquals(node.getPackageName()) || !node.isVisibleToUser()) {
            return;
        }
        String id = node.getViewIdResourceName();
        boolean exact = resourceId.equals(id) || (APP_PACKAGE + ":id/" + resourceId).equals(id);
        if (exact && node.isEnabled() && (!scrollable || node.isScrollable())) {
            matches.add(node);
        }
        for (int index = 0; index < node.getChildCount(); index++) {
            AccessibilityNodeInfo child = node.getChild(index);
            if (child != null) find(child, resourceId, scrollable, matches, depth + 1, count);
        }
    }
}
