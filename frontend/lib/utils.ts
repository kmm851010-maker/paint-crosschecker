export function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ");
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve((reader.result as string).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export function downloadBase64(base64: string, filename: string) {
  const blob = b64toBlob(base64, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function b64toBlob(b64Data: string, contentType = "") {
  const byteChars = atob(b64Data);
  const byteArrays = [];
  for (let i = 0; i < byteChars.length; i += 512) {
    const slice = byteChars.slice(i, i + 512);
    const byteNumbers = Array.from(slice).map((c) => c.charCodeAt(0));
    byteArrays.push(new Uint8Array(byteNumbers));
  }
  return new Blob(byteArrays, { type: contentType });
}

export function kstNow() {
  return new Date(Date.now() + 9 * 3600000);
}

export function kstDateStr(date?: Date) {
  const d = date ?? kstNow();
  return d.toISOString().slice(0, 10);
}

export function formatDateTime(str: string) {
  if (!str) return "";
  return str.replace("T", " ").slice(0, 16);
}
