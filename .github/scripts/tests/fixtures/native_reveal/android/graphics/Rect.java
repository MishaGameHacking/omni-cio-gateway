package android.graphics;
/** Minimal geometry double for executing the real driver guard on the host. */
public class Rect {
    public int left, top, right, bottom;
    public Rect() {}
    public Rect(int l, int t, int r, int b) { left=l; top=t; right=r; bottom=b; }
    public boolean isEmpty() { return right<=left || bottom<=top; }
    public boolean intersect(Rect r) {
        int l=Math.max(left,r.left),t=Math.max(top,r.top);
        int rr=Math.min(right,r.right),b=Math.min(bottom,r.bottom);
        if (rr<=l || b<=t) return false;
        left=l;top=t;right=rr;bottom=b;return true;
    }
}
