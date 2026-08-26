import { config } from "./config.js";

interface ChatResponse {
  reply: string;
}

export async function askAgent(externalId: string, text: string, requestId: string): Promise<string> {
  const response = await fetch(`${config.agentUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Request-Id": requestId },
    body: JSON.stringify({ channel: "telegram", external_id: externalId, text }),
  });

  if (!response.ok) {
    throw new Error(`agent-core responded with ${response.status}`);
  }

  const data = (await response.json()) as ChatResponse;
  return data.reply;
}
