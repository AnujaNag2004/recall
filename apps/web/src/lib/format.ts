export function formatTimestamp(totalSeconds: number): string {
  const whole = Math.floor(totalSeconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const seconds = String(whole % 60).padStart(2, "0");
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${seconds}` : `${minutes}:${seconds}`;
}

const dateTime = new Intl.DateTimeFormat(undefined, {
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});
const dateOnly = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });

export const formatDateTime = (value: string | Date) => dateTime.format(new Date(value));
export const formatDate = (value: string | Date) => dateOnly.format(new Date(value));

/** The value a datetime-local input needs, in the viewer's own time zone. */
export function toLocalInput(value: Date): string {
  const offset = value.getTimezoneOffset() * 60000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

export const SOURCE_LABELS: Record<string, string> = {
  youtube: "YouTube",
  x: "X",
  instagram: "Instagram",
  facebook: "Facebook",
  linkedin: "LinkedIn",
  reddit: "Reddit",
  article: "Article",
  pdf: "PDF",
  image: "Image",
  audio: "Audio",
  video: "Video",
  text: "Note",
};
