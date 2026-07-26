export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (response.status === 204) {
    return undefined as T;
  }
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // 非 JSON 响应
  }
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `请求失败（${response.status}）`;
    throw new ApiError(detail, response.status);
  }
  return body as T;
}
