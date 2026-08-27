import { randomUUID } from "node:crypto";
import { Bot, type BotConfig, type Context } from "grammy";
import { config } from "./config.js";
import { askAgent } from "./agentClient.js";
import { logger } from "./logger.js";

const FALLBACK_REPLY = "Sorry, I'm having trouble responding right now. Please try again in a moment.";
const START_REPLY = "Hi! I'm Max. Send me a text message and I'll get back to you.";
const UNSUPPORTED_REPLY = "I can only handle text messages right now.";

export function createBot(token: string = config.telegramBotToken, options?: BotConfig<Context>): Bot {
  const bot = new Bot(token, options);

  bot.command("start", async (ctx) => {
    await ctx.reply(START_REPLY);
  });

  bot.on("message:text", async (ctx) => {
    const chatId = String(ctx.chat.id);
    const requestId = randomUUID();
    logger.info("message_received", { request_id: requestId, chat_id: chatId });

    try {
      const reply = await askAgent(chatId, ctx.message.text, requestId);
      await ctx.reply(reply);
      logger.info("reply_sent", { request_id: requestId, chat_id: chatId });
    } catch (error) {
      logger.error("agent_call_failed", { request_id: requestId, chat_id: chatId, error: String(error) });
      await ctx.reply(FALLBACK_REPLY);
    }
  });

  bot.on("message", async (ctx) => {
    await ctx.reply(UNSUPPORTED_REPLY);
  });

  return bot;
}
