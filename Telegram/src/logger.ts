type Fields = Record<string, unknown>;

function emit(level: "info" | "error", event: string, fields: Fields = {}): void {
  const line = JSON.stringify({
    timestamp: new Date().toISOString(),
    level: level.toUpperCase(),
    logger: "telegram-gateway",
    event,
    ...fields,
  });
  if (level === "error") {
    console.error(line);
  } else {
    console.log(line);
  }
}

export const logger = {
  info: (event: string, fields?: Fields) => emit("info", event, fields),
  error: (event: string, fields?: Fields) => emit("error", event, fields),
};
