import { randomUUID } from "node:crypto";
import { Bot, InlineKeyboard, type BotConfig, type Context } from "grammy";
import { config } from "./config.js";
import { askAgent } from "./agentClient.js";
import { logger } from "./logger.js";

const FALLBACK_REPLY = "Sorry, I'm having trouble responding right now. Please try again in a moment.";
const START_REPLY = "Hi! I'm Max. Send me a text message and I'll get back to you.";
const UNSUPPORTED_REPLY = "I can only handle text messages right now.";

// Telegram rejects an inline button with empty callback_data ("Text buttons are not allowed"),
// but an option's value can legitimately be "" (e.g. "No due date" - see request_clarification's
// contract). Stand in a non-empty placeholder for the button and translate it back on tap.
const EMPTY_VALUE_CALLBACK_DATA = "__empty__";

async function replyWithAgentResponse(
  ctx: Context,
  chatId: string,
  text: string,
  requestId: string,
): Promise<void> {
  const response = await askAgent(chatId, text, requestId);
  if (response.options) {
    const keyboard = new InlineKeyboard(
      response.options.map((option) => [
        InlineKeyboard.text(option.label, option.value || EMPTY_VALUE_CALLBACK_DATA),
      ]),
    );
    await ctx.reply(response.reply, { reply_markup: keyboard });
  } else {
    await ctx.reply(response.reply);
  }
}

export function createBot(token: string = config.telegramBotToken, options?: BotConfig<Context>): Bot {
  const bot = new Bot(token, options);

  bot.command("start", async (ctx) => {
    await ctx.reply(START_REPLY);
  });

  bot.on("message:text", async (ctx) => {
    const chatId = String(ctx.chat.id);
    const requestId = randomUUID();
    logger.info("message_received", { request_id: requestId, chat_id: chatId });

    // Lets the user know we've seen their message right away, before the (possibly slow)
    // agent call below - not fatal to the reply if it fails for any reason.
    try {
      await ctx.react("👀");
    } catch (error) {
      logger.error("reaction_failed", { request_id: requestId, chat_id: chatId, error: String(error) });
    }

    try {
      await replyWithAgentResponse(ctx, chatId, ctx.message.text, requestId);
      logger.info("reply_sent", { request_id: requestId, chat_id: chatId });
    } catch (error) {
      logger.error("agent_call_failed", { request_id: requestId, chat_id: chatId, error: String(error) });
      await ctx.reply(FALLBACK_REPLY);
    }
  });

  bot.on("callback_query:data", async (ctx) => {
    if (!ctx.chat) return;
    const chatId = String(ctx.chat.id);
    const requestId = randomUUID();
    const selectedOption =
      ctx.callbackQuery.data === EMPTY_VALUE_CALLBACK_DATA ? "" : ctx.callbackQuery.data;
    logger.info("callback_query_received", { request_id: requestId, chat_id: chatId });

    await ctx.answerCallbackQuery();
    try {
      await replyWithAgentResponse(ctx, chatId, selectedOption, requestId);
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
