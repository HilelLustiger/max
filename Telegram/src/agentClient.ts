import { config } from "./config.js";

export interface ClarificationResponse {
  field: string;
  question: string;
  options: string[];
}

export interface ChatResponse {
  reply: string;
  clarification?: ClarificationResponse;
}

export async function askAgent(
  externalId: string,
  text: string,
  requestId: string,
): Promise<ChatResponse> {
  const response = await fetch(`${config.agentUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Request-Id": requestId },
    body: JSON.stringify({ channel: "telegram", external_id: externalId, text }),
  });

  if (!response.ok) {
    throw new Error(`agent-core responded with ${response.status}`);
  }

  return (await response.json()) as ChatResponse;
}
