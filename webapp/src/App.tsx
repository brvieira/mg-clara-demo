import { AppHeader } from "@/components/AppHeader";
import { ClientSidebar } from "@/components/ClientSidebar";
import { ChatPanel } from "@/components/ChatPanel";
import { DebugPanel } from "@/components/DebugPanel";
import { ClientProfileDialog } from "@/components/ClientProfileDialog";

function App() {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <AppHeader />
      <div className="flex min-h-0 flex-1">
        <ClientSidebar />
        <ChatPanel />
        <DebugPanel />
      </div>
      <ClientProfileDialog />
    </div>
  );
}

export default App;
