import { validateFile } from "./format.js";

export function postReceipt(
  permission,
  file,
  {
    signal,
    onProgress = () => {},
    xhrFactory = () => new XMLHttpRequest(),
  } = {},
) {
  validateFile(file);
  const url = new URL(permission.upload.url);
  if (url.protocol !== "https:")
    throw new Error("Upload destination must use HTTPS.");
  const form = new FormData();
  Object.entries(permission.upload.fields).forEach(([key, value]) =>
    form.append(key, value),
  );
  form.append("file", file); // S3 requires file last; never override signed fields.
  return new Promise((resolve, reject) => {
    const xhr = xhrFactory();
    const cleanup = () => signal?.removeEventListener("abort", abort);
    const abort = () => {
      xhr.abort();
      cleanup();
      reject(new DOMException("Upload cancelled", "AbortError"));
    };
    if (signal?.aborted) {
      abort();
      return;
    }
    xhr.open("POST", url.href);
    xhr.timeout = 60000;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable)
        onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      cleanup();
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else
        reject(
          new Error(
            "Receipt upload was rejected. Check the file and request a new upload.",
          ),
        );
    };
    xhr.onerror = xhr.ontimeout = () => {
      cleanup();
      reject(
        new Error(
          "Upload connection failed. Check receipt status before uploading again.",
        ),
      );
    };
    signal?.addEventListener("abort", abort, { once: true });
    // No JWT, cookies or AWS credentials are added to the S3 upload.
    xhr.send(form);
  });
}
export function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException("Cancelled", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve();
    }, ms);
    if (signal?.aborted) abort();
    else signal?.addEventListener("abort", abort, { once: true });
  });
}
export async function pollReceipt(
  api,
  id,
  {
    signal,
    onStatus = () => {},
    attempts = 15,
    interval = 2000,
    sleep = delay,
  } = {},
) {
  for (let i = 0; i < attempts; i++) {
    signal?.throwIfAborted();
    const item = await api.detail(id, signal);
    onStatus(item);
    if (["PROCESSED", "FAILED"].includes(item.status)) return item;
    if (i < attempts - 1) await sleep(interval, signal);
  }
  return null; // Unfinished is not a failed receipt or a successful scan.
}
