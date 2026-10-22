const env = process.env;

const integer = (name, fallback) => {
  const value = Number.parseInt(env[name] || "", 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
};

export default {
  get_host: env.EVENTS_GET_HOST || "0.0.0.0",
  get_port: integer("EVENTS_GET_PORT", 9996),
  post_host: env.EVENTS_POST_HOST || "0.0.0.0",
  post_port: integer("EVENTS_POST_PORT", 9997),
  http_host: env.EVENTS_HTTP_HOST || "0.0.0.0",
  http_port: integer("EVENTS_HTTP_PORT", 9995),
  max_queue: integer("EVENTS_MAX_QUEUE", 50),
  max_filter: integer("EVENTS_MAX_FILTER", 5),
  max_body_size: integer("EVENTS_MAX_BODY_SIZE", 200),
  long_poll_timeout: integer("EVENTS_LONG_POLL_TIMEOUT", 60000),
};
