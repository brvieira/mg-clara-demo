import logotipo from "@/assets/logotipo.png";
import { extractChips } from "@/lib/format";
import type { ChatMessage } from "@/types";
import { TypingIndicator } from "@/components/TypingIndicator";

export function ChatBubble({ message }: { message: ChatMessage }) {
  if (message.role === "system") {
    return (
      <div className="mx-auto max-w-[82%] rounded-full bg-red-50 px-3 py-1.5 text-center text-xs text-red-700">
        {message.text}
      </div>
    );
  }

  const isAgent = message.role === "agent";
  const showTyping = isAgent && message.pending && message.text === "";
  const chips = isAgent ? extractChips(message.text) : [];

  return (
    <div className={`flex items-end gap-2 ${isAgent ? "justify-start" : "justify-end"}`}>
      {isAgent && (
        <div className="size-7 shrink-0 overflow-hidden rounded-md bg-white ring-1 ring-[var(--vz-border)]">
          <img
            src={logotipo}
            alt="Clara"
            className="size-full object-cover"
            style={{ objectPosition: "left center" }}
          />
        </div>
      )}

      <div
        className={`max-w-[82%] px-3.5 py-2.5 text-sm whitespace-pre-wrap ${
          isAgent
            ? "rounded-tl-2xl rounded-tr-2xl rounded-br-2xl rounded-bl-[5px] bg-vz-branco text-vz-ink shadow-[0_1px_3px_rgba(13,27,42,.06)]"
            : "rounded-tl-2xl rounded-tr-2xl rounded-bl-2xl rounded-br-[5px] bg-vz-roxo text-vz-branco"
        }`}
      >
        {showTyping ? (
          <TypingIndicator />
        ) : (
          <>
            {message.text}
            {chips.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {chips.map((chip) => (
                  <span
                    key={chip}
                    className="mono rounded-full bg-[var(--vz-accent-soft)] px-2 py-0.5 text-[11px] text-vz-roxo"
                  >
                    {chip}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
        <div className={`mt-1 text-[10px] ${isAgent ? "text-[var(--vz-muted)]" : "text-white/70"}`}>
          {message.time}
        </div>
      </div>
    </div>
  );
}
