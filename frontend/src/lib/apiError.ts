// FastAPI error bodies come in two shapes depending on how the error was raised: a plain
// `{detail: string}` for manually-raised HTTPException (404s, 403s, business-rule 422s),
// or `{detail: ValidationError[]}` for pydantic's automatic request validation -- openapi-fetch
// hands back whichever one the server actually sent, untyped as `unknown` at the call site.
export function formatApiError(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((entry) => (entry && typeof entry === "object" && "msg" in entry ? String((entry as { msg: unknown }).msg) : JSON.stringify(entry)))
        .join("; ");
    }
  }
  return String(error);
}
