package ru.omnicio.ciframe;
import android.graphics.Rect;
import android.view.accessibility.AccessibilityNodeInfo;
import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.function.Consumer;

public final class NodeRevealActionTest {
    private static final String AREA="workspace-content", TARGET="assistant-impact-position";
    private static int cases=0;
    private static final class Scene {
        final AccessibilityNodeInfo root=new AccessibilityNodeInfo();
        final AccessibilityNodeInfo list=new AccessibilityNodeInfo();
        final AccessibilityNodeInfo target=new AccessibilityNodeInfo();
        Scene() {
            list.id=AREA;list.scrollable=true;list.bounds=new Rect(0,171,320,393);
            target.id=TARGET;target.bounds=new Rect(38,378,282,430);
            root.children.add(list);list.children.add(target);
        }
        boolean run() throws IOException {
            return NodeRevealAction.perform(root,AREA,TARGET,new Rect(0,0,320,640));
        }
    }
    private static void refused(Consumer<Scene> change) throws Exception {
        Scene scene=new Scene();change.accept(scene);
        try { scene.run(); throw new AssertionError("Invalid scene accepted"); }
        catch(IOException expected) {
            if(scene.target.actionsPerformed!=0)throw new AssertionError("Acted before validation");
        }
        cases++;
    }
    private static void invalidTarget(byte[] data) throws Exception {
        try {
            NodeRevealAction.readTarget(new DataInputStream(new ByteArrayInputStream(data)));
            throw new AssertionError("Invalid target accepted");
        } catch(IOException expected) { cases++; }
    }
    public static void main(String[] args) throws Exception {
        Scene valid=new Scene();
        if(!valid.run() || valid.target.actionsPerformed!=1)throw new AssertionError("Observed partial target rejected");
        cases++;
        Scene noMove=new Scene();noMove.target.performed=false;
        if(noMove.run())throw new AssertionError("False action became a pass");
        cases++;
        Scene qualified=new Scene();qualified.list.id="ru.omnicio.app.debug:id/"+AREA;
        qualified.target.id="ru.omnicio.app.debug:id/"+TARGET;
        if(!qualified.run())throw new AssertionError("Exact qualified names rejected");
        cases++;
        refused(s->s.root.packageName="foreign.app");
        refused(s->s.root.window=null);
        refused(s->s.root.window.active=false);
        refused(s->s.root.window.focused=false);
        refused(s->s.root.window.type=2);
        refused(s->s.list.scrollable=false);
        refused(s->s.list.enabled=false);
        refused(s->s.list.visible=false);
        refused(s->s.list.bounds=new Rect(400,0,500,600));
        refused(s->s.target.bounds=new Rect(38,400,282,452));
        refused(s->s.target.enabled=false);
        refused(s->s.target.visible=false);
        refused(s->s.target.packageName="foreign.app");
        refused(s->s.target.id=TARGET+"-other");
        Scene unlisted=new Scene();unlisted.target.actions.clear();
        if(!unlisted.run())throw new AssertionError("Supported unlisted standard action rejected");
        cases++;
        refused(s->{s.list.children.remove(s.target);s.root.children.add(s.target);});
        refused(s->{AccessibilityNodeInfo duplicate=new AccessibilityNodeInfo();duplicate.id=TARGET;
            duplicate.bounds=new Rect(38,330,282,382);s.list.children.add(duplicate);});
        refused(s->{AccessibilityNodeInfo duplicate=new AccessibilityNodeInfo();duplicate.id=AREA;
            duplicate.scrollable=true;s.root.children.add(duplicate);});
        refused(s->{AccessibilityNodeInfo p=s.root;for(int i=0;i<101;i++){
            AccessibilityNodeInfo c=new AccessibilityNodeInfo();p.children.add(c);p=c;}});
        invalidTarget(new byte[]{0,0});
        invalidTarget(new byte[]{0,97});
        invalidTarget(new byte[]{0,3,'a'});
        invalidTarget(new byte[]{0,1,(byte)0xff});
        invalidTarget(new byte[]{0,3,'.','.','/'});
        byte[] target=TARGET.getBytes(StandardCharsets.US_ASCII);
        byte[] packet=new byte[target.length+2];packet[1]=(byte)target.length;
        System.arraycopy(target,0,packet,2,target.length);
        if(!TARGET.equals(NodeRevealAction.readTarget(new DataInputStream(new ByteArrayInputStream(packet)))))
            throw new AssertionError("Exact resource did not round-trip");
        cases++;
        System.out.println("NATIVE_REVEAL_GUARD_CASES="+cases);
    }
}
