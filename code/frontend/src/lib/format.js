export const categories = [
  "Groceries",
  "Dining",
  "Transport",
  "Shopping",
  "Health",
  "Other",
];
export const colours = {
  Groceries: "#147b74",
  Dining: "#4678c4",
  Transport: "#ebac46",
  Shopping: "#8b73b8",
  Health: "#cf7180",
  Other: "#78899b",
};
export const money = (value = 0) =>
  new Intl.NumberFormat("en-AU", { style: "currency", currency: "AUD" }).format(
    value,
  );
export function sydneyDay(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Sydney",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}
export const currentMonth = () => sydneyDay().slice(0, 7);
export const dateLabel = (day) =>
  day
    ? new Intl.DateTimeFormat("en-AU", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(`${day}T12:00:00Z`))
    : "Awaiting receipt";
export const monthLabel = (month) =>
  new Intl.DateTimeFormat("en-AU", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${month}-01T12:00:00Z`));

// Integer cents are used for local/demo arithmetic. The API remains authoritative.
export function cents(value) {
  const str = String(value);
  if (!/^\d+(\.\d{1,2})?$/.test(str) || Number(str) > 100000000)
    throw new Error(
      "Enter an AUD amount from 0 to 100,000,000 with at most two decimal places.",
    );
  const [whole, fraction = ""] = str.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}
export function amount(value) {
  return (cents(value) / 100).toFixed(2);
}
export function validateExpense(data) {
  if (!data.merchant?.trim() || data.merchant.length > 200)
    throw new Error("Enter a merchant name of up to 200 characters.");
  const parsed = new Date(`${data.receiptDate}T12:00:00Z`);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(data.receiptDate) ||
    Number.isNaN(parsed.getTime()) ||
    parsed.toISOString().slice(0, 10) !== data.receiptDate
  )
    throw new Error("Enter a valid transaction date.");
  if (!categories.includes(data.category))
    throw new Error("Choose an expense category.");
  const out = {
    merchant: data.merchant.trim(),
    receiptDate: data.receiptDate,
    total: amount(data.total),
    category: data.category,
    currency: "AUD",
  };
  if (data.gst !== "" && data.gst !== undefined) {
    out.gst = amount(data.gst);
    if (cents(out.gst) > cents(out.total))
      throw new Error("GST cannot exceed the total.");
  }
  return out;
}
export function validateFile(file) {
  if (!file) throw new Error("Choose a receipt image.");
  if (!["image/jpeg", "image/png"].includes(file.type))
    throw new Error("Choose a JPEG or PNG image.");
  if (!file.size || file.size > 5 * 1024 * 1024)
    throw new Error(
      "Your receipt must be between 1 byte and 5 MB (5,242,880 bytes).",
    );
  return file;
}
