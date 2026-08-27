import { createBot } from "./bot.js";
import { logger } from "./logger.js";

const bot = createBot();

bot.start({
  onStart: () => logger.info("bot_started"),
});

async function shutdown(signal: string): Promise<void> {
  logger.info("shutting_down", { signal });
  await bot.stop();
  process.exit(0);
}

process.once("SIGTERM", () => void shutdown("SIGTERM"));
process.once("SIGINT", () => void shutdown("SIGINT"));
