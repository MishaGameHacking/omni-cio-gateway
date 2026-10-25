package android.view.accessibility;
import android.graphics.Rect;
import java.util.ArrayList;
import java.util.List;
/** Observations and action spy only: no implementation of native scrolling. */
public class AccessibilityNodeInfo {
    public String packageName="ru.omnicio.app.debug", id="";
    public boolean visible=true, enabled=true, scrollable=false, performed=true;
    public int actionsPerformed=0;
    public AccessibilityWindowInfo window=new AccessibilityWindowInfo();
    public Rect bounds=new Rect(0,0,320,640);
    public final List<AccessibilityNodeInfo> children=new ArrayList<>();
    public final List<AccessibilityAction> actions=new ArrayList<>(List.of(AccessibilityAction.ACTION_SHOW_ON_SCREEN));
    public CharSequence getPackageName() { return packageName; }
    public String getViewIdResourceName() { return id; }
    public boolean isVisibleToUser() { return visible; }
    public boolean isEnabled() { return enabled; }
    public boolean isScrollable() { return scrollable; }
    public AccessibilityWindowInfo getWindow() { return window; }
    public List<AccessibilityAction> getActionList() { return actions; }
    public int getChildCount() { return children.size(); }
    public AccessibilityNodeInfo getChild(int i) { return children.get(i); }
    public void getBoundsInScreen(Rect r) {
        r.left=bounds.left;r.top=bounds.top;r.right=bounds.right;r.bottom=bounds.bottom;
    }
    public boolean performAction(int id) {
        if(id!=AccessibilityAction.ACTION_SHOW_ON_SCREEN.getId())throw new AssertionError("Wrong action");
        actionsPerformed++;return performed;
    }
    public static class AccessibilityAction {
        public static final AccessibilityAction ACTION_SHOW_ON_SCREEN=new AccessibilityAction();
        public int getId() { return 16908342; }
    }
}
