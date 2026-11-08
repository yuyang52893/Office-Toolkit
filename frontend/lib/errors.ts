export class ApiError extends Error {
  code: string;
  details?: unknown;
  status: number;

  constructor(message: string, code = "REQUEST_FAILED", status = 0, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

