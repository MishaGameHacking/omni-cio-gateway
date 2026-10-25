package android.view.accessibility;
public class AccessibilityWindowInfo {
    public static final int TYPE_APPLICATION=1;
    public boolean active=true, focused=true;
    public int type=TYPE_APPLICATION;
    public boolean isActive() { return active; }
    public boolean isFocused() { return focused; }
    public int getType() { return type; }
}
